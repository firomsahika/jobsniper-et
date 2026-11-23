"""FastAPI Dashboard Application for JobSniper ET.

Provides real-time analytics, candidate management, job telemetry, and match monitoring.
"""

from datetime import datetime, timezone, timedelta
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import async_session_factory, get_db_session
from src.db.models.candidate import Candidate
from src.db.models.job import Job
from src.db.models.match import JobMatch
from src.db.models.interview import MockInterview
from src.ingestion.channels import ETHIOPIAN_JOB_CHANNELS, get_monitored_channel_handles

logger = logging.getLogger(__name__)

dashboard_app = FastAPI(
    title="JobSniper ET Admin Dashboard",
    description="Real-time Management & Telemetry for JobSniper ET Telegram Bot",
    version="1.0.0",
)


# -----------------------------------------------------------------
# 1. Real-time Aggregated KPIs
# -----------------------------------------------------------------
@dashboard_app.get("/api/analytics")
async def get_analytics_summary(session: AsyncSession = Depends(get_db_session)):
    """Computes comprehensive telemetry metrics for the dashboard KPI cards."""
    # Candidate stats
    total_candidates = await session.scalar(select(func.count(Candidate.id))) or 0
    active_candidates = await session.scalar(select(func.count(Candidate.id)).where(Candidate.is_active.is_(True))) or 0
    
    # Language distribution
    lang_stmt = select(Candidate.ui_language, func.count(Candidate.id)).group_by(Candidate.ui_language)
    lang_res = await session.execute(lang_stmt)
    languages = dict(lang_res.all())

    # Job stats
    total_jobs = await session.scalar(select(func.count(Job.id))) or 0
    
    # Jobs in last 24h
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    jobs_24h = await session.scalar(select(func.count(Job.id)).where(Job.created_at >= since_24h)) or 0

    # Match stats
    total_matches = await session.scalar(select(func.count(JobMatch.id))) or 0
    high_matches = await session.scalar(select(func.count(JobMatch.id)).where(JobMatch.match_score >= 80)) or 0
    applied_matches = await session.scalar(select(func.count(JobMatch.id)).where(JobMatch.user_feedback == "applied")) or 0
    not_relevant_matches = await session.scalar(select(func.count(JobMatch.id)).where(JobMatch.user_feedback == "not_relevant")) or 0

    # Mock Interview stats
    total_interviews = await session.scalar(select(func.count(MockInterview.id))) or 0
    completed_interviews = await session.scalar(select(func.count(MockInterview.id)).where(MockInterview.status == "completed")) or 0
    avg_score = await session.scalar(select(func.avg(MockInterview.final_score)).where(MockInterview.final_score.is_not(None))) or 0.0

    # Conversion rate
    conversion_rate = round((applied_matches / max(1, total_matches)) * 100, 1)

    return {
        "candidates": {
            "total": total_candidates,
            "active": active_candidates,
            "paused": total_candidates - active_candidates,
            "languages": languages,
        },
        "jobs": {
            "total": total_jobs,
            "last_24h": jobs_24h,
            "channels_monitored": len(get_monitored_channel_handles()),
        },
        "matches": {
            "total": total_matches,
            "high_quality": high_matches,
            "applied": applied_matches,
            "not_relevant": not_relevant_matches,
            "conversion_rate": conversion_rate,
        },
        "interviews": {
            "total": total_interviews,
            "completed": completed_interviews,
            "average_score": round(float(avg_score), 1),
        }
    }


# -----------------------------------------------------------------
# 2. Ingested Jobs Endpoint
# -----------------------------------------------------------------
@dashboard_app.get("/api/jobs")
async def get_jobs_list(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
    channel: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(Job).order_by(desc(Job.created_at))
    if channel:
        stmt = stmt.where(Job.source_channel == channel)
    stmt = stmt.offset(offset).limit(limit)
    res = await session.execute(stmt)
    jobs = res.scalars().all()

    return [
        {
            "id": str(j.id),
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "deadline": j.deadline,
            "source_channel": j.source_channel,
            "required_experience": (j.structured_data or {}).get("required_experience_years", 0),
            "skills": (j.structured_data or {}).get("required_skills", []),
            "employment_type": (j.structured_data or {}).get("employment_type", "Full-time"),
            "posted_at": j.posted_at.isoformat() if j.posted_at else None,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]


# -----------------------------------------------------------------
# 3. Candidates / Users Endpoint
# -----------------------------------------------------------------
@dashboard_app.get("/api/candidates")
async def get_candidates_list(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(Candidate).order_by(desc(Candidate.created_at)).offset(offset).limit(limit)
    res = await session.execute(stmt)
    candidates = res.scalars().all()

    return [
        {
            "id": str(c.id),
            "telegram_id": c.telegram_id,
            "full_name": c.full_name,
            "ui_language": c.ui_language,
            "title": (c.structured_profile or {}).get("primary_title", "Professional"),
            "experience": (c.structured_profile or {}).get("years_of_experience", 0),
            "skills": (c.structured_profile or {}).get("skills", []),
            "min_match_score": c.min_match_score,
            "is_active": c.is_active,
            "has_cv": bool(c.cv_embedding is not None),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in candidates
    ]


# -----------------------------------------------------------------
# 4. Matches Telemetry Endpoint
# -----------------------------------------------------------------
@dashboard_app.get("/api/matches")
async def get_matches_list(
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    stmt = (
        select(JobMatch, Candidate, Job)
        .join(Candidate, JobMatch.candidate_id == Candidate.id)
        .join(Job, JobMatch.job_id == Job.id)
        .order_by(desc(JobMatch.sent_at))
        .limit(limit)
    )
    res = await session.execute(stmt)
    rows = res.all()

    return [
        {
            "match_id": str(m.id),
            "candidate_name": c.full_name,
            "job_title": j.title,
            "company": j.company,
            "channel": j.source_channel,
            "score": m.match_score,
            "reasoning": m.match_reasoning,
            "gap_advisory": m.skill_gap_tip,
            "feedback": m.user_feedback,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        }
        for m, c, j in rows
    ]


# -----------------------------------------------------------------
# 5. Monitored Channels Registry Endpoint
# -----------------------------------------------------------------
@dashboard_app.get("/api/channels")
async def get_channels_status():
    return [
        {
            "handle": ch["handle"],
            "name": ch["name"],
            "category": ch["category"],
            "status": "Listening 24/7",
        }
        for ch in ETHIOPIAN_JOB_CHANNELS
    ]


# -----------------------------------------------------------------
# 6. HTML Dashboard UI (Matching the User's Screenshot Design)
# -----------------------------------------------------------------
@dashboard_app.get("/", response_class=HTMLResponse)
@dashboard_app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Dashboard template not found. Please verify src/dashboard/templates/index.html</h1>"

