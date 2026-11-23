"""Job Repository for Ingestion, Deduplication, and Retrieval."""

from datetime import datetime, timedelta, timezone
import logging
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
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        max_distance = 1.0 - threshold

        stmt = (
            select(Job.id)
            .where(Job.created_at >= cutoff)
            .where(Job.job_embedding.is_not(None))
            .where(Job.job_embedding.cosine_distance(job_embedding) <= max_distance)
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none() is not None

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

