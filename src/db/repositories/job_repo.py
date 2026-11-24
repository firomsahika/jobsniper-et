"""Job Repository for Ingestion, Deduplication, and Retrieval."""

from datetime import datetime, timedelta, timezone
import logging
import numpy as np
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.job import Job

logger = logging.getLogger(__name__)


class JobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_content_hash(self, content_hash: str) -> Optional[Job]:
        stmt = select(Job).where(Job.content_hash == content_hash)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_id(self, job_id: UUID) -> Optional[Job]:
        stmt = select(Job).where(Job.id == job_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def is_near_duplicate(
        self,
        job_embedding: List[float],
        threshold: float = 0.92,
        lookback_hours: int = 48
    ) -> bool:
        """Evaluates whether an identical or near-duplicate job was posted in the last 48 hours."""
        if not job_embedding:
            return False

        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        stmt = (
            select(Job.job_embedding)
            .where(Job.created_at >= cutoff)
            .where(Job.job_embedding.is_not(None))
        )
        res = await self.session.execute(stmt)
        recent_embeddings = res.scalars().all()
        if not recent_embeddings:
            return False

        job_vec = np.array(job_embedding, dtype=np.float32)
        job_norm = np.linalg.norm(job_vec)
        if job_norm == 0:
            return False

        for emb in recent_embeddings:
            if not emb:
                continue
            emb_vec = np.array(emb, dtype=np.float32)
            emb_norm = np.linalg.norm(emb_vec)
            if emb_norm == 0:
                continue
            sim = float(np.dot(job_vec, emb_vec) / (job_norm * emb_norm))
            if sim >= threshold:
                return True

        return False

    async def create_job(
        self,
        source_channel: str,
        source_message_id: int,
        content_hash: str,
        title: str,
        company: str,
        location: str,
        deadline: Optional[str],
        structured_data: Dict[str, Any],
        job_embedding: List[float],
        raw_text: str,
        posted_at: datetime,
    ) -> Job:
        job = Job(
            source_channel=source_channel,
            source_message_id=source_message_id,
            content_hash=content_hash,
            title=title,
            company=company,
            location=location,
            deadline=deadline,
            structured_data=structured_data,
            job_embedding=job_embedding,
            raw_text=raw_text,
            posted_at=posted_at,
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_recent_jobs(self, limit: int = 10) -> List[Job]:
        stmt = select(Job).order_by(Job.created_at.desc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

