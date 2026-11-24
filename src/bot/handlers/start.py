"""Handler for /start and Language Selection."""

import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from src.bot.keyboards.common import (
    get_language_inline_kb,
    get_onboarding_choice_kb,
    get_main_menu_reply_kb,
)
from src.bot.middlewares.i18n import I18nManager
from src.db.session import async_session_factory
from src.db.repositories.candidate_repo import CandidateRepository

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    """Entrypoint: Checks candidate registration or prompts language selection."""
    await state.clear()
    user_id = message.from_user.id
    name = message.from_user.first_name or "Applicant"

    async with async_session_factory() as session:
        repo = CandidateRepository(session)
        candidate = await repo.get_by_telegram_id(user_id)

    if not candidate:
        # First-time user: Display informative overview and offer language selection
        welcome_txt = (
            f"🎯 <b>Welcome to JobSniper ET!</b>\n"
            f"ሰላም! Baga nagaan dhuftan!\n\n"
            f"⚡ <b>What is JobSniper ET?</b>\n"
            f"Your personal AI-powered Career Radar & Mock Interview Coach for the Ethiopian job market.\n\n"
            f"🎯 <b>Why Use It?</b>\n"
            f"Never miss a high-match vacancy again! We monitor <b>31+ Ethiopian job channels</b> 24/7 and alert you only when a job matches 80%+ of your exact qualifications.\n\n"
            f"🚀 <b>How It Works:</b>\n"
            f"1️⃣ <b>Build Profile:</b> Send your CV or fill your skills manually.\n"
            f"2️⃣ <b>Sniper Alerts:</b> Instant notifications as soon as a matching vacancy is posted.\n"
            f"3️⃣ <b>1-Tap Cover Letters:</b> Tailored 3-paragraph drafts ready to send.\n"
            f"4️⃣ <b>STAR Mock Interviews:</b> Practice with AI via voice notes or text.\n\n"
            f"🌐 <b>Please choose your preferred language / እባክዎ ቋንቋ ይምረጡ:</b>"
        )
        await message.answer(welcome_txt, reply_markup=get_language_inline_kb(), parse_mode="HTML")
    else:
        # Existing user: Display welcome back dashboard
        welcome = i18n.get("welcome_body", lang=candidate.ui_language, name=name)
        await message.answer(
            f"🎯 <b>JobSniper ET</b>\n\n{welcome}",
            reply_markup=get_main_menu_reply_kb(lang=candidate.ui_language),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("lang:"))
async def handle_language_choice(callback: CallbackQuery, state: FSMContext, i18n: I18nManager):
    """Processes user language selection."""
    selected_lang = callback.data.split(":")[1]
    user_id = callback.from_user.id
    name = callback.from_user.first_name or "Applicant"

    async with async_session_factory() as session:
        repo = CandidateRepository(session)
        candidate = await repo.get_by_telegram_id(user_id)
        if candidate:
            await repo.update_language(user_id, selected_lang)
        else:
            await repo.create_or_update(
                telegram_id=user_id,
                full_name=name,
                ui_language=selected_lang,
            )

    has_profile = bool(candidate and candidate.structured_profile)

    await callback.answer(f"Language updated!")

    if has_profile:
        lang_names = {"en": "English", "am": "አማርኛ", "om": "Afaan Oromoo"}
        confirm_text = f"✅ <b>Language switched to {lang_names.get(selected_lang, selected_lang)}!</b>\n\nYour preferences and notifications will now appear in your selected language."
        await callback.message.edit_text(confirm_text, parse_mode="HTML")
        await callback.message.answer(
            "📋 <b>Main Menu</b>\n\nSelect an option below to continue:",
            reply_markup=get_main_menu_reply_kb(lang=selected_lang),
            parse_mode="HTML"
        )
    else:
        welcome = i18n.get("welcome_body", lang=selected_lang, name=name)
        onboard_prompt = i18n.get("onboarding_prompt", lang=selected_lang)

        await callback.message.edit_text(
            f"{i18n.get('welcome_title', lang=selected_lang)}\n\n{welcome}\n\n{onboard_prompt}",
            reply_markup=get_onboarding_choice_kb(lang=selected_lang),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "cancel_action")
async def handle_cancel(callback: CallbackQuery, state: FSMContext, lang: str, i18n: I18nManager):
    await state.clear()
    await callback.answer("Cancelled")
    await callback.message.delete()

