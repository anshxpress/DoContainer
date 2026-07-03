"""
Sprint 11 - Security Service
Provides:
  - SSE-S3 upload headers for MinIO
  - Signed download URL generation (MinIO pre-signed + HMAC claims)
  - Dynamic PDF watermarking (applied at download time)
  - Document ACL evaluation (doc ACL -> folder ACL -> org role)
"""
from __future__ import annotations

import hashlib
import hmac
import io
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.s3 import s3_storage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SSE-S3 helpers
# ---------------------------------------------------------------------------

def get_sse_s3_headers() -> dict:
    """
    Return ExtraArgs for boto3 upload that enable MinIO SSE-S3 (AES-256).
    Pass these to upload_file / put_object calls.
    """
    return {"ServerSideEncryption": "AES256"}


def upload_with_sse(local_path: str, s3_key: str, content_type: str = "application/octet-stream") -> None:
    """Upload a file to MinIO with SSE-S3 encryption enabled."""
    extra_args = {
        "ContentType": content_type,
        "ServerSideEncryption": "AES256",
    }
    s3_storage.client.upload_file(
        local_path, s3_storage.bucket_name, s3_key, ExtraArgs=extra_args
    )
    logger.info("Uploaded %s with SSE-S3 encryption", s3_key)


def upload_bytes_with_sse(data: bytes, s3_key: str, content_type: str = "application/octet-stream") -> None:
    """Upload raw bytes to MinIO with SSE-S3 encryption enabled."""
    s3_storage.client.put_object(
        Bucket=s3_storage.bucket_name,
        Key=s3_key,
        Body=data,
        ContentType=content_type,
        ServerSideEncryption="AES256",
    )
    logger.info("Uploaded bytes %s with SSE-S3 encryption", s3_key)


# ---------------------------------------------------------------------------
# Signed URL generation
# ---------------------------------------------------------------------------

_SIGNING_SECRET = getattr(settings, "SECRET_KEY", "fallback-secret-change-me")


def generate_signed_download_url(
    document_id: str,
    s3_key: str,
    user_id: str,
    expires_seconds: int = 900,
) -> str:
    """
    Generate a MinIO pre-signed URL and embed an HMAC token as a query
    parameter so we can validate identity on the download endpoint.

    Returns the full pre-signed URL with ?sig=<token>&uid=<user_id>&exp=<ts>
    """
    expiry = int(time.time()) + expires_seconds

    # HMAC over document_id + user_id + expiry
    message = f"{document_id}:{user_id}:{expiry}".encode()
    token = hmac.new(_SIGNING_SECRET.encode(), message, hashlib.sha256).hexdigest()

    try:
        presigned_url = s3_storage.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": s3_storage.bucket_name, "Key": s3_key},
            ExpiresIn=expires_seconds,
        )
        sep = "&" if "?" in presigned_url else "?"
        return f"{presigned_url}{sep}sig={token}&uid={user_id}&exp={expiry}"
    except Exception as exc:
        logger.error("Failed to generate pre-signed URL for %s: %s", s3_key, exc)
        raise


def validate_signed_url_token(document_id: str, user_id: str, expiry: int, token: str) -> bool:
    """Verify an HMAC signed download token."""
    if int(time.time()) > expiry:
        return False
    message = f"{document_id}:{user_id}:{expiry}".encode()
    expected = hmac.new(_SIGNING_SECRET.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, token)


# ---------------------------------------------------------------------------
# Dynamic watermarking (PDF, applied per download)
# ---------------------------------------------------------------------------

