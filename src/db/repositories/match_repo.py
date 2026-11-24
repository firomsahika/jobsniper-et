"""Match and Mock Interview Repository."""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.match import JobMatch
from src.db.models.interview import MockInterview

logger = logging.getLogger(__name__)


class MatchRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_match(self, candidate_id: UUID, job_id: UUID) -> Optional[JobMatch]:
        stmt = select(JobMatch).where(
            JobMatch.candidate_id == candidate_id,
            JobMatch.job_id == job_id
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_match(
        self,
        candidate_id: UUID,
        job_id: UUID,
        match_score: int,
        match_reasoning: List[str],
        skill_gap_tip: Optional[str] = None,
        is_delivered: bool = False,
    ) -> JobMatch:
        match = JobMatch(
            candidate_id=candidate_id,
            job_id=job_id,
            match_score=match_score,
            match_reasoning=match_reasoning,
            skill_gap_tip=skill_gap_tip,
            is_delivered=is_delivered,
            delivered_at=datetime.utcnow() if is_delivered else None,
        )
        self.session.add(match)
        await self.session.commit()
        await self.session.refresh(match)
        return match

    async def mark_delivered(self, match_id: UUID) -> None:
        stmt = (
            update(JobMatch)
            .where(JobMatch.id == match_id)
            .values(is_delivered=True, delivered_at=datetime.utcnow())
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_undelivered_matches_for_candidate(self, candidate_id: UUID, limit: int = 5) -> List[JobMatch]:
        from sqlalchemy.orm import selectinload
        stmt = (
            select(JobMatch)
            .options(selectinload(JobMatch.job))
            .where(
                JobMatch.candidate_id == candidate_id,
                JobMatch.is_delivered.is_(False)
            )
            .order_by(JobMatch.match_score.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def update_feedback(self, match_id: UUID, feedback: str) -> None:
        stmt = update(JobMatch).where(JobMatch.id == match_id).values(user_feedback=feedback)
        await self.session.execute(stmt)
        await self.session.commit()

    async def save_cover_letter(self, match_id: UUID, cover_letter: str) -> None:
        stmt = update(JobMatch).where(JobMatch.id == match_id).values(cover_letter_draft=cover_letter)
        await self.session.execute(stmt)
        await self.session.commit()


class InterviewRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(
        self,
        candidate_id: UUID,
        job_id: Optional[UUID],
        job_context: str,
        mode: str = "text"
    ) -> MockInterview:
        session = MockInterview(
            candidate_id=candidate_id,
            job_id=job_id,
            job_context=job_context,
            mode=mode,
            transcript=[],
            status="in_progress",
        )
        self.session.add(session)
        await self.session.commit()
        await self.session.refresh(session)
        return session

    async def get_active_session(self, candidate_id: UUID) -> Optional[MockInterview]:
        stmt = (
            select(MockInterview)
            .where(
                MockInterview.candidate_id == candidate_id,
                MockInterview.status == "in_progress"
            )
            .order_by(MockInterview.created_at.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def append_transcript_turn(
        self,
        session_id: UUID,
        turn_data: Dict[str, Any]
    ) -> MockInterview:
        interview = await self.session.get(MockInterview, session_id)
        if interview:
            transcript = list(interview.transcript or [])
            transcript.append(turn_data)
            interview.transcript = transcript
            await self.session.commit()
            await self.session.refresh(interview)
        return interview

    async def complete_session(
        self,
        session_id: UUID,
        final_score: float
    ) -> MockInterview:
        interview = await self.session.get(MockInterview, session_id)
        if interview:
            interview.status = "completed"
            interview.final_score = final_score
            await self.session.commit()
            await self.session.refresh(interview)
        return interview

