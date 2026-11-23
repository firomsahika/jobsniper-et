"""Candidate Onboarding Handler (CV Upload + 4-Step Interactive Wizard)."""

import io
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, Document
from aiogram.fsm.context import FSMContext
from src.bot.states.onboarding import OnboardingStates
from src.bot.keyboards.common import get_main_menu_reply_kb, get_cancel_kb
from src.bot.middlewares.i18n import I18nManager
from src.core.document_parser import document_parser
from src.core.gemini import gemini_service
from src.db.session import async_session_factory
from src.db.repositories.candidate_repo import CandidateRepository

logger = logging.getLogger(__name__)
router = Router()


# -----------------------------------------------------------------
# Path A: CV File Upload (PDF / Word)
# -----------------------------------------------------------------
@router.callback_query(F.data == "onboard:upload_cv")
async def trigger_cv_upload(callback: CallbackQuery, state: FSMContext, lang: str, i18n: I18nManager):
    await state.set_state(OnboardingStates.waiting_for_cv)
    instructions = i18n.get("upload_cv_instructions", lang=lang)
    await callback.message.edit_text(instructions, reply_markup=get_cancel_kb(lang), parse_mode="HTML")
    await callback.answer()


@router.message(OnboardingStates.waiting_for_cv, F.document)
async def process_cv_document(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    doc: Document = message.document
    file_name = doc.file_name or "resume.pdf"
    file_size = doc.file_size or 0

    if file_size > 10 * 1024 * 1024:
        await message.answer("⚠️ File size exceeds 10MB limit. Please upload a smaller PDF or DOCX file.")
        return

    # Send processing progress message
    proc_msg = await message.answer(i18n.get("cv_processing", lang=lang), parse_mode="HTML")

    try:
        # Download document into memory
        file_io = io.BytesIO()
        await message.bot.download(doc, destination=file_io)
        file_bytes = file_io.getvalue()

        # 1. Extract text from PDF / DOCX
        raw_text = document_parser.extract_from_bytes(file_bytes, file_name)
        if not raw_text or len(raw_text.strip()) < 50:
            await proc_msg.edit_text(i18n.get("cv_error", lang=lang), parse_mode="HTML")
            return

        # 2. Extract structured profile via Gemini
        structured = await gemini_service.parse_cv_text(raw_text)

        # 3. Generate 768-dim vector embedding
        embedding = await gemini_service.get_embedding(raw_text)

        # 4. Save to Database with AES-256-GCM encryption
        user_id = message.from_user.id
        name = structured.get("full_name") or message.from_user.full_name or "Applicant"

        async with async_session_factory() as session:
            repo = CandidateRepository(session)
            candidate = await repo.create_or_update(
                telegram_id=user_id,
                full_name=name,
                ui_language=lang,
                raw_cv_text=raw_text,
                structured_profile=structured,
                cv_embedding=embedding,
            )

        await state.clear()

        # 5. Success confirmation
        skills_str = ", ".join(structured.get("skills", [])[:5])
        success_card = i18n.get(
            "cv_success",
            lang=lang,
            name=name,
            title=structured.get("primary_title", "Professional"),
            education=structured.get("highest_education", "Higher Education"),
            experience=structured.get("years_of_experience", 0),
            skills=skills_str,
            threshold=candidate.min_match_score,
        )

        await proc_msg.delete()
        await message.answer(
            success_card,
            reply_markup=get_main_menu_reply_kb(lang=lang),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error handling CV upload: {e}", exc_info=True)
        await proc_msg.edit_text(
            "⚠️ An error occurred while parsing your document. Please try again or use the Guided Builder.",
            parse_mode="HTML"
        )


# -----------------------------------------------------------------
# Path B: Guided 4-Step Builder (For Fresh Grads & Non-CV Users)
# -----------------------------------------------------------------
@router.callback_query(F.data == "onboard:wizard")
async def start_wizard(callback: CallbackQuery, state: FSMContext, lang: str, i18n: I18nManager):
    await state.set_state(OnboardingStates.wizard_education)
    prompt = i18n.get("wizard_step1", lang=lang)
    await callback.message.edit_text(prompt, reply_markup=get_cancel_kb(lang), parse_mode="HTML")
    await callback.answer()


@router.message(OnboardingStates.wizard_education)
async def wizard_step1_education(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    await state.update_data(education=message.text.strip())
    await state.set_state(OnboardingStates.wizard_experience)
    await message.answer(i18n.get("wizard_step2", lang=lang), parse_mode="HTML")


@router.message(OnboardingStates.wizard_experience)
async def wizard_step2_experience(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    await state.update_data(experience=message.text.strip())
    await state.set_state(OnboardingStates.wizard_skills)
    await message.answer(i18n.get("wizard_step3", lang=lang), parse_mode="HTML")


@router.message(OnboardingStates.wizard_skills)
async def wizard_step3_skills(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    await state.update_data(skills=message.text.strip())
    await state.set_state(OnboardingStates.wizard_preferences)
    await message.answer(i18n.get("wizard_step4", lang=lang), parse_mode="HTML")


@router.message(OnboardingStates.wizard_preferences)
async def wizard_step4_preferences(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    data = await state.get_data()
    preferences = message.text.strip()
    education = data.get("education", "")
    experience_text = data.get("experience", "")
    skills_text = data.get("skills", "")

    # Build normalized profile representation
    raw_synth_cv = (
        f"Education: {education}\n"
        f"Professional Experience: {experience_text}\n"
        f"Skills: {skills_text}\n"
        f"Work Preferences: {preferences}"
    )

    proc = await message.answer("⏳ <b>Synthesizing your profile...</b>", parse_mode="HTML")

    structured = await gemini_service.parse_cv_text(raw_synth_cv)
    embedding = await gemini_service.get_embedding(raw_synth_cv)

    user_id = message.from_user.id
    name = message.from_user.full_name or "Applicant"

    async with async_session_factory() as session:
        repo = CandidateRepository(session)
        candidate = await repo.create_or_update(
            telegram_id=user_id,
            full_name=name,
            ui_language=lang,
            raw_cv_text=raw_synth_cv,
            structured_profile=structured,
            cv_embedding=embedding,
        )

    await state.clear()
    await proc.delete()

    skills_str = ", ".join(structured.get("skills", [])[:5])
    success_card = i18n.get(
        "cv_success",
        lang=lang,
        name=name,
        title=structured.get("primary_title", "Professional"),
        education=education,
        experience=structured.get("years_of_experience", 0),
        skills=skills_str,
        threshold=candidate.min_match_score,
    )

    await message.answer(
        success_card,
        reply_markup=get_main_menu_reply_kb(lang=lang),
        parse_mode="HTML"
    )