def apply_watermark_to_pdf(
    pdf_bytes: bytes,
    watermark_text: str,
    username: Optional[str] = None,
    include_timestamp: bool = True,
    opacity: float = 0.15,
) -> bytes:
    """
    Apply a diagonal text watermark to every page of a PDF.
    Uses pypdf (pure Python, no OS dependencies).
    Returns the watermarked PDF as bytes.
    """
    try:
        import pypdf
        from pypdf import PdfWriter, PdfReader
        from pypdf.generic import ArrayObject, FloatObject, NameObject, DictionaryObject

        # Build display text
        parts = [watermark_text]
        if username:
            parts.append(username)
        if include_timestamp:
            parts.append(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
        display_text = "  |  ".join(parts)

        # Create watermark page using reportlab if available, else fallback text overlay
        try:
            from reportlab.pdfgen import canvas as rl_canvas
            from reportlab.lib.pagesizes import A4
            import math

            wm_buf = io.BytesIO()
            c = rl_canvas.Canvas(wm_buf, pagesize=A4)
            width, height = A4
            c.saveState()
            c.setFont("Helvetica", 40)
            c.setFillColorRGB(0.5, 0.5, 0.5, alpha=opacity)
            c.translate(width / 2, height / 2)
            c.rotate(45)
            c.drawCentredString(0, 0, display_text)
            c.restoreState()
            c.save()
            wm_buf.seek(0)
            wm_reader = PdfReader(wm_buf)
            wm_page = wm_reader.pages[0]

            reader = PdfReader(io.BytesIO(pdf_bytes))
            writer = PdfWriter()
            for page in reader.pages:
                page.merge_page(wm_page)
                writer.add_page(page)

            out_buf = io.BytesIO()
            writer.write(out_buf)
            out_buf.seek(0)
            return out_buf.read()

        except ImportError:
            # reportlab not available — use pypdf's own content stream annotation
            reader = PdfReader(io.BytesIO(pdf_bytes))
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)

            out_buf = io.BytesIO()
            writer.write(out_buf)
            logger.warning("reportlab not installed; watermark text omitted (page structure preserved)")
            return out_buf.read()

    except ImportError:
        logger.warning("pypdf not installed; returning original PDF without watermark")
        return pdf_bytes
    except Exception as exc:
        logger.error("Watermark application failed: %s", exc)
        return pdf_bytes


# ---------------------------------------------------------------------------
# Document ACL evaluation
# ---------------------------------------------------------------------------

def check_document_acl(
    db: Session,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    permission: str,
    user_team_ids: Optional[list] = None,
    user_role_id: Optional[uuid.UUID] = None,
) -> bool:
    """
    Returns True if the user has the given permission on this document via ACL.
    Evaluates:
      1. Direct user ACL entry
      2. Team ACL entry (if user belongs to any of user_team_ids)
      3. Role ACL entry (if user's role_id matches)
    Does NOT check org-level RBAC — that's the caller's responsibility.
    """
    from backend.app.models.models import DocumentACL

    # Build principal_id candidates
    candidates: list[tuple[str, uuid.UUID]] = [("user", user_id)]
    for team_id in (user_team_ids or []):
        candidates.append(("team", uuid.UUID(str(team_id))))
    if user_role_id:
        candidates.append(("role", user_role_id))

    for principal_type, principal_id in candidates:
        entry = db.query(DocumentACL).filter(
            DocumentACL.document_id == document_id,
            DocumentACL.principal_type == principal_type,
            DocumentACL.principal_id == principal_id,
            DocumentACL.permission == permission,
        ).first()
        if entry:
            return True

    return False


def get_document_watermark_config(db: Session, document_id: uuid.UUID, folder_id: Optional[uuid.UUID]):
    """
    Returns the DocumentWatermark config for a document.
    Falls back to folder-level watermark if no doc-specific one exists.
    """
    from backend.app.models.models import DocumentWatermark

    wm = db.query(DocumentWatermark).filter(
        DocumentWatermark.document_id == document_id
    ).first()
    if wm:
        return wm

    if folder_id:
        wm = db.query(DocumentWatermark).filter(
            DocumentWatermark.folder_id == folder_id,
            DocumentWatermark.document_id.is_(None),
        ).first()

    return wm
