"""Handler for Profile Viewing, Settings, and Data Deletion."""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from src.bot.keyboards.profile import (
    get_profile_actions_kb,
    get_threshold_selection_kb,
    get_delete_confirmation_kb,
)
from src.bot.middlewares.i18n import I18nManager
from src.db.session import async_session_factory
from src.db.repositories.candidate_repo import CandidateRepository

logger = logging.getLogger(__name__)
router = Router()


async def show_profile_card(user_id: int, target_msg: Message, lang: str, i18n: I18nManager, is_edit: bool = False):
    async with async_session_factory() as session:
        repo = CandidateRepository(session)
        candidate = await repo.get_by_telegram_id(user_id)

    if not candidate:
        text = "⚠️ You have not set up a profile yet. Type /start to get started."
        if is_edit:
            await target_msg.edit_text(text)
        else:
            await target_msg.answer(text)
        return

    profile = candidate.structured_profile or {}
    skills_str = ", ".join(profile.get("skills", [])[:5]) or "Not specified"
    status_badge = "🟢 Active (Listening 24/7)" if candidate.is_active else "🔴 Paused"

    q_start = candidate.quiet_hours_start.strftime("%H:%M") if candidate.quiet_hours_start else "22:00"
    q_end = candidate.quiet_hours_end.strftime("%H:%M") if candidate.quiet_hours_end else "07:00"

    card_text = i18n.get(
        "profile_view",
        lang=lang,
        name=candidate.full_name,
        title=profile.get("primary_title", "Professional"),
        experience=profile.get("years_of_experience", 0),
        skills=skills_str,
        threshold=candidate.min_match_score,
        quiet_start=q_start,
        quiet_end=q_end,
        status_badge=status_badge,
    )

    kb = get_profile_actions_kb(candidate.is_active, candidate.min_match_score, lang=lang)

    if is_edit:
        await target_msg.edit_text(card_text, reply_markup=kb, parse_mode="HTML")
    else:
        await target_msg.answer(card_text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("profile"))
@router.message(F.text.in_(["👤 My Profile", "👤 የኔ መረጃ", "👤 Profile Koo", "⚙️ Preferences", "⚙️ ምርጫዎች", "⚙️ Filannoo"]))
async def view_profile_command(message: Message, lang: str, i18n: I18nManager):
    await show_profile_card(message.from_user.id, message, lang, i18n, is_edit=False)


@router.callback_query(F.data == "settings:threshold")
async def open_threshold_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎯 <b>Select your Minimum Match Threshold:</b>\n\n"
        "Only jobs matching at or above this percentage will trigger instant Telegram alerts.\n"
        "• <b>70% - 75%:</b> Higher volume, broader opportunities.\n"
        "• <b>80% (Recommended):</b> Balanced high-relevance feed.\n"
        "• <b>90% - 95%:</b> Ultra-strict exact qualification match.",
        reply_markup=get_threshold_selection_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_thresh:"))
async def save_threshold(callback: CallbackQuery, lang: str, i18n: I18nManager):
    new_thresh = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        repo = CandidateRepository(session)
        await repo.update_threshold(callback.from_user.id, new_thresh)

    await callback.answer(f"Match threshold updated to {new_thresh}%!")
    await show_profile_card(callback.from_user.id, callback.message, lang, i18n, is_edit=True)


@router.callback_query(F.data == "settings:toggle_active")
async def toggle_active_status(callback: CallbackQuery, lang: str, i18n: I18nManager):
    async with async_session_factory() as session:
        repo = CandidateRepository(session)
        is_now_active = await repo.toggle_active(callback.from_user.id)

    status_msg = "Alerts resumed! Radar is active." if is_now_active else "Alerts paused."
    await callback.answer(status_msg)
    await show_profile_card(callback.from_user.id, callback.message, lang, i18n, is_edit=True)


@router.callback_query(F.data == "settings:back")
async def back_to_profile(callback: CallbackQuery, lang: str, i18n: I18nManager):
    await show_profile_card(callback.from_user.id, callback.message, lang, i18n, is_edit=True)


@router.callback_query(F.data == "settings:delete_confirm")
@router.message(Command("delete_data"))
async def prompt_delete_data(event: [Message, CallbackQuery], lang: str, i18n: I18nManager):
    warn_text = (
        "⚠️ <b>DATA DELETION CONFIRMATION</b>\n\n"
        "This will permanently purge:\n"
        "• Your CV & encrypted resume records\n"
        "• Your structured career profile & vector embeddings\n"
        "• All job match histories & cover letter drafts\n"
        "• All mock interview records\n\n"
        "This action cannot be undone. Are you sure?"
    )
    kb = get_delete_confirmation_kb()
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(warn_text, reply_markup=kb, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(warn_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "delete:confirm_yes")
async def execute_data_deletion(callback: CallbackQuery):
    async with async_session_factory() as session:
        repo = CandidateRepository(session)
        await repo.delete_all_candidate_data(callback.from_user.id)

    await callback.message.edit_text(
        "✅ <b>All your personal data and profiles have been completely purged from our database.</b>\n\n"
        "You can type /start anytime if you wish to register again.",
        parse_mode="HTML"
    )
    await callback.answer("Data deleted.")

