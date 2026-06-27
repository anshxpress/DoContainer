"""
Sprint 4 — Days 3 & 4: SSE Streaming Chat Route  POST /api/v1/chat/ask

Flow:
  1. Validate auth + permissions
  2. Load or create a ChatSession
  3. Persist the user's message
  4. Run hybrid_search to fetch relevant pages + presigned S3 URLs
  5. Fetch page PNG bytes from MinIO for multimodal context
  6. Stream LLM tokens back to the client as Server-Sent Events
  7. Persist the full assistant response + citations on stream completion
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncIterator, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user_context, CurrentUserContext, PermissionChecker
from backend.app.core.db import get_db
from backend.app.models.models import ChatSession, ChatMessage, TeamMembership
from backend.app.services.llm_client import get_llm_client
from backend.app.services.search_service import hybrid_search
from backend.app.core.s3 import s3_storage

logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_user_team_ids(db: Session, user_id: uuid.UUID) -> List[str]:
    memberships = db.query(TeamMembership).filter(TeamMembership.user_id == user_id).all()
    return [str(tm.team_id) for tm in memberships]


def _get_or_create_session(
    db: Session,
    session_id: Optional[str],
    user_id: uuid.UUID,
    org_id: str,
    title: str,
) -> ChatSession:
    if session_id:
        try:
            session_uuid = uuid.UUID(session_id)
            existing = db.query(ChatSession).filter(
                ChatSession.id == session_uuid,
                ChatSession.user_id == user_id,
            ).first()
            if existing:
                return existing
        except (ValueError, AttributeError):
            pass

    # Create new session
    new_session = ChatSession(
        user_id=user_id,
        org_id=uuid.UUID(str(org_id)) if isinstance(org_id, str) else org_id,
        title=title[:100] if title else "New Chat",
    )
    db.add(new_session)
    db.flush()
    return new_session


def _load_history(db: Session, session: ChatSession, last_n: int = 6) -> list:
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(last_n)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in reversed(messages)]


async def _fetch_page_bytes(storage_path: str) -> Optional[bytes]:
    """Download a page PNG from MinIO; returns None on failure."""
    try:
        import io
        buf = io.BytesIO()
        s3_storage.client.download_fileobj(s3_storage.bucket_name, storage_path, buf)
        return buf.getvalue()
    except Exception as exc:
        logger.warning("Could not fetch page bytes from '%s': %s", storage_path, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# SSE generator
# ─────────────────────────────────────────────────────────────────────────────

async def _sse_chat_stream(
    query: str,
    session_id_str: Optional[str],
    document_id_str: Optional[str],
    top_k: int,
    user_id: uuid.UUID,
    org_id: str,
    db: Session,
) -> AsyncIterator[str]:
    """
    Core SSE generator — yields properly formatted SSE event strings.
    SSE format:  'data: <json>\\n\\n'
    """

    # ── 1. Get/create session ────────────────────────────────────────────────
    session = _get_or_create_session(db, session_id_str, user_id, org_id, query[:80])
    yield f"data: {json.dumps({'event': 'session_id', 'session_id': str(session.id)})}\n\n"

    # ── 2. Persist user message ──────────────────────────────────────────────
    user_msg = ChatMessage(session_id=session.id, role="user", content=query)
    db.add(user_msg)
    db.commit()

    # ── 3. Hybrid search ────────────────────────────────────────────────────
    team_ids = _get_user_team_ids(db, user_id)
    try:
        search_results = hybrid_search(
            db=db, query=query, org_id=org_id, team_ids=team_ids, top_k=top_k, document_id=document_id_str
        )
    except Exception as exc:
        logger.error("hybrid_search failed in chat: %s", exc)
        search_results = []

    # Build page metadata for the LLM context
    page_metadata = [
        {
            "doc_name": r.document_name,
            "page_number": r.page_number,
            "text_snippet": r.text_snippet,
            "s3_signed_url": r.s3_signed_url,
            "page_id": r.page_id,
            "document_id": r.document_id,
        }
        for r in search_results
    ]

    # Emit context pages to UI (so it can show them in the viewer panel)
    yield f"data: {json.dumps({'event': 'context_pages', 'pages': page_metadata})}\n\n"

    # ── 4. Fetch PNG bytes for multimodal input ──────────────────────────────
    page_images: List[bytes] = []
    for r in search_results[:4]:   # top 4 pages for vision context
        if hasattr(r, 'png_storage_path') and r.png_storage_path:
            img_bytes = await _fetch_page_bytes(r.png_storage_path)
            if img_bytes:
                page_images.append(img_bytes)

    # ── 5. Load conversation history ─────────────────────────────────────────
    history = _load_history(db, session, last_n=6)

    # ── 6. Stream LLM tokens ─────────────────────────────────────────────────
    llm_client = get_llm_client()
    full_response = ""
    citations = []

    try:
        async for token in llm_client.stream_answer(
            query=query,
            page_images=page_images,
            page_metadata=page_metadata,
            history=history,
        ):
            # Check if this is the done sentinel
            if token.startswith('{"__done__"'):
                try:
                    payload = json.loads(token)
                    citations = payload.get("citations", [])
                    yield f"data: {json.dumps({'event': 'done', 'citations': citations})}\n\n"
                except json.JSONDecodeError:
                    yield f"data: {json.dumps({'event': 'done', 'citations': []})}\n\n"
            else:
                full_response += token
                yield f"data: {json.dumps({'event': 'token', 'token': token})}\n\n"
    except Exception as exc:
        logger.error("LLM stream error: %s", exc)
        error_msg = "I encountered an error generating the response. Please try again."
        yield f"data: {json.dumps({'event': 'token', 'token': error_msg})}\n\n"
        full_response = error_msg
        yield f"data: {json.dumps({'event': 'done', 'citations': []})}\n\n"

    # ── 7. Persist assistant response ────────────────────────────────────────
    try:
        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=full_response,
            citations_json=json.dumps(citations),
        )
        db.add(assistant_msg)
        db.commit()

        # Log API tokens usage metric
        try:
            input_chars = len(query) + 2000
            for h in history:
                input_chars += len(h.get("content", ""))
            input_tokens = max(1, input_chars // 4)
            output_tokens = max(1, len(full_response) // 4)
            total_tokens = input_tokens + output_tokens

            from backend.app.services.metrics_service import log_usage_metric
            log_usage_metric(
                db=db,
                org_id=uuid.UUID(str(org_id)) if isinstance(org_id, str) else org_id,
                metric_type="api_tokens",
                value=float(total_tokens),
                metadata={"session_id": str(session.id), "input_tokens": input_tokens, "output_tokens": output_tokens}
            )
        except Exception as metric_err:
            logger.warning("Failed to log token usage metric in chat: %s", metric_err)
    except Exception as exc:
        logger.error("Failed to persist assistant message: %s", exc)



# ─────────────────────────────────────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/ask",
    summary="Multimodal AI chat with SSE streaming",
    description=(
        "Streams an AI-generated answer grounded in your documents via Server-Sent Events. "
        "Events: session_id → context_pages → token(s) → done."
    ),
    response_class=StreamingResponse,
)
def chat_ask(
    query: str = Query(..., min_length=1, max_length=2000, description="User question"),
    session_id: Optional[str] = Query(None, description="Existing session UUID to continue"),
    document_id: Optional[str] = Query(None, description="Scope chat to a specific document ID"),
    top_k: int = Query(default=5, ge=1, le=20, description="Pages to retrieve for context"),
    current_context: CurrentUserContext = Depends(PermissionChecker("search:documents")),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    POST /api/v1/chat/ask?query=...&session_id=...&top_k=5
    """
    return StreamingResponse(
        _sse_chat_stream(
            query=query,
            session_id_str=session_id,
            document_id_str=document_id,
            top_k=top_k,
            user_id=current_context.user.id,
            org_id=current_context.org_id,
            db=db,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


@router.get(
    "/sessions",
    summary="List chat sessions for the current user",
)
def list_sessions(
    current_context: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """Return the 20 most recent chat sessions for the authenticated user."""
    sessions = (
        db.query(ChatSession)
        .filter(
            ChatSession.user_id == current_context.user.id,
        )
        .order_by(ChatSession.updated_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": str(s.id),
            "title": s.title,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]


@router.get(
    "/sessions/{session_id}/messages",
    summary="Get all messages in a session",
)
def get_session_messages(
    session_id: str,
    current_context: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """Return full message history for a session owned by the current user."""
    session = db.query(ChatSession).filter(
        ChatSession.id == uuid.UUID(session_id),
        ChatSession.user_id == current_context.user.id,
    ).first()
    if not session:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "citations": json.loads(m.citations_json) if m.citations_json else [],
            "created_at": m.created_at.isoformat(),
        }
        for m in session.messages
    ]
