"""
Sprint 4 — Day 1: LLM Client Abstraction
Supports Gemini 1.5 Flash (production) and MockLLMClient (local dev / no API key).

Usage:
    from backend.app.services.llm_client import get_llm_client
    client = get_llm_client()
    async for token in client.stream_answer(images, query, history):
        print(token, end="", flush=True)
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Any, Optional
from opentelemetry import trace
from backend.app.core.telemetry import tracer

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Message type alias
# ─────────────────────────────────────────────────────────────────────────────
ChatMessage = Dict[str, str]   # {"role": "user"|"assistant", "content": "..."}


# ─────────────────────────────────────────────────────────────────────────────
# Abstract base
# ─────────────────────────────────────────────────────────────────────────────
class BaseLLMClient(ABC):
    """Common interface for all LLM provider implementations."""

    @abstractmethod
    async def stream_answer(
        self,
        query: str,
        page_images: List[bytes],          # raw PNG bytes per page
        page_metadata: List[Dict[str, Any]], # [{doc_name, page_number, text_snippet}]
        history: Optional[List[ChatMessage]] = None,
    ) -> AsyncIterator[str]:
        """
        Stream answer tokens for the given query + visual context.

        Yields:
            Individual string tokens as they arrive from the model.
            The last yielded value is always a JSON sentinel:
                '{"__done__": true, "citations": [...]}'
        """
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Mock client — no API key required
# ─────────────────────────────────────────────────────────────────────────────
class MockLLMClient(BaseLLMClient):
    """
    Deterministic streaming mock for local development.
    Emits a well-structured answer with [DocName, Page N] citations.
    """

    @tracer.start_as_current_span("mock_llm_client.stream_answer")
    async def stream_answer(
        self,
        query: str,
        page_images: List[bytes],
        page_metadata: List[Dict[str, Any]],
        history: Optional[List[ChatMessage]] = None,
    ) -> AsyncIterator[str]:
        # Build citation references from provided pages
        refs = []
        for m in page_metadata[:3]:
            refs.append(f"[{m.get('doc_name', 'Document')}, Page {m.get('page_number', 1)}]")

        ref_str = " ".join(refs) if refs else "[Document, Page 1]"
        snippet = page_metadata[0].get("text_snippet", "") if page_metadata else ""

        answer = (
            f"Based on the provided documents, here is what I found regarding your query about **{query}**.\n\n"
            f"The relevant information appears on the following pages: {ref_str}.\n\n"
            f"{'The page states: ' + snippet[:120] + '...' if snippet else 'The content matches your search criteria.'}\n\n"
            f"Please refer to the highlighted pages in the viewer panel for full visual context. "
            f"All information is sourced directly from your organization's documents."
        )

        words = answer.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.04)   # simulate realistic token speed

        import json
        citations = [
            {"doc_name": m.get("doc_name", "Document"), "page_number": m.get("page_number", 1)}
            for m in page_metadata[:3]
        ]
        yield json.dumps({"__done__": True, "citations": citations})


# ─────────────────────────────────────────────────────────────────────────────
# Gemini client
# ─────────────────────────────────────────────────────────────────────────────
class GeminiClient(BaseLLMClient):
    """
    Streams answers from Google Gemini 1.5 Flash using multimodal inputs
    (text query + PNG page images as inline bytes).

    Falls back to MockLLMClient when:
    - google-generativeai is not installed
    - GEMINI_API_KEY is empty
    - API call fails
    """

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash") -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._model = None
        self._fallback = MockLLMClient()
        self._init_model()

    def _init_model(self) -> None:
        if not self._api_key:
            logger.warning("GeminiClient: GEMINI_API_KEY is empty — using MockLLMClient fallback.")
            return
        try:
            import google.generativeai as genai   # type: ignore
            genai.configure(api_key=self._api_key)
            self._model = genai.GenerativeModel(
                model_name=self._model_name,
                generation_config={
                    "temperature": 0.2,
                    "top_p": 0.95,
                    "max_output_tokens": 2048,
                },
            )
            logger.info("GeminiClient: model '%s' initialized.", self._model_name)
        except ImportError:
            logger.warning("GeminiClient: google-generativeai not installed. Using mock fallback.")
        except Exception as exc:
            logger.error("GeminiClient: init failed (%s). Using mock fallback.", exc)

    @tracer.start_as_current_span("gemini_client.stream_answer")
    async def stream_answer(
        self,
        query: str,
        page_images: List[bytes],
        page_metadata: List[Dict[str, Any]],
        history: Optional[List[ChatMessage]] = None,
    ) -> AsyncIterator[str]:
        if self._model is None:
            async for token in self._fallback.stream_answer(query, page_images, page_metadata, history):
                yield token
            return

        try:
            import google.generativeai as genai   # type: ignore
            from backend.app.services.citation_parser import build_system_prompt

            system_prompt = build_system_prompt(page_metadata)

            # Build content parts: system instruction + page images + query
            parts: list = [system_prompt]
            for img_bytes in page_images[:6]:   # cap at 6 pages to stay within token limits
                parts.append({"mime_type": "image/png", "data": img_bytes})
            parts.append(f"\nUser question: {query}")

            # History turns (Gemini format)
            chat_history = []
            if history:
                for msg in history[-6:]:   # last 3 turns
                    role = "user" if msg["role"] == "user" else "model"
                    chat_history.append({"role": role, "parts": [msg["content"]]})

            chat = self._model.start_chat(history=chat_history)

            import json
            full_response = ""
            response = await asyncio.to_thread(
                lambda: chat.send_message(parts, stream=True)
            )
            for chunk in response:
                token = chunk.text
                if token:
                    full_response += token
                    yield token

            # Extract and emit citations sentinel
            from backend.app.services.citation_parser import parse_citations
            citations = parse_citations(full_response)
            yield json.dumps({"__done__": True, "citations": [c.__dict__ for c in citations]})

        except Exception as exc:
            logger.error("GeminiClient.stream_answer failed: %s — falling back to mock.", exc)
            async for token in self._fallback.stream_answer(query, page_images, page_metadata, history):
                yield token


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────
def get_llm_client() -> BaseLLMClient:
    """
    Return the configured LLM client.
    Resolution: LLM_PROVIDER env var → "gemini" | "mock"
    """
    from backend.app.core.config import settings

    provider = settings.LLM_PROVIDER.lower()
    if provider == "gemini":
        return GeminiClient(
            api_key=settings.GEMINI_API_KEY,
            model_name=settings.GEMINI_MODEL,
        )
    return MockLLMClient()
