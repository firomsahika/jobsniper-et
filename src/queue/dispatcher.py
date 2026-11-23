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
        """Dispatches an alert card to the candidate, honoring quiet hours and rate limits."""
        # 1. Quiet Hours check
        if candidate.quiet_hours_start and candidate.quiet_hours_end:
            if is_in_quiet_hours(candidate.quiet_hours_start, candidate.quiet_hours_end):
                logger.info(f"Candidate {candidate.telegram_id} is in quiet hours (22:00-07:00 EAT). Queueing alert.")
                # Non-critical alert can be delivered after quiet hours
                return False

        # Format message in candidate's language (default English)
        lang = candidate.ui_language or "en"
        
        strengths_formatted = "\n".join(f"• {s}" for s in strengths[:2]) if strengths else "• Strong alignment with your core profile."
        gap_formatted = f"• {gap_advisory}" if gap_advisory else "• Tailor your CV to emphasize relevant project achievements."

        alert_text = (
            f"🎯 <b>NEW JOB MATCH: {score}% Match Score</b>\n\n"
            f"💼 <b>{job_data.get('title')}</b>\n"
            f"🏢 <b>{job_data.get('company', 'Not Specified')}</b>\n"
            f"📍 {job_data.get('location', 'Addis Ababa')} | ⏳ <b>Deadline:</b> {job_data.get('deadline', 'Open')}\n\n"
            f"💡 <b>Alignment Strengths:</b>\n{strengths_formatted}\n\n"
            f"⚠️ <b>Skill Gap Advisory:</b>\n{gap_formatted}\n\n"
            f"📢 <i>Source: {job_data.get('source_channel', 'Telegram')}</i>"
        )

        job_id = job_data.get("id")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📝 Generate Cover Letter", callback_data=f"cvletter:{job_id}:{match_id}"),
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

