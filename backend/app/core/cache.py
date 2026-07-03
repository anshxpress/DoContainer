import logging
import json
import hashlib
from typing import Any, Optional
import redis

from backend.app.core.config import settings
from backend.app.services.storage_optimizer import maybe_compress, maybe_decompress

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TTL presets (seconds) — namespaced so each cache type has an appropriate
# lifetime without manual per-callsite configuration.
# ---------------------------------------------------------------------------
CACHE_TTL = {
    "search":   300,       # 5 minutes  — search result sets
    "embed":    3_600,     # 1 hour     — embedding vectors per text chunk
    "metadata": 86_400,    # 24 hours   — Gemini metadata extraction results
    "default":  300,       # fallback
}

# Initialize a global Redis connection pool using the CELERY_BROKER_URL
redis_client = None
try:
    if settings.CELERY_BROKER_URL.startswith("redis://"):
        pool = redis.ConnectionPool.from_url(
            settings.CELERY_BROKER_URL,
            decode_responses=False,   # binary mode so we can handle compressed values
        )
        redis_client = redis.Redis(connection_pool=pool)
        logger.info("Redis cache client initialized successfully (binary mode, compression enabled).")
except Exception as e:
    logger.warning(f"Failed to initialize Redis cache: {e}")


def _ttl_for_key(key: str) -> int:
    """Derive the correct TTL from the key prefix."""
    prefix = key.split(":")[0]
    return CACHE_TTL.get(prefix, CACHE_TTL["default"])


def get_cache(key: str) -> Optional[Any]:
    """Retrieve an item from Redis cache by key. Decompresses large values automatically."""
    if not redis_client:
        return None
    try:
        raw = redis_client.get(key)
        if raw:
            decompressed = maybe_decompress(raw)
            return json.loads(decompressed.decode("utf-8"))
    except Exception as e:
        logger.warning(f"Redis get error for {key}: {e}")
    return None


def set_cache(key: str, value: Any, expire: Optional[int] = None) -> None:
    """
    Store an item in Redis cache.
    - expire: explicit TTL in seconds; if None the key-prefix TTL preset is used.
    - Values larger than 1 KB are automatically GZIP-compressed.
    """
    if not redis_client:
        return
    try:
        ttl = expire if expire is not None else _ttl_for_key(key)
        raw = json.dumps(value).encode("utf-8")
        payload = maybe_compress(raw)
        redis_client.setex(key, ttl, payload)
    except Exception as e:
        logger.warning(f"Redis set error for {key}: {e}")


def generate_cache_key(prefix: str, **kwargs) -> str:
    """Generate a consistent SHA256 cache key based on a dictionary of arguments."""
    sorted_items = sorted(kwargs.items())
    key_str = json.dumps(sorted_items, default=str)
    hashed = hashlib.sha256(key_str.encode("utf-8")).hexdigest()
    return f"{prefix}:{hashed}"


def invalidate_pattern(prefix: str) -> int:
    """
    Delete all Redis keys matching `prefix:*`.
    Useful for cache busting on document deletion or metadata updates.
    Returns the number of keys deleted.
    """
    if not redis_client:
        return 0
    deleted = 0
    try:
        pattern = f"{prefix}:*"
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match=pattern, count=200)
            if keys:
                redis_client.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
        if deleted:
            logger.info("Cache invalidated %d keys with prefix '%s'", deleted, prefix)
    except Exception as e:
        logger.warning("Cache invalidation error for prefix '%s': %s", prefix, e)
    return deleted
