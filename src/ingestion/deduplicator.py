"""Two-Layer Job Deduplication Engine for JobSniper ET.

Layer 1: SHA-256 Exact text hash on normalized string.
Layer 2: 48-Hour Cosine Similarity Near-Duplicate Check (>= 0.92).
"""

import hashlib
import re
from typing import List, Optional
from src.db.repositories.job_repo import JobRepository
from src.queue.redis_client import redis_manager


class JobDeduplicator:
    @staticmethod
    def compute_content_hash(raw_text: str) -> str:
        """Computes a normalized SHA-256 hash of the job vacancy text.

        Strips whitespace, converts to lowercase, and removes noise characters.
        """
        # Remove URLs and usernames which may differ slightly across channel cross-posts
        text = re.sub(r"https?://\S+|t\.me/\S+|@\w+", "", raw_text)
        # Normalize whitespace and lowercase
        normalized = "".join(text.lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    async def is_duplicate(
        raw_text: str,
        job_embedding: Optional[List[float]],
        job_repo: JobRepository,
        cosine_threshold: float = 0.92
    ) -> bool:
        """Performs two-layer deduplication check with Redis fast-path caching."""
        content_hash = JobDeduplicator.compute_content_hash(raw_text)

        # Layer 1.1: Fast Redis In-Memory Lookup (< 1ms)
        if await redis_manager.is_hash_cached(content_hash):
            return True

        # Layer 1.2: Persistent PostgreSQL Exact Hash Check
        existing_exact = await job_repo.get_by_content_hash(content_hash)
        if existing_exact:
            await redis_manager.cache_hash(content_hash)
            return True

        # Layer 2: Near-Duplicate 48hr Vector Cosine Check
        if job_embedding:
            is_near = await job_repo.is_near_duplicate(
                job_embedding=job_embedding,
                threshold=cosine_threshold,
                lookback_hours=48
            )
            if is_near:
                return True

        # Cache this unique job hash for 48h to prevent repeated cross-posts
        await redis_manager.cache_hash(content_hash)
        return False

