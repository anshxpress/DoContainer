"""
Hybrid Pipeline — BGE-M3 Embedding Service + BGE-Reranker Service

Provides:
  BGEM3Service         — Encodes text chunks to 1024-dim dense vectors (FlagEmbedding).
  BGERerankerService   — Cross-encoder reranking (FlagReranker).

Both services use lazy loading and singleton instances to avoid repeated model
loads inside Celery workers. fp16 is used when a CUDA GPU is available.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BGE-M3 Embedding Service
# ---------------------------------------------------------------------------

class BGEM3Service:
    """
    Wraps FlagEmbedding BGEM3FlagModel for dense text embedding.

    Output: normalised 1024-dimensional float vectors (Cosine-ready).
    """

    def __init__(self) -> None:
        self._model = None  # lazy loaded

    def _get_model(self):
        if self._model is not None:
            return self._model

        try:
            from FlagEmbedding import BGEM3FlagModel
            import torch

            use_fp16 = torch.cuda.is_available()
            logger.info(
                f"Loading BGE-M3 model '{settings.BGE_M3_MODEL_PATH}' "
                f"(fp16={use_fp16})…"
            )
            self._model = BGEM3FlagModel(
                settings.BGE_M3_MODEL_PATH,
                use_fp16=use_fp16,
            )
            logger.info("BGE-M3 model loaded successfully.")
        except ImportError:
            logger.warning(
                "FlagEmbedding is not installed. BGE-M3 encoding will return "
                "zero vectors. Install with: pip install FlagEmbedding"
            )
            self._model = None

        return self._model

    def encode_texts(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
    ) -> List[List[float]]:
        """
        Encode a list of text strings into 1024-dim dense vectors.

        Args:
            texts:      Input text strings (already chunked to ≤512 tokens).
            batch_size: Override the global BGE_M3_BATCH_SIZE setting.

        Returns:
            List of float lists, one per input text.
            Returns zero vectors when the model is unavailable.
        """
        model = self._get_model()
        if model is None or not texts:
            return [[0.0] * 1024 for _ in texts]

        bs = batch_size or settings.BGE_M3_BATCH_SIZE
        try:
            output = model.encode(
                texts,
                batch_size=bs,
                max_length=settings.BGE_M3_MAX_TOKENS,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            dense = output["dense_vecs"]
            # Convert numpy array rows to plain float lists
            return [vec.tolist() for vec in dense]
        except Exception as exc:
            logger.error(f"BGE-M3 encode_texts failed: {exc}")
            return [[0.0] * 1024 for _ in texts]

    def encode_query(self, query: str) -> List[float]:
        """
        Encode a single search query string into a 1024-dim dense vector.

        Returns a zero vector when the model is unavailable.
        """
        results = self.encode_texts([query], batch_size=1)
        return results[0] if results else [0.0] * 1024


# ---------------------------------------------------------------------------
# BGE-Reranker Service
# ---------------------------------------------------------------------------

class BGERerankerService:
    """
    Wraps FlagEmbedding FlagReranker (BGE-Reranker-v2-m3) for cross-encoder
    passage reranking.
    """

    def __init__(self) -> None:
        self._reranker = None  # lazy loaded

    def _get_reranker(self):
        if self._reranker is not None:
            return self._reranker

        try:
            from FlagEmbedding import FlagReranker
            import torch

            use_fp16 = torch.cuda.is_available()
            logger.info(
                f"Loading BGE-Reranker model '{settings.BGE_RERANKER_MODEL_PATH}' "
                f"(fp16={use_fp16})…"
            )
            self._reranker = FlagReranker(
                settings.BGE_RERANKER_MODEL_PATH,
                use_fp16=use_fp16,
            )
            logger.info("BGE-Reranker model loaded successfully.")
        except ImportError:
            logger.warning(
                "FlagEmbedding is not installed. Reranking will return input order. "
                "Install with: pip install FlagEmbedding"
            )
            self._reranker = None

        return self._reranker

    def rerank(
        self,
        query: str,
        passages: List[str],
    ) -> List[float]:
        """
        Compute cross-encoder relevance scores for query–passage pairs.

        Args:
            query:    The search query string.
            passages: List of passage strings (already chunked text or snippets).

        Returns:
            List of float scores (one per passage), same order as input.
            Higher is more relevant. Falls back to descending index order
            when the model is unavailable.
        """
        reranker = self._get_reranker()
        if reranker is None or not passages:
            # Fallback: return decreasing pseudo-scores to preserve input ranking
            return [1.0 / (i + 1) for i in range(len(passages))]

        try:
            pairs = [[query, passage] for passage in passages]
            scores = reranker.compute_score(pairs, normalize=True)
            if isinstance(scores, (int, float)):
                scores = [scores]
            return [float(s) for s in scores]
        except Exception as exc:
            logger.error(f"BGEReranker.rerank failed: {exc}")
            return [1.0 / (i + 1) for i in range(len(passages))]


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_bge_service_instance: Optional[BGEM3Service] = None
_reranker_service_instance: Optional[BGERerankerService] = None


def get_bge_service() -> BGEM3Service:
    """Return the process-level BGEM3Service singleton."""
    global _bge_service_instance
    if _bge_service_instance is None:
        _bge_service_instance = BGEM3Service()
    return _bge_service_instance


def get_reranker_service() -> BGERerankerService:
    """Return the process-level BGERerankerService singleton."""
    global _reranker_service_instance
    if _reranker_service_instance is None:
        _reranker_service_instance = BGERerankerService()
    return _reranker_service_instance
