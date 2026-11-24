"""Candidate Repository for Database Operations."""

import logging
from datetime import time
import numpy as np
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.candidate import Candidate
from src.core.security import security_manager

logger = logging.getLogger(__name__)


class CandidateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Candidate]:
        stmt = select(Candidate).where(Candidate.telegram_id == telegram_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_id(self, candidate_id: UUID) -> Optional[Candidate]:
        stmt = select(Candidate).where(Candidate.id == candidate_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_or_update(
        self,
        telegram_id: int,
        full_name: str,
        ui_language: str = "en",
        raw_cv_text: Optional[str] = None,
        structured_profile: Optional[Dict[str, Any]] = None,
        cv_embedding: Optional[List[float]] = None,
        min_match_score: int = 80,
    ) -> Candidate:
        candidate = await self.get_by_telegram_id(telegram_id)
        encrypted_cv = security_manager.encrypt_text(raw_cv_text) if raw_cv_text else None

        if candidate:
            candidate.full_name = full_name
            candidate.ui_language = ui_language
            if encrypted_cv:
                candidate.cv_raw_text_encrypted = encrypted_cv
            if structured_profile:
                candidate.structured_profile = structured_profile
            if cv_embedding:
                candidate.cv_embedding = cv_embedding
            candidate.min_match_score = min_match_score
            candidate.is_active = True
        else:
            candidate = Candidate(
                telegram_id=telegram_id,
                full_name=full_name,
                ui_language=ui_language,
                cv_raw_text_encrypted=encrypted_cv,
                structured_profile=structured_profile or {},
                cv_embedding=cv_embedding,
                min_match_score=min_match_score,
                is_active=True,
            )
            self.session.add(candidate)

        await self.session.commit()
        await self.session.refresh(candidate)
        return candidate

    async def update_language(self, telegram_id: int, language: str) -> None:
        stmt = (
            update(Candidate)
            .where(Candidate.telegram_id == telegram_id)
            .values(ui_language=language)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def update_threshold(self, telegram_id: int, threshold: int) -> None:
        stmt = (
            update(Candidate)
            .where(Candidate.telegram_id == telegram_id)
            .values(min_match_score=threshold)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def update_notification_mode(
        self,
        telegram_id: int,
        mode: str,
        start_t: Optional[time] = None,
        end_t: Optional[time] = None
    ) -> None:
        values = {"notification_mode": mode}
        if start_t is not None:
            values["quiet_hours_start"] = start_t
        if end_t is not None:
            values["quiet_hours_end"] = end_t
        stmt = (
            update(Candidate)
            .where(Candidate.telegram_id == telegram_id)
            .values(**values)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def toggle_active(self, telegram_id: int) -> bool:
        candidate = await self.get_by_telegram_id(telegram_id)
        if not candidate:
            return False
        candidate.is_active = not candidate.is_active
        await self.session.commit()
        return candidate.is_active

    async def delete_all_candidate_data(self, telegram_id: int) -> bool:
        """Purges all user data (CV, profile, matches, mock interviews) per NFR-Security & GDPR."""
        stmt = delete(Candidate).where(Candidate.telegram_id == telegram_id)
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.rowcount > 0

    async def find_candidates_for_vector_match(
        self,
        job_embedding: List[float],
        cosine_threshold: float = 0.70
    ) -> List[Candidate]:
        """Stage 1: Cosine Similarity Pre-filtering.

        Calculates cosine similarity between the job embedding and candidate embeddings,
        returning candidates where similarity >= cosine_threshold.
        """
        stmt = (
            select(Candidate)
            .where(Candidate.is_active.is_(True))
            .where(Candidate.cv_embedding.is_not(None))
        )
        res = await self.session.execute(stmt)
        candidates = list(res.scalars().all())

        if not candidates or not job_embedding:
            return []

        job_vec = np.array(job_embedding, dtype=np.float32)
        job_norm = np.linalg.norm(job_vec)
        if job_norm == 0:
            return candidates[:100]

        scored_candidates = []
        for cand in candidates:
            if not cand.cv_embedding:
                continue
            cand_vec = np.array(cand.cv_embedding, dtype=np.float32)
            cand_norm = np.linalg.norm(cand_vec)
            if cand_norm == 0:
                continue
            sim = float(np.dot(cand_vec, job_vec) / (cand_norm * job_norm))
            if sim >= cosine_threshold:
                scored_candidates.append((sim, cand))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        return [cand for _, cand in scored_candidates[:100]]

