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
        # First-time user: Offer language selection
        welcome_txt = (
            f"🎯 <b>Welcome to JobSniper ET!</b>\n"
            f"ሰላም! Baga nagaan dhuftan!\n\n"
            f"The premier AI-powered Career Sniper & Mock Interview Coach for Ethiopia.\n\n"
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

    await callback.answer()
    
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

