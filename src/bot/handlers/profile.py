"""Handler for Afriwork-Style Navigation: Settings, Account, Terms, and Job Matches."""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from src.bot.keyboards.common import (
    get_main_menu_reply_kb,
    get_settings_reply_kb,
    get_language_inline_kb,
)
from src.bot.keyboards.profile import (
    get_profile_actions_kb,
    get_threshold_selection_kb,
    get_delete_confirmation_kb,
)
from src.bot.middlewares.i18n import I18nManager
from src.db.session import async_session_factory
from src.db.repositories.candidate_repo import CandidateRepository
from src.db.repositories.job_repo import JobRepository
from src.db.models.match import JobMatch
from sqlalchemy import select, desc

logger = logging.getLogger(__name__)
router = Router()


# -----------------------------------------------------------------
# 1. Settings Navigation (Matching Afriwork Screenshot Structure)
# -----------------------------------------------------------------
@router.message(Command("settings"))
@router.message(F.text.in_([
    "⚙️ Settings", "Settings", "⚙️ ቅንብሮች", "⚙️ Filannoowwan",
    "⚙️ Settings / ምርጫዎች", "⚙️ Preferences"
]))
async def handle_settings_menu(message: Message, lang: str):
    """Displays settings overview card and switches bottom keyboard to Settings mode."""
    settings_text = (
        "<b>Settings</b>\n\n"
        "<b>Language/ ቋንቋ:</b> to change the language preference / ቋንቋ ለመቀየር\n\n"
        "<b>Terms and conditions:</b> to view our terms and conditions & privacy policy\n\n"
        "<b>Account:</b> to view or update your career profile & qualifications"
    )
    await message.answer(
        settings_text,
        reply_markup=get_settings_reply_kb(lang=lang),
        parse_mode="HTML"
    )


# -----------------------------------------------------------------
# 2. Language Picker Handler
# -----------------------------------------------------------------
@router.message(F.text.in_(["Language/ቋንቋ", "Language", "ቋንቋ", "Afaan"]))
async def handle_language_button(message: Message):
    """Presents inline language selection flags."""
    await message.answer(
        "🌐 <b>Select your preferred language / እባክዎ ቋንቋ ይምረጡ:</b>",
        reply_markup=get_language_inline_kb(),
        parse_mode="HTML"
    )


# -----------------------------------------------------------------
# 3. Terms and Conditions Handler
# -----------------------------------------------------------------
@router.message(Command("terms"))
@router.message(F.text.in_([
    "Terms and Conditions", "Terms and conditions", "Terms", "ውሎች እና ደንቦች"
]))
async def handle_terms_and_conditions(message: Message):
    terms_text = (
        "📄 <b>JobSniper ET — Terms & Conditions & Privacy Policy</b>\n\n"
        "🔒 <b>Data Protection & Privacy:</b>\n"
        "• Your resume and profile details are encrypted using bank-grade <b>AES-256-GCM</b> authenticated encryption.\n"
        "• We do not sell, rent, or leak your private information to third-party advertisers.\n"
        "• You can permanently delete all your data and uploaded CV files anytime by clicking <i>Delete Account Data</i> or using /delete_data.\n\n"
        "🎯 <b>Service Operation:</b>\n"
        "• JobSniper ET monitors 31+ public Ethiopian Telegram job channels 24/7 to discover vacancies matching your skills.\n"
        "• Match scores and skill gap tips are powered by high-speed vector embeddings and Gemini AI.\n\n"
        "✨ <b>Free Tier:</b>\n"
        "• Core channel scanning, deduplication, instant alerts, and STAR mock interview simulations are provided 100% free of charge."
    )
    await message.answer(terms_text, parse_mode="HTML")


# -----------------------------------------------------------------
# 4. Back Button Handler (Returns to Main Menu Keyboard)
# -----------------------------------------------------------------
@router.message(F.text.in_(["Back", "back", "🔙 Back", "ተመለስ", "Deebi'i"]))
async def handle_back_button(message: Message, lang: str):
    """Returns smoothly to the primary navigation grid."""
    await message.answer(
        "📋 <b>Main Menu</b>\n\nSelect an option below to continue:",
        reply_markup=get_main_menu_reply_kb(lang=lang),
        parse_mode="HTML"
    )


