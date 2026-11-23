"""Two-Stage Hybrid AI Matching Engine for JobSniper ET.

Stage 1: ANN Cosine Similarity Pre-filtering (< 20ms) via pgvector.
Stage 2: Gemini LLM Precision Constraint Scoring (Experience, Skills, Domain).
"""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.candidate import Candidate
from src.db.models.job import Job
from src.db.repositories.candidate_repo import CandidateRepository
from src.db.repositories.match_repo import MatchRepository
from src.core.gemini import gemini_service
from src.config.settings import settings

logger = logging.getLogger(__name__)


class MatchingEngine:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.candidate_repo = CandidateRepository(session)
        self.match_repo = MatchRepository(session)

    async def match_job_against_candidates(
        self,
        job: Job
    ) -> List[Dict[str, Any]]:
        """Processes newly ingested job through the two-stage hybrid matching pipeline."""
        if not job.job_embedding:
            logger.warning(f"Job {job.id} does not have an embedding. Skipping match.")
            return []

        # ---------------------------------------------------------
        # Stage 1: Vector Pre-Filtering (ANN Cosine Distance < 20ms)
        # ---------------------------------------------------------
        candidates = await self.candidate_repo.find_candidates_for_vector_match(
            job_embedding=job.job_embedding,
            cosine_threshold=settings.STAGE1_VECTOR_THRESHOLD
        )
        logger.info(f"Stage 1 Vector Pre-filter selected {len(candidates)} candidates for job: {job.title}")

        qualified_matches: List[Dict[str, Any]] = []

        for candidate in candidates:
            # Check if this candidate was already alerted for this job (idempotency)
            existing_match = await self.match_repo.get_match(candidate.id, job.id)
            if existing_match:
                continue

            # ---------------------------------------------------------
            # Stage 2: Gemini LLM Precision Scoring
            # ---------------------------------------------------------
            precision_result = await gemini_service.evaluate_match_precision(
                candidate_profile=candidate.structured_profile or {},
                job_structured=job.structured_data or {},
                job_raw=job.raw_text,
            )

            score = precision_result.get("match_score", 0)
            threshold = candidate.min_match_score or settings.DEFAULT_MIN_MATCH_SCORE

            if score >= threshold:
                strengths = precision_result.get("strengths", [])
                gap_tip = precision_result.get("gap_advisory", "")

                # Record match in database
                match_record = await self.match_repo.create_match(
                    candidate_id=candidate.id,
                    job_id=job.id,
                    match_score=score,
                    match_reasoning=strengths,
                    skill_gap_tip=gap_tip,
                )

                qualified_matches.append({
                    "match_id": match_record.id,
                    "candidate": candidate,
                    "job": job,
                    "score": score,
                    "strengths": strengths,
                    "gap": gap_tip,
                })

        logger.info(f"Stage 2 LLM Precision qualified {len(qualified_matches)} candidates (>= min thresholds).")
        return qualified_matches

