"""Handler for Job Match Alert Interactions (Feedback Loop)."""

import logging
from uuid import UUID
from aiogram import Router, F
from aiogram.types import CallbackQuery
from src.bot.middlewares.i18n import I18nManager
from src.db.session import async_session_factory
from src.db.repositories.match_repo import MatchRepository

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("fb_applied:"))
async def handle_feedback_applied(callback: CallbackQuery, lang: str, i18n: I18nManager):
    match_id_str = callback.data.split(":")[1]
    try:
        match_id = UUID(match_id_str)
        async with async_session_factory() as session:
            repo = MatchRepository(session)
            await repo.update_feedback(match_id, "applied")

        await callback.answer(i18n.get("fb_applied_ack", lang=lang), show_alert=True)
    except Exception as e:
        logger.error(f"Error updating feedback applied: {e}")
        await callback.answer(i18n.get("fb_applied_ack", lang=lang))


@router.callback_query(F.data.startswith("fb_notrel:"))
async def handle_feedback_not_relevant(callback: CallbackQuery, lang: str, i18n: I18nManager):
    match_id_str = callback.data.split(":")[1]
    try:
        match_id = UUID(match_id_str)
        async with async_session_factory() as session:
            repo = MatchRepository(session)
            await repo.update_feedback(match_id, "not_relevant")

        await callback.answer(i18n.get("fb_notrel_ack", lang=lang), show_alert=True)
    except Exception as e:
        logger.error(f"Error updating feedback not relevant: {e}")
        await callback.answer(i18n.get("fb_notrel_ack", lang=lang))