# -----------------------------------------------------------------
# 5. Account / Profile Handler (Afriwork-Inspired Staying Updated Banner)
# -----------------------------------------------------------------
@router.message(Command("profile"))
@router.message(Command("account"))
@router.message(F.text.in_([
    "Account", "account", "👤 Account", "👤 My Profile", "👤 የኔ አካውንት",
    "👤 የኔ መረጃ", "👤 Account Koo", "👤 Profile Koo"
]))
async def view_account_handler(message: Message, lang: str, i18n: I18nManager):
    user_id = message.from_user.id
    async with async_session_factory() as session:
        repo = CandidateRepository(session)
        candidate = await repo.get_by_telegram_id(user_id)

    if not candidate:
        await message.answer("⚠️ You have not set up a profile yet. Send /start to get started.")
        return

    # Afriwork-style motivational callout
    banner_text = (
        "<b>Staying Updated Matters!</b>\n\n"
        "A well maintained profile helps our AI matcher find high-salary opportunities and land your dream job sooner.\n\n"
        "View and update your career details below:"
    )
    await message.answer(banner_text, parse_mode="HTML")

    # Send detailed profile card
    await show_profile_card(user_id, message, lang, i18n, is_edit=False)


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
    skills_list = profile.get("skills", [])
    skills_str = ", ".join(skills_list[:6]) if skills_list else "General Professional"
    status_badge = "🟢 Active (Radar Listening 24/7)" if candidate.is_active else "⏸️ Alerts Paused"

    card_text = (
        f"👤 <b>Candidate Account: {candidate.full_name}</b>\n\n"
        f"💼 <b>Primary Role:</b> {profile.get('primary_title', 'Professional')}\n"
        f"🎓 <b>Education:</b> {profile.get('highest_education', 'Higher Education')}\n"
        f"⏳ <b>Experience:</b> {profile.get('years_of_experience', 0)} years\n"
        f"🛠️ <b>Top Skills:</b> <code>{skills_str}</code>\n\n"
        f"⚙️ <b>Current Sniper Preferences:</b>\n"
        f"• <b>Match Threshold:</b> <code>{candidate.min_match_score}%</code>\n"
        f"• <b>Quiet Hours:</b> <code>22:00 - 07:00 EAT</code>\n"
        f"• <b>Radar Status:</b> {status_badge}"
    )

    kb = get_profile_actions_kb(candidate.is_active, candidate.min_match_score, lang=lang)

    if is_edit:
        await target_msg.edit_text(card_text, reply_markup=kb, parse_mode="HTML")
    else:
        await target_msg.answer(card_text, reply_markup=kb, parse_mode="HTML")


# -----------------------------------------------------------------
# 6. Job Matches Handler
# -----------------------------------------------------------------
@router.message(Command("jobs"))
@router.message(F.text.in_([
    "🎯 Job Matches", "🎯 የስራ እድሎች", "🎯 Carraa Hojii", "Job Matches", "Jobs"
]))
async def handle_job_matches_button(message: Message, lang: str):
    """Displays recent active matches or prompts radar status."""
    user_id = message.from_user.id
    async with async_session_factory() as session:
        cand_repo = CandidateRepository(session)
        candidate = await cand_repo.get_by_telegram_id(user_id)

        if not candidate:
            await message.answer("Please set up your profile with /start first.")
            return

        # Fetch candidate's matches
        stmt = (
            select(JobMatch)
            .where(JobMatch.candidate_id == candidate.id)
            .order_by(desc(JobMatch.sent_at))
            .limit(3)
        )
        res = await session.execute(stmt)
        matches = res.scalars().all()

    if not matches:
        empty_card = (
            "🎯 <b>Your Job Sniper Radar is Active!</b>\n\n"
            f"We are monitoring <b>31+ Ethiopian job channels</b> 24/7 for positions matching your qualifications.\n\n"
            f"• <b>Your Threshold:</b> <code>{candidate.min_match_score}% Match</code>\n"
            "• <b>Monitored Sources:</b> HaHuJobs, Ethiojobs, Awra Jobs, Josad Tech, Beleqet, Freelance ET, and 25+ more.\n\n"
            "As soon as a relevant vacancy appears, you'll receive an instant sniper alert right here with a 1-tap cover letter generator and mock interview coach!"
        )
        await message.answer(empty_card, parse_mode="HTML")
    else:
        await message.answer(f"🎯 <b>Here are your latest {len(matches)} matched vacancies:</b>", parse_mode="HTML")
        # Could show summary cards


# -----------------------------------------------------------------
# 7. Inline Actions Callbacks (Threshold, Toggle Active, Delete Data)
# -----------------------------------------------------------------
@router.callback_query(F.data == "settings:threshold")
async def open_threshold_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎯 <b>Select your Minimum Match Threshold:</b>\n\n"
        "Only jobs matching at or above this percentage will trigger instant Telegram alerts.\n\n"
        "• <b>70% - 75%:</b> Higher volume, broader opportunities.\n"
        "• <b>80% (Recommended):</b> Balanced, high-relevance feed.\n"
        "• <b>90% - 95%:</b> Ultra-strict exact qualification fit.",
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

    status_msg = "Radar Resumed! You will receive live alerts." if is_now_active else "Radar Paused. Alerts temporarily halted."
    await callback.answer(status_msg, show_alert=True)
    await show_profile_card(callback.from_user.id, callback.message, lang, i18n, is_edit=True)


@router.callback_query(F.data == "settings:back")
async def back_to_profile(callback: CallbackQuery, lang: str, i18n: I18nManager):
    await show_profile_card(callback.from_user.id, callback.message, lang, i18n, is_edit=True)


@router.callback_query(F.data == "settings:delete_confirm")
@router.message(Command("delete_data"))
async def prompt_delete_data(event: [Message, CallbackQuery]):
    warn_text = (
        "⚠️ <b>CONFIRM ACCOUNT & DATA PURGE</b>\n\n"
        "This will permanently delete:\n"
        "• Your CV & encrypted resume files\n"
        "• Your structured career profile & vector embeddings\n"
        "• All match alerts and tailored cover letters\n"
        "• All mock interview transcripts\n\n"
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
        "✅ <b>All your personal records, CVs, and data have been permanently purged.</b>\n\n"
        "Thank you for using JobSniper ET. You can start fresh anytime by sending /start.",
        parse_mode="HTML"
    )
    await callback.answer("Data purged.")
