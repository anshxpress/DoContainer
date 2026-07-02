import logging
import json
import hashlib
from typing import Any, Optional
import redis

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize a global Redis connection pool using the CELERY_BROKER_URL
redis_client = None
try:
    if settings.CELERY_BROKER_URL.startswith("redis://"):
        pool = redis.ConnectionPool.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
        redis_client = redis.Redis(connection_pool=pool)
        logger.info("Redis cache client initialized successfully.")
except Exception as e:
    logger.warning(f"Failed to initialize Redis cache: {e}")


def get_cache(key: str) -> Optional[Any]:
    """Retrieve an item from Redis cache by key."""
    if not redis_client:
        return None
    try:
        val = redis_client.get(key)
        if val:
            return json.loads(val)
    except Exception as e:
        logger.warning(f"Redis get error for {key}: {e}")
    return None

def set_cache(key: str, value: Any, expire: int = 300) -> None:
    """Store an item in Redis cache with expiration in seconds (default 5 mins)."""
    if not redis_client:
        return
    try:
        redis_client.setex(key, expire, json.dumps(value))
    except Exception as e:
        logger.warning(f"Redis set error for {key}: {e}")

def generate_cache_key(prefix: str, **kwargs) -> str:
    """Generate a consistent SHA256 cache key based on a dictionary of arguments."""
    sorted_items = sorted(kwargs.items())
    key_str = json.dumps(sorted_items, default=str)
    hashed = hashlib.sha256(key_str.encode("utf-8")).hexdigest()
    return f"{prefix}:{hashed}"
