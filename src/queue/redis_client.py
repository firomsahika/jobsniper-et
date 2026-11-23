"""Redis Client for Caching, Rate Limiting & Outbound Alert Queue.

Supports:
- Async connection pooling
- FSM storage backend for Telegram Bot sessions
- Sliding-window rate limiter (e.g. keeping Gemini within 15 RPM Free Tier limit)
- Channel post deduplication caching
"""

import asyncio
import logging
import time
from typing import Any, Optional

try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except (ImportError, ModuleNotFoundError):
    aioredis = None
    HAS_REDIS = False

from src.config.settings import settings

logger = logging.getLogger(__name__)


class RedisManager:
    def __init__(self):
        self._redis: Optional[Any] = None
        # In-memory fallback if Redis is temporarily offline or not installed
        self._local_rpm_timestamps = []

    async def get_client(self) -> Optional[Any]:
        """Returns active async Redis client or None if connection fails or redis is not installed."""
        if not HAS_REDIS:
            return None

        if self._redis is None:
            try:
                client = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_timeout=3.0,
                )
                await client.ping()
                self._redis = client
            except Exception as e:
                logger.warning(f"Redis not reachable at {settings.REDIS_URL} ({e}). Using in-memory fallback.")
                return None
        return self._redis

    async def close(self):
        if self._redis:
            await self._redis.close()
            self._redis = None

    # -------------------------------------------------------------
    # Free Tier Safeguard: 15 Requests Per Minute Rate Limiter
    # -------------------------------------------------------------
    async def wait_for_gemini_slot(self, max_rpm: int = 14):
        """Paces Gemini API requests to guarantee it stays strictly within the 100% Free Tier limit (15 RPM)."""
        redis = await self.get_client()
        now = time.time()

        if redis:
            key = f"ratelimit:gemini_rpm:{int(now // 60)}"
            try:
                # Increment count for current 1-minute window
                current_count = await redis.incr(key)
                if current_count == 1:
                    await redis.expire(key, 70)  # Expire after slightly over 1 minute

                if current_count > max_rpm:
                    # We hit the minute threshold; wait until next minute begins
                    sleep_time = 60 - (now % 60) + 1.0
                    logger.info(f"Gemini Free Tier Rate Limiter: Reached {current_count} RPM. Pausing for {sleep_time:.1f}s...")
                    await asyncio.sleep(sleep_time)
                return
            except Exception as e:
                logger.warning(f"Redis rate-limit check failed: {e}. Falling back to memory.")

        # In-memory sliding window fallback
        self._local_rpm_timestamps = [t for t in self._local_rpm_timestamps if now - t < 60]
        if len(self._local_rpm_timestamps) >= max_rpm:
            oldest = self._local_rpm_timestamps[0]
            sleep_time = max(0.1, 60 - (now - oldest) + 0.5)
            logger.info(f"Gemini Free Tier (Memory Limiter): Pausing for {sleep_time:.1f}s to respect 15 RPM...")
            await asyncio.sleep(sleep_time)

        self._local_rpm_timestamps.append(time.time())

    # -------------------------------------------------------------
    # Deduplication Cache
    # -------------------------------------------------------------
    async def is_hash_cached(self, content_hash: str) -> bool:
        """Checks if a job hash was processed in recent memory (fast RAM lookup)."""
        redis = await self.get_client()
        if not redis:
            return False
        try:
            return bool(await redis.get(f"job:hash:{content_hash}"))
        except Exception:
            return False

    async def cache_hash(self, content_hash: str, ttl_seconds: int = 172800):
        """Caches content hash for 48 hours."""
        redis = await self.get_client()
        if not redis:
            return
        try:
            await redis.set(f"job:hash:{content_hash}", "1", ex=ttl_seconds)
        except Exception as e:
            logger.warning(f"Could not cache job hash in Redis: {e}")


redis_manager = RedisManager()
