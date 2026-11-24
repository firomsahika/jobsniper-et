"""Two-Stage Hybrid AI Matching Engine for JobSniper ET.

Stage 1: ANN Cosine Similarity Pre-filtering (< 20ms) via pgvector.
Stage 2: Gemini LLM Precision Constraint Scoring (Experience, Skills, Domain).
"""

import logging
import re
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.candidate import Candidate
from src.db.models.job import Job
from src.db.repositories.candidate_repo import CandidateRepository
from src.db.repositories.match_repo import MatchRepository
from src.core.gemini import gemini_service
from src.config.settings import settings

logger = logging.getLogger(__name__)


class RoleDomain:
    SOFTWARE_WEB = "software_web"       # Fullstack, Frontend, Backend, Web Developer, React, Django, Node, Python, Software Engineer
    MOBILE = "mobile"                   # Android, iOS, Flutter, React Native, Mobile App Developer
    DEVOPS_CLOUD = "devops_cloud"       # DevOps, Cloud, SRE, Infrastructure, Docker, Kubernetes, AWS
    DATA_AI = "data_ai"                 # Data Analyst, Data Scientist, ML Engineer, AI Engineer
    NETWORK_SYSADMIN = "network_it"     # Network Engineer, Network Administrator, Cisco, IT Support, Helpdesk, Hardware
    CIVIL_STRUCTURAL = "civil_eng"      # Civil Engineer, Structural, Site Engineer, Construction, AutoCAD
    MECHANICAL_ELEC = "mech_elec_eng"   # Mechanical Engineer, Electrical Engineer, Hardware
    FINANCE_ACCOUNTING = "finance_acc"  # Accountant, Auditor, Financial Analyst, Cashier, IFRS
    HR_ADMIN = "hr_admin"               # HR, Human Resources, Administration, Secretary, Office
    MARKETING_SALES = "sales_marketing" # Marketing, Sales, Digital Marketing, Business Development
    OTHER = "other"


def classify_role_domain(title: str, text: str = "", skills: Optional[List[str]] = None) -> str:
    """Classifies a title, description, or skill set into a distinct professional domain cluster."""
    combined = f"{title} {text} {' '.join(skills or [])}".lower()
    t_lower = (title or "").lower()

    # 1. Civil & Structural Engineering
    if any(k in t_lower for k in ["civil", "structural", "surveyor", "architect", "construction", "site engineer", "draftsman"]):
        return RoleDomain.CIVIL_STRUCTURAL

    # 2. Accounting & Finance
    if any(k in t_lower for k in ["accountant", "auditor", "finance", "financial", "cashier", "ifrs", "bookkeeper", "accounting"]):
        return RoleDomain.FINANCE_ACCOUNTING

    # 3. HR & Admin
    if any(k in t_lower for k in ["human resources", "hr officer", "hr specialist", "recruiter", "administrative", "secretary", "receptionist", "office manager"]):
        return RoleDomain.HR_ADMIN

    # 4. Sales & Marketing
    if any(k in t_lower for k in ["sales", "marketing", "digital marketing", "business development", "account executive"]):
        return RoleDomain.MARKETING_SALES

    # 5. Network Engineering & IT Support / Hardware
    if any(k in t_lower for k in ["network engineer", "network administrator", "network technician", "cisco", "ccna", "ccnp", "system administrator", "sysadmin", "it support", "helpdesk", "hardware technician", "telecom engineer", "telecommunication"]):
        if not any(sw in t_lower for sw in ["fullstack", "software", "developer", "backend", "frontend"]):
            return RoleDomain.NETWORK_SYSADMIN

    # 6. Mechanical & Electrical
    if any(k in t_lower for k in ["mechanical engineer", "electrical engineer", "electromechanical"]):
        return RoleDomain.MECHANICAL_ELEC

    # 7. Mobile Development
    if any(k in t_lower for k in ["mobile developer", "android developer", "ios developer", "flutter developer", "react native developer"]):
        return RoleDomain.MOBILE

    # 8. Data & AI
    if any(k in t_lower for k in ["data analyst", "data scientist", "data engineer", "machine learning", "ai engineer", "deep learning", "business intelligence"]):
        return RoleDomain.DATA_AI

    # 9. DevOps & Cloud
    if any(k in t_lower for k in ["devops", "cloud engineer", "sre", "site reliability"]):
        return RoleDomain.DEVOPS_CLOUD

    # 10. Software & Web Engineering (Fullstack, Frontend, Backend)
    if any(k in t_lower for k in ["fullstack", "full stack", "software engineer", "developer", "backend", "frontend", "web developer", "python developer", "react developer", "node developer", "java developer", "api developer"]):
        return RoleDomain.SOFTWARE_WEB

    # Fallback inspection of combined text
    if any(k in combined for k in ["fullstack", "full stack", "software engineering", "frontend developer", "backend developer", "react.js", "next.js", "django", "fastapi"]):
        return RoleDomain.SOFTWARE_WEB

    return RoleDomain.OTHER


