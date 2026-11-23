"""Job Ingestion Processor & Pipeline Coordinator."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.gemini import gemini_service
from src.core.matching_engine import MatchingEngine
from src.db.models.job import Job
from src.db.repositories.job_repo import JobRepository
from src.ingestion.deduplicator import JobDeduplicator

logger = logging.getLogger(__name__)


class IngestionPipeline:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.job_repo = JobRepository(session)
        self.matching_engine = MatchingEngine(session)

    async def process_incoming_post(
        self,
        source_channel: str,
        message_id: int,
        raw_text: str,
        posted_at: Optional[datetime] = None
    ) -> Optional[Job]:
        """Runs a raw channel post through deduplication, parsing, embedding, storage, and matching."""
        if not raw_text or len(raw_text.strip()) < 40:
            logger.info("Skipping post: text too short to be a valid job vacancy.")
            return None

        # 1. Exact Duplicate Hash Check
        content_hash = JobDeduplicator.compute_content_hash(raw_text)
        existing = await self.job_repo.get_by_content_hash(content_hash)
        if existing:
            logger.info(f"Duplicate post detected via SHA-256 hash ({content_hash[:8]}). Dropping.")
            return None

        # 2. Generate Embedding
        job_embedding = await gemini_service.get_embedding(raw_text)

        # 3. Near-Duplicate Vector Check (48h rolling window)
        is_near_dup = await self.job_repo.is_near_duplicate(job_embedding, threshold=0.92, lookback_hours=48)
        if is_near_dup:
            logger.info("Near-duplicate job post detected across channels via vector similarity (>= 0.92). Dropping.")
            return None

        # 4. Structured Entity Extraction via Gemini
        structured = await gemini_service.parse_job_post(raw_text, source_channel)

        # 5. Persist Job
        job = await self.job_repo.create_job(
            source_channel=source_channel,
            source_message_id=message_id,
            content_hash=content_hash,
            title=structured.get("title", "Job Vacancy"),
            company=structured.get("company", "Not Specified"),
            location=structured.get("location", "Ethiopia"),
            deadline=structured.get("deadline", "Open"),
            structured_data=structured,
            job_embedding=job_embedding,
            raw_text=raw_text,
            posted_at=posted_at or datetime.now(timezone.utc),
        )
        logger.info(f"Successfully ingested and indexed job: {job.title} at {job.company} (ID: {job.id})")

        # 6. Trigger Stage 1 & Stage 2 Matching Pipeline
        qualified_matches = await self.matching_engine.match_job_against_candidates(job)
        logger.info(f"Job {job.id} matched {len(qualified_matches)} candidate(s).")

        return job

