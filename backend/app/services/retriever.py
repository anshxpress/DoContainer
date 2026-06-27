"""
Sprint 3 — Day 1-2: Retriever Interface
Provides an abstract retriever base class, a deterministic MockRetriever
for local development, a ColQwen2Retriever stub that auto-falls back when
the colpali_engine library is unavailable, and a factory function.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------
# A "multi-vector" is a list of token-level embedding vectors.
# Shape: [num_tokens, embedding_dim]
MultiVector = List[List[float]]


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------
class BaseRetriever(ABC):
    """
    Abstract interface for all retriever implementations.
    """

    @abstractmethod
    def embed_query(self, text: str) -> MultiVector:
        """
        Convert a natural-language query string into a multi-vector
        representation suitable for Qdrant MaxSim queries.

        Args:
            text: The raw query string.

        Returns:
            A list of 128-dimensional vectors (one per query token / patch).
        """
        ...


# ---------------------------------------------------------------------------
# Mock retriever (deterministic, no GPU required)
# ---------------------------------------------------------------------------
class MockRetriever(BaseRetriever):
    """
    Deterministic mock retriever for local development and unit tests.
    Produces two 128-dimensional vectors whose values are derived from the
    hash of the input string, giving stable and reproducible results.
    """

    EMBEDDING_DIM = 128
    NUM_VECTORS = 2

    def embed_query(self, text: str) -> MultiVector:
        h = hash(text)
        # Use two complementary values so the multi-vector is non-trivial
        v1 = (abs(h) % 1000) / 1000.0        # e.g. 0.421
        v2 = 1.0 - v1                          # e.g. 0.579
        return [
            [v1] * self.EMBEDDING_DIM,
            [v2] * self.EMBEDDING_DIM,
        ]


# ---------------------------------------------------------------------------
# ColQwen2 stub retriever
# ---------------------------------------------------------------------------
class ColQwen2Retriever(BaseRetriever):
    """
    Stub retriever backed by the ColQwen2 / ColPali vision-language model.

    When `colpali_engine` is installed and a model path is configured,
    this class loads the model and performs real multi-vector inference.
    When the library is missing (local dev / CI), it transparently falls
    back to MockRetriever.

    Usage (production):
        Set the environment variable COLQWEN2_MODEL_PATH to the local
        weights directory or a HuggingFace model ID, e.g.:
            COLQWEN2_MODEL_PATH=vidore/colqwen2-v1.0
    """

    def __init__(self, model_path: str | None = None) -> None:
        self._model_path = model_path
        self._model = None
        self._processor = None
        self._fallback = MockRetriever()
        self._load_model()

    def _load_model(self) -> None:
        """Attempt to load ColQwen2; fall back silently on ImportError."""
        if not self._model_path:
            logger.info(
                "ColQwen2Retriever: COLQWEN2_MODEL_PATH not set — "
                "using MockRetriever fallback."
            )
            return

        try:
            # pylint: disable=import-outside-toplevel
            from colpali_engine.models import ColQwen2, ColQwen2Processor  # type: ignore

            logger.info(
                "ColQwen2Retriever: loading model from '%s' …", self._model_path
            )
            self._model = ColQwen2.from_pretrained(
                self._model_path,
                torch_dtype="auto",
                device_map="auto",
            ).eval()
            self._processor = ColQwen2Processor.from_pretrained(self._model_path)
            logger.info("ColQwen2Retriever: model loaded successfully.")
        except ImportError:
            logger.warning(
                "ColQwen2Retriever: colpali_engine not installed — "
                "falling back to MockRetriever. "
                "Install it with: pip install colpali-engine"
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "ColQwen2Retriever: failed to load model (%s) — "
                "falling back to MockRetriever.",
                exc,
            )

    def embed_query(self, text: str) -> MultiVector:
        if self._model is None or self._processor is None:
            return self._fallback.embed_query(text)

        try:
            import torch  # type: ignore

            inputs = self._processor(text=[text], return_tensors="pt")
            with torch.no_grad():
                embeddings = self._model(**inputs).embeddings  # shape: [1, seq_len, 128]
            # Convert to list[list[float]]
            return embeddings[0].tolist()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "ColQwen2Retriever: inference failed (%s) — falling back to mock.", exc
            )
            return self._fallback.embed_query(text)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_retriever() -> BaseRetriever:
    """
    Factory function returning the best available retriever.

    Resolution order:
    1. If COLQWEN2_MODEL_PATH env var is set → attempt ColQwen2Retriever.
    2. Otherwise → MockRetriever.

    This keeps the import side-effect-free for unit tests.
    """
    import os

    model_path = os.environ.get("COLQWEN2_MODEL_PATH", "").strip()
    if model_path:
        return ColQwen2Retriever(model_path=model_path)
    return MockRetriever()
