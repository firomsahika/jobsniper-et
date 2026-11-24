"""Outbound Alert Dispatcher with Quiet Hours & Rate Limiter."""

import asyncio
from datetime import datetime, time, timezone, timedelta
import logging
from typing import Any, Dict, Optional
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from src.config.settings import settings
from src.db.session import async_session_factory
from src.db.models.candidate import Candidate
from src.db.repositories.candidate_repo import CandidateRepository

logger = logging.getLogger(__name__)

# East Africa Time is UTC+3
EAT_TIMEZONE = timezone(timedelta(hours=3))


def is_in_quiet_hours(start_t: time, end_t: time) -> bool:
    """Checks whether current time in East Africa Time falls inside candidate's quiet hours."""
    now_eat = datetime.now(EAT_TIMEZONE).time()
    if start_t <= end_t:
        return start_t <= now_eat <= end_t
    else:  # Crosses midnight, e.g. 22:00 to 07:00
        return now_eat >= start_t or now_eat <= end_t


class AlertDispatcher:
    def __init__(self, bot: Bot):
        self.bot = bot
        self._delay_between_messages = 1.0 / max(1, settings.OUTBOUND_RATE_LIMIT_PER_SEC)

    async def dispatch_job_alert(
        self,
        candidate: Candidate,
        job_data: Dict[str, Any],
        match_id: str,
        score: int,
        strengths: list,
        gap_advisory: str
    ) -> bool:
        """Dispatches an alert card to the candidate, honoring notification timing modes and rate limits."""
        # 1. Notification Mode and Timing check
        mode = getattr(candidate, "notification_mode", "quiet_standard") or "quiet_standard"

        # If user chose a daily digest mode, hold for digest batch
        if mode in ["digest_morning", "digest_evening"]:
            logger.info(f"Candidate {candidate.telegram_id} is on '{mode}' batch mode. Holding match for scheduled digest.")
            return False

        # If not instant, check quiet hours / work hours
        if mode != "instant" and candidate.quiet_hours_start and candidate.quiet_hours_end:
            if is_in_quiet_hours(candidate.quiet_hours_start, candidate.quiet_hours_end):
                logger.info(f"Candidate {candidate.telegram_id} is in quiet hours ({candidate.quiet_hours_start}-{candidate.quiet_hours_end} EAT). Queueing alert.")
                return False

        # Format message in candidate's language (default English)
        lang = candidate.ui_language or "en"
        
        strengths_formatted = "\n".join(f"• {s}" for s in strengths[:2]) if strengths else "• Strong alignment with your core profile."
        gap_formatted = f"• {gap_advisory}" if gap_advisory else "• Tailor your CV to emphasize relevant project achievements."

        # Source Channel Display & Clickable Direct Link
        from src.ingestion.web_scraper import get_channel_display_name, build_telegram_post_url
        source_ch = job_data.get("source_channel", "@hahujobs")
        source_msg_id = job_data.get("source_message_id")
        structured_info = job_data.get("structured_data") or {}
        post_url = build_telegram_post_url(source_ch, source_msg_id, structured_info)
        channel_display = get_channel_display_name(source_ch)

        # Structured Job Fields
        job_title = job_data.get('title') or 'Professional Vacancy'
        company_name = job_data.get('company') or 'Not Specified'
        location = job_data.get('location') or 'Addis Ababa'
        deadline = job_data.get('deadline') or 'Open / Not specified'
        salary = job_data.get('salary_range') or structured_info.get('salary_range', 'Negotiable')
        job_type = job_data.get('job_type') or structured_info.get('employment_type', 'Full-time')
        req_skills = job_data.get('required_skills') or structured_info.get('required_skills', [])
        skills_display = ", ".join(req_skills[:8]) if req_skills else "Modern Development & Domain Skills"
        exp_years = job_data.get('required_experience_years') or structured_info.get('required_experience_years')
        exp_display = f"{exp_years}+ years" if exp_years else "Open / Fresh Graduate"

        alert_text = (
            f"🎯 <b>NEW JOB MATCH: {score}% Match Score</b>\n\n"
            f"💼 <b>Job Title:</b> {job_title}\n"
            f"🏢 <b>Company:</b> {company_name}\n"
            f"📌 <b>Job Type:</b> {job_type}\n"
            f"📍 <b>Location:</b> {location}\n"
            f"⏳ <b>Experience Required:</b> {exp_display}\n"
            f"🛠️ <b>Required Skills:</b> <code>{skills_display}</code>\n"
            f"📅 <b>Application Deadline:</b> {deadline}\n"
            f"💰 <b>Salary:</b> {salary}\n\n"
            f"💡 <b>Why You Match:</b>\n{strengths_formatted}\n\n"
            f"⚠️ <b>Skill Gap Tip:</b>\n{gap_formatted}\n\n"
            f"📢 <b>Source Channel:</b> <a href=\"{post_url}\">{channel_display}</a>"
        )

        job_id = job_data.get("id")
        apply_txt = "🚀 Apply on Telegram (View Post)"
        if lang == "am":
            apply_txt = "🚀 በቴሌግራም ያመልክቱ (ይመልከቱ)"
        elif lang == "om":
            apply_txt = "🚀 Telegram irratti Iyyadhaa"

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=apply_txt, url=post_url),
                ],
                [
                    InlineKeyboardButton(text="📝 Generate Cover Letter", callback_data=f"cvletter:{job_id}"),
                    InlineKeyboardButton(text="🎙️ Mock Interview", callback_data=f"mockint:{job_id}"),
                ],
                [
                    InlineKeyboardButton(text="✅ Applied", callback_data=f"fb_applied:{match_id}"),
                    InlineKeyboardButton(text="❌ Not Relevant", callback_data=f"fb_notrel:{match_id}"),
                ]
            ]
        )

        try:
            await self.bot.send_message(
                chat_id=candidate.telegram_id,
                text=alert_text,
                reply_markup=kb,
                parse_mode="HTML"
            )

            # Mark match as delivered in database
            if match_id:
                async with async_session_factory() as session:
                    from src.db.repositories.match_repo import MatchRepository
                    from uuid import UUID
                    match_repo = MatchRepository(session)
                    mid = UUID(str(match_id)) if not isinstance(match_id, UUID) else match_id
                    await match_repo.mark_delivered(mid)

            # Global rate-limiting pacing
            await asyncio.sleep(self._delay_between_messages)
            return True
        except TelegramForbiddenError:
            logger.warning(f"Candidate {candidate.telegram_id} blocked the bot (403 Forbidden). Deactivating profile.")
            async with async_session_factory() as session:
                repo = CandidateRepository(session)
                await repo.toggle_active(candidate.telegram_id)
            return False
        except TelegramRetryAfter as e:
            logger.warning(f"Telegram Rate limit hit. Backing off for {e.retry_after} seconds.")
            await asyncio.sleep(e.retry_after)
            return await self.dispatch_job_alert(candidate, job_data, match_id, score, strengths, gap_advisory)
        except Exception as e:
            logger.error(f"Failed to dispatch alert to {candidate.telegram_id}: {e}")
            return False

    async def dispatch_pending_queued_alerts(self) -> int:
        """Dispatches queued alerts to candidates whose quiet period has ended."""
        dispatched_count = 0
        try:
            async with async_session_factory() as session:
                from sqlalchemy import select
                from src.db.models.candidate import Candidate
                from src.db.repositories.match_repo import MatchRepository

                stmt = (
                    select(Candidate)
                    .where(Candidate.is_active.is_(True))
                    .where(Candidate.notification_mode.notin_(["digest_morning", "digest_evening"]))
                )
                res = await session.execute(stmt)
                candidates = list(res.scalars().all())

                for cand in candidates:
                    mode = getattr(cand, "notification_mode", "quiet_standard") or "quiet_standard"
                    if mode != "instant" and cand.quiet_hours_start and cand.quiet_hours_end:
                        if is_in_quiet_hours(cand.quiet_hours_start, cand.quiet_hours_end):
                            continue

                    match_repo = MatchRepository(session)
                    pending_matches = await match_repo.get_undelivered_matches_for_candidate(cand.id, limit=3)
                    for pm in pending_matches:
                        if not pm.job:
                            continue
                        job_data = {
                            "id": pm.job.id,
                            "title": pm.job.title,
                            "company": pm.job.company,
                            "location": pm.job.location,
                            "deadline": pm.job.deadline,
                            "source_channel": pm.job.source_channel,
                            "source_message_id": pm.job.source_message_id,
                            "structured_data": pm.job.structured_data,
                        }
                        sent = await self.dispatch_job_alert(
                            candidate=cand,
                            job_data=job_data,
                            match_id=str(pm.id),
                            score=pm.match_score,
                            strengths=pm.match_reasoning or [],
                            gap_advisory=pm.skill_gap_tip or "",
                        )
                        if sent:
                            dispatched_count += 1

        except Exception as e:
            logger.error(f"Error in dispatch_pending_queued_alerts: {e}")

        return dispatched_count

    async def dispatch_daily_digest(self, target_mode: str = "digest_morning") -> int:
        """Bundles pending matches into a consolidated daily digest for digest-mode candidates."""
        dispatched_count = 0
        try:
            async with async_session_factory() as session:
                from sqlalchemy import select
                from src.db.models.candidate import Candidate
                from src.db.repositories.match_repo import MatchRepository

                stmt = (
                    select(Candidate)
                    .where(Candidate.is_active.is_(True))
                    .where(Candidate.notification_mode == target_mode)
                )
                res = await session.execute(stmt)
                candidates = list(res.scalars().all())

                for cand in candidates:
                    match_repo = MatchRepository(session)
                    pending_matches = await match_repo.get_undelivered_matches_for_candidate(cand.id, limit=5)
                    if not pending_matches:
                        continue

                    lang = cand.ui_language or "en"
                    is_morning = target_mode == "digest_morning"
                    header = "🌅 <b>Good Morning! Your Daily Job Digest</b>" if is_morning else "🌆 <b>Good Evening! Your Daily Job Digest</b>"
                    if lang == "am":
                        header = "🌅 <b>እንደምን አደሩ! የዕለቱ የስራ ማጠቃለያ</b>" if is_morning else "🌆 <b>እንደምን አመሹ! የማታ የስራ ማጠቃለያ</b>"
                    elif lang == "om":
                        header = "🌅 <b>Akkam Bultan! Cuunfaa Hojii Har'aa</b>" if is_morning else "🌆 <b>Akkam Ooltan! Cuunfaa Hojii Galgalaa</b>"

                    from src.ingestion.web_scraper import get_channel_display_name, build_telegram_post_url
                    lines = [f"{header}\n\nHere are top opportunities matching your profile:\n"]
                    for i, pm in enumerate(pending_matches, 1):
                        p_url = build_telegram_post_url(pm.job.source_channel, pm.job.source_message_id, pm.job.structured_data)
                        ch_name = get_channel_display_name(pm.job.source_channel)
                        lines.append(
                            f"<b>{i}. {pm.job.title}</b> at {pm.job.company}\n"
                            f"🎯 <b>Match:</b> <code>{pm.match_score}%</code> | 📍 {pm.job.location}\n"
                            f"📢 <b>Source:</b> <a href=\"{p_url}\">{ch_name}</a> | <a href=\"{p_url}\"><b>👉 Apply on Telegram</b></a>\n"
                        )

                    lines.append("Tap <b>🎯 Job Matches</b> below to view full details and practice mock interviews!")
                    digest_text = "\n".join(lines)

                    try:
                        await self.bot.send_message(
                            chat_id=cand.telegram_id,
                            text=digest_text,
                            parse_mode="HTML"
                        )
                        for pm in pending_matches:
                            await match_repo.mark_delivered(pm.id)
                        dispatched_count += 1
                        await asyncio.sleep(self._delay_between_messages)
                    except Exception as e:
                        logger.error(f"Error sending digest to {cand.telegram_id}: {e}")

        except Exception as e:
            logger.error(f"Error in dispatch_daily_digest: {e}")

        return dispatched_count

    async def check_and_alert_active_candidates(self) -> int:
        """Proactively checks recent fresh jobs (< 48h) against active candidates on 24/7 / instant alert mode.
        
        Guarantees that candidates receive instant notifications whenever a matching job is present
        without requiring them to click 'Get Matches'.
        """
        dispatched_count = 0
        try:
            async with async_session_factory() as session:
                from sqlalchemy import select, desc
                from src.db.models.candidate import Candidate
                from src.db.models.job import Job
                from src.db.models.match import JobMatch
                from src.db.repositories.match_repo import MatchRepository
                from src.core.gemini import gemini_service

                # Fetch active candidates who are not in digest-only mode
                stmt_c = (
                    select(Candidate)
                    .where(Candidate.is_active.is_(True))
                    .where(Candidate.notification_mode.notin_(["digest_morning", "digest_evening"]))
                )
                res_c = await session.execute(stmt_c)
                candidates = list(res_c.scalars().all())
                if not candidates:
                    return 0

                # Fetch recent jobs from the past 48 hours
                now_utc = datetime.now(timezone.utc)
                cutoff = now_utc - timedelta(hours=48)
                stmt_j = (
                    select(Job)
                    .where(Job.posted_at >= cutoff)
                    .order_by(desc(Job.posted_at))
                    .limit(40)
                )
                res_j = await session.execute(stmt_j)
                recent_jobs = list(res_j.scalars().all())
                if not recent_jobs:
                    return 0

                for cand in candidates:
                    mode = getattr(cand, "notification_mode", "quiet_standard") or "quiet_standard"
                    if mode != "instant" and cand.quiet_hours_start and cand.quiet_hours_end:
                        if is_in_quiet_hours(cand.quiet_hours_start, cand.quiet_hours_end):
                            continue

                    for job in recent_jobs:
                        stmt_m = (
                            select(JobMatch)
                            .where(JobMatch.candidate_id == cand.id)
                            .where(JobMatch.job_id == job.id)
                        )
                        res_m = await session.execute(stmt_m)
                        existing_match = res_m.scalar_one_or_none()

                        if existing_match:
                            if existing_match.is_delivered:
                                continue
                            structured_info = job.structured_data or {}
                            job_data = {
                                "id": str(job.id),
                                "title": job.title,
                                "company": job.company,
                                "location": job.location,
                                "deadline": job.deadline,
                                "source_channel": job.source_channel,
                                "source_message_id": job.source_message_id,
                                "structured_data": structured_info,
                                "raw_text": job.raw_text,
                                "job_type": structured_info.get("employment_type", "Full-time"),
                                "required_skills": structured_info.get("required_skills", []),
                                "salary_range": structured_info.get("salary_range", "Negotiable"),
                                "required_experience_years": structured_info.get("required_experience_years", 0),
                            }
                            sent = await self.dispatch_job_alert(
                                candidate=cand,
                                job_data=job_data,
                                match_id=str(existing_match.id),
                                score=existing_match.match_score,
                                strengths=existing_match.match_reasoning or [],
                                gap_advisory=existing_match.skill_gap_tip or "",
                            )
                            if sent:
                                dispatched_count += 1
                        else:
                            # Evaluate match precision with domain & contextual engine
                            precision_result = await gemini_service.evaluate_match_precision(
                                candidate_profile=cand.structured_profile or {},
                                job_structured=job.structured_data or {},
                                job_raw=job.raw_text,
                            )
                            score = precision_result.get("match_score", 0)
                            threshold = cand.min_match_score or settings.DEFAULT_MIN_MATCH_SCORE

                            if score >= threshold:
                                strengths = precision_result.get("strengths", [])
                                gap_tip = precision_result.get("gap_advisory", "")
                                match_repo = MatchRepository(session)
                                match_record = await match_repo.create_match(
                                    candidate_id=cand.id,
                                    job_id=job.id,
                                    match_score=score,
                                    match_reasoning=strengths,
                                    skill_gap_tip=gap_tip,
                                )
                                structured_info = job.structured_data or {}
                                job_data = {
                                    "id": str(job.id),
                                    "title": job.title,
                                    "company": job.company,
                                    "location": job.location,
                                    "deadline": job.deadline,
                                    "source_channel": job.source_channel,
                                    "source_message_id": job.source_message_id,
                                    "structured_data": structured_info,
                                    "raw_text": job.raw_text,
                                    "job_type": structured_info.get("employment_type", "Full-time"),
                                    "required_skills": structured_info.get("required_skills", []),
                                    "salary_range": structured_info.get("salary_range", "Negotiable"),
                                    "required_experience_years": structured_info.get("required_experience_years", 0),
                                }
                                sent = await self.dispatch_job_alert(
                                    candidate=cand,
                                    job_data=job_data,
                                    match_id=str(match_record.id),
                                    score=score,
                                    strengths=strengths,
                                    gap_advisory=gap_tip,
                                )
                                if sent:
                                    dispatched_count += 1

        except Exception as e:
            logger.error(f"Error in check_and_alert_active_candidates: {e}")

        return dispatched_count


