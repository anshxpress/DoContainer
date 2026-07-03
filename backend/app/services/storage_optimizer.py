"""
Sprint 10 � Storage Optimizer
Centralised utilities for deduplication, compression, and content-addressed storage.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import logging
import zlib
from pathlib import Path
from typing import Any, Optional, Type

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def hash_bytes(data: bytes) -> str:
    """Return the hex SHA-256 digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def hash_text(text: str) -> str:
    """Return the hex SHA-256 digest of a UTF-8 string."""
    return hash_bytes(text.encode("utf-8"))


# ---------------------------------------------------------------------------
# Text compression (for PostgreSQL TEXT/BYTEA blobs)
# ---------------------------------------------------------------------------

def compress_text(text: str) -> bytes:
    """GZIP-compress a string. Returns compressed bytes."""
    return gzip.compress(text.encode("utf-8"), compresslevel=6)


def decompress_text(data: bytes) -> str:
    """Decompress GZIP bytes back to a string."""
    return gzip.decompress(data).decode("utf-8")


# ---------------------------------------------------------------------------
# Image compression (PNG to WebP)
# ---------------------------------------------------------------------------

def png_to_webp(png_path: str, quality: int = 72) -> bytes:
    """
    Convert a PNG file to WebP bytes in memory.

    Args:
        png_path: Absolute path to source PNG file.
        quality:  WebP quality 0-100 (72 is visually lossless for documents).

    Returns:
        WebP-encoded bytes. Falls back to raw PNG bytes if conversion fails.
    """
    try:
        from PIL import Image

        img = Image.open(png_path).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=quality, method=4)
        buf.seek(0)
        webp_bytes = buf.read()
        orig_size = Path(png_path).stat().st_size
        ratio = (1 - len(webp_bytes) / orig_size) * 100 if orig_size else 0
        logger.debug(
            "WebP compression: %d -> %d bytes (%.1f%% reduction)",
            orig_size, len(webp_bytes), ratio,
        )
        return webp_bytes
    except Exception as exc:
        logger.warning("WebP conversion failed for %s: %s. Falling back to raw PNG.", png_path, exc)
        with open(png_path, "rb") as f:
            return f.read()


# ---------------------------------------------------------------------------
# Generic deduplication helper
# ---------------------------------------------------------------------------

def find_completed_duplicate(
    db: Session,
    model: Type[Any],
    hash_value: str,
    exclude_id: Any,
    hash_column: str = "file_hash",
    status_column: str = "status",
    completed_status: str = "completed",
) -> Optional[Any]:
    """
    Return the first completed document whose hash_column matches hash_value,
    excluding exclude_id. Returns None when no duplicate exists.
    """
    if not hash_value:
        return None
    try:
        hash_col = getattr(model, hash_column)
        status_col = getattr(model, status_column)
        id_col = getattr(model, "id")
        return (
            db.query(model)
            .filter(
                hash_col == hash_value,
                status_col == completed_status,
                id_col != exclude_id,
            )
            .first()
        )
    except Exception as exc:
        logger.warning("Dedup query failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Redis value compression (used by cache.py)
# ---------------------------------------------------------------------------

COMPRESSION_THRESHOLD_BYTES = 1024   # compress values larger than 1 KB
COMPRESSION_MARKER = b"\x1f\x8b"    # gzip magic bytes


def maybe_compress(raw: bytes) -> bytes:
    """Compress raw if it is larger than COMPRESSION_THRESHOLD_BYTES."""
    if len(raw) >= COMPRESSION_THRESHOLD_BYTES:
        return gzip.compress(raw, compresslevel=6)
    return raw


def maybe_decompress(data: bytes) -> bytes:
    """Decompress data if it looks like a gzip stream."""
    if data[:2] == COMPRESSION_MARKER:
        try:
            return gzip.decompress(data)
        except Exception:
            pass
    return data