def evaluate_domain_compatibility(cand_domain: str, job_domain: str) -> tuple[bool, float, str]:
    """Determines whether candidate and job belong to compatible professional domains."""
    if cand_domain == job_domain:
        return True, 100.0, "Exact domain match"

    # Rules for Software / Web Engineers:
    if cand_domain == RoleDomain.SOFTWARE_WEB:
        # Related software disciplines
        if job_domain == RoleDomain.MOBILE:
            return True, 88.0, "Mobile engineering aligns with software engineering foundation."
        if job_domain == RoleDomain.DEVOPS_CLOUD:
            return True, 85.0, "DevOps/Cloud aligns with backend/infrastructure software engineering."
        if job_domain == RoleDomain.DATA_AI:
            return True, 82.0, "Data/AI engineering shares strong software engineering competencies."
        # HARD INCOMPATIBILITY with Network, Civil, Mechanical, Finance, HR, Sales
        if job_domain in [RoleDomain.NETWORK_SYSADMIN, RoleDomain.CIVIL_STRUCTURAL, RoleDomain.MECHANICAL_ELEC, RoleDomain.FINANCE_ACCOUNTING, RoleDomain.HR_ADMIN, RoleDomain.MARKETING_SALES]:
            return False, 20.0, f"Domain mismatch: Software engineering profile is not suitable for {job_domain} role."

    # Rules for Network / IT Support:
    if cand_domain == RoleDomain.NETWORK_SYSADMIN:
        if job_domain != RoleDomain.NETWORK_SYSADMIN:
            return False, 20.0, f"Domain mismatch: IT/Network profile is not suitable for {job_domain} role."

    # Rules for Civil Engineering:
    if cand_domain == RoleDomain.CIVIL_STRUCTURAL:
        if job_domain != RoleDomain.CIVIL_STRUCTURAL:
            return False, 15.0, f"Domain mismatch: Civil engineering profile is not suitable for {job_domain} role."

    # Rules for Finance / Accounting:
    if cand_domain == RoleDomain.FINANCE_ACCOUNTING:
        if job_domain != RoleDomain.FINANCE_ACCOUNTING:
            return False, 15.0, f"Domain mismatch: Accounting/Finance profile is not suitable for {job_domain} role."

    return True, 75.0, "General cross-domain evaluation"


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

            # Domain Pre-validation (Zero-latency domain incompatibility check)
            cand_profile = candidate.structured_profile or {}
            cand_domain = classify_role_domain(
                cand_profile.get("primary_title", ""),
                cand_profile.get("summary", ""),
                cand_profile.get("skills", [])
            )
            job_domain = classify_role_domain(
                job.title,
                job.raw_text,
                (job.structured_data or {}).get("required_skills", [])
            )
            is_compat, max_score, compat_reason = evaluate_domain_compatibility(cand_domain, job_domain)
            if not is_compat:
                logger.info(f"Candidate {candidate.telegram_id} ({cand_domain}) incompatible with job '{job.title}' ({job_domain}): {compat_reason}")
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