async def run_alert_scheduler(bot: Bot):
    """Background loop that periodically releases queued alerts, checks new matches, and delivers scheduled digests."""
    dispatcher = AlertDispatcher(bot)
    logger.info("Outbound Alert & Daily Digest Scheduler active (30s cadence).")
    while True:
        try:
            # 1. Proactive real-time check for active candidates with 24/7 alerts
            new_alerts = await dispatcher.check_and_alert_active_candidates()
            if new_alerts > 0:
                logger.info(f"Dispatched {new_alerts} real-time job alerts to active candidates.")

            # 2. Release queued alerts for users whose quiet hours ended
            released = await dispatcher.dispatch_pending_queued_alerts()
            if released > 0:
                logger.info(f"Released {released} queued job alerts post-quiet hours.")

            # 3. Check for scheduled daily digests
            now_eat = datetime.now(EAT_TIMEZONE)
            # Morning digest between 08:30 and 08:45 EAT
            if now_eat.hour == 8 and 30 <= now_eat.minute <= 45:
                sent = await dispatcher.dispatch_daily_digest("digest_morning")
                if sent > 0:
                    logger.info(f"Dispatched {sent} morning digests.")
            # Evening digest between 18:30 and 18:45 EAT
            elif now_eat.hour == 18 and 30 <= now_eat.minute <= 45:
                sent = await dispatcher.dispatch_daily_digest("digest_evening")
                if sent > 0:
                    logger.info(f"Dispatched {sent} evening digests.")

        except Exception as e:
            logger.error(f"Error in run_alert_scheduler: {e}")

        # Check every 30 seconds
        await asyncio.sleep(30)

