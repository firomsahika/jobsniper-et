"""Candidate Onboarding Handler (CV Upload + 4-Step Interactive Wizard)."""

import io
import logging
import re
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery, Document, InlineKeyboardMarkup, InlineKeyboardButton
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
        await message.answer(i18n.get("cv_too_large", lang=lang))
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

        # 2. Extract structured profile (AI + Local Heuristic Extraction)
        user_name = message.from_user.full_name or message.from_user.first_name or "Applicant"
        structured = await gemini_service.parse_cv_text(raw_text, file_name=file_name, user_full_name=user_name)

        # 3. Generate 768-dim vector embedding
        embedding = await gemini_service.get_embedding(raw_text)

        # 4. Save to Database with AES-256-GCM encryption
        user_id = message.from_user.id
        name = structured.get("full_name") or user_name

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
        skills_list = structured.get("skills", [])
        skills_str = ", ".join(skills_list) if skills_list else "Communication, Problem Solving"
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
            i18n.get("cv_parse_failed", lang=lang),
            parse_mode="HTML"
        )


@router.message(OnboardingStates.waiting_for_cv, F.text)
async def handle_text_in_cv_upload(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    """Handles text sent while the bot is waiting for a CV document (e.g. user wants manual entry)."""
    text = (message.text or "").strip().lower()

    # If user asks to fill manually or without a file
    manual_keywords = ["fill", "myself", "manual", "without", "no cv", "not uploading", "change", "write", "typing", "form"]
    if any(k in text for k in manual_keywords):
        await state.set_state(OnboardingStates.wizard_title)
        prompt = i18n.get("wizard_step1", lang=lang)
        intro = (
            "✍️ <b>Guided Profile Setup</b>\n\n"
            "No problem! You can enter your qualifications directly in 5 simple steps.\n\n"
        )
        if lang == "am":
            intro = "✍️ <b>በራስዎ ሞልተው ያስመዝግቡ</b>\n\nምንም ችግር የለም! መረጃዎን በ 5 ቀላል ደረጃዎች በቀጥታ መሙላት ይችላሉ።\n\n"
        elif lang == "om":
            intro = "✍️ <b>Profile Ofiin Guutuu</b>\n\nRakkoon hin jiru! Odeeffannoo keessan tarkaanfii 5 salphaa ta'een guutuu dandeessu.\n\n"
        await message.answer(f"{intro}{prompt}", reply_markup=get_cancel_kb(lang), parse_mode="HTML")
        return

    # If user asks to cancel
    if any(c in text for c in ["cancel", "ሰርዝ", "haqi", "exit", "quit", "back", "ተመለስ"]):
        await state.clear()
        await message.answer(i18n.get("action_cancelled", lang=lang), reply_markup=get_main_menu_reply_kb(lang=lang))
        return

    # Otherwise explain document format and offer 1-tap button to switch to manual builder
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✍️ Enter Details Manually" if lang == "en" else ("✍️ በራስዎ ሞልተው ያስመዝግቡ" if lang == "am" else "✍️ Ofiin Guutaa"),
                callback_data="onboard:wizard"
            )],
            [InlineKeyboardButton(
                text="❌ Cancel" if lang == "en" else ("❌ ሰርዝ" if lang == "am" else "❌ Haqi"),
                callback_data="cancel_action"
            )]
        ]
    )
    guide_text = (
        "📎 <b>Resume / CV Document Required</b>\n\n"
        "Please upload your CV as a <b>file attachment</b> (PDF or DOCX format, up to 10MB).\n\n"
        "💡 <i>Prefer to enter your information manually without a file?</i> Tap <b>✍️ Enter Details Manually</b> below."
    )
    if lang == "am":
        guide_text = (
            "📎 <b>የሲቪ (CV) ፋይል ያስፈልጋል</b>\n\n"
            "እባክዎ ሲቪዎን በ PDF ወይም DOCX ፎርማት እንደ ፋይል አባሪ ይላኩ።\n\n"
            "💡 <i>ያለ ፋይል በራስዎ መሙላት ይፈልጋሉ?</i> ከታች <b>✍️ በራስዎ ሞልተው ያስመዝግቡ</b> የሚለውን ይጫኑ።"
        )
    elif lang == "om":
        guide_text = (
            "📎 <b>Faayiliin CV Barbaachisaadha</b>\n\n"
            "Maaloo CV keessan faayilii PDF ykn DOCX ta'een ergaa.\n\n"
            "💡 <i>Faayilii malee ofiin guutuu barbaadduu?</i> As tuquun <b>✍️ Ofiin Guutaa</b> kan jedhu filadhaa."
        )
    await message.answer(guide_text, reply_markup=kb, parse_mode="HTML")


# -----------------------------------------------------------------
# Path B: Guided 5-Step Builder (For Fresh Grads & Manual Entry)
# -----------------------------------------------------------------
@router.message(
    StateFilter("*"),
    F.text.ilike("%fill%myself%") | F.text.ilike("%by%myself%") | F.text.ilike("%manual%") | F.text.ilike("%without%cv%") | F.text.ilike("%not%uploading%")
)
async def trigger_manual_wizard_by_text(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    """Allows user to enter the manual profile wizard directly via conversational text."""
    await state.set_state(OnboardingStates.wizard_title)
    prompt = i18n.get("wizard_step1", lang=lang)
    await message.answer(prompt, reply_markup=get_cancel_kb(lang), parse_mode="HTML")


@router.callback_query(F.data == "onboard:wizard")
async def start_wizard(callback: CallbackQuery, state: FSMContext, lang: str, i18n: I18nManager):
    await state.set_state(OnboardingStates.wizard_title)
    prompt = i18n.get("wizard_step1", lang=lang)
    await callback.message.edit_text(prompt, reply_markup=get_cancel_kb(lang), parse_mode="HTML")
    await callback.answer()


@router.message(OnboardingStates.wizard_title)
async def wizard_step1_title(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(OnboardingStates.wizard_education)
    await message.answer(i18n.get("wizard_step2", lang=lang), parse_mode="HTML")


@router.message(OnboardingStates.wizard_education)
async def wizard_step2_education(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    await state.update_data(education=message.text.strip())
    await state.set_state(OnboardingStates.wizard_experience)
    await message.answer(i18n.get("wizard_step3", lang=lang), parse_mode="HTML")


@router.message(OnboardingStates.wizard_experience)
async def wizard_step3_experience(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    await state.update_data(experience=message.text.strip())
    await state.set_state(OnboardingStates.wizard_skills)
    await message.answer(i18n.get("wizard_step4", lang=lang), parse_mode="HTML")


@router.message(OnboardingStates.wizard_skills)
async def wizard_step4_skills(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    await state.update_data(skills=message.text.strip())
    await state.set_state(OnboardingStates.wizard_preferences)
    await message.answer(i18n.get("wizard_step5", lang=lang), parse_mode="HTML")


@router.message(OnboardingStates.wizard_preferences)
async def wizard_step5_preferences(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    data = await state.get_data()
    preferences = message.text.strip()
    title = data.get("title", "").strip() or "Specialist"
    education = data.get("education", "").strip()
    experience_text = data.get("experience", "").strip()
    skills_text = data.get("skills", "").strip()

    # Build normalized profile representation with explicit Title
    raw_synth_cv = (
        f"Target Role / Professional Title: {title}\n"
        f"Education & Field of Study: {education}\n"
        f"Professional Experience: {experience_text}\n"
        f"Core Skills: {skills_text}\n"
        f"Work Preferences: {preferences}"
    )

    proc = await message.answer(i18n.get("synthesizing_profile", lang=lang), parse_mode="HTML")

    user_id = message.from_user.id
    name = message.from_user.full_name or message.from_user.first_name or "Applicant"

    structured = await gemini_service.parse_cv_text(raw_synth_cv, user_full_name=name)
    embedding = await gemini_service.get_embedding(raw_synth_cv)

    # Ensure manual fields directly override generic defaults
    years_int = 0
    if experience_text:
        match_y = re.search(r'\d+', experience_text)
        if match_y:
            years_int = int(match_y.group())
    
    parsed_skills = [s.strip() for s in skills_text.split(",") if s.strip()]
    if parsed_skills:
        structured["skills"] = parsed_skills
    if education:
        structured["highest_education"] = education
    if years_int > 0:
        structured["years_of_experience"] = years_int
    structured["primary_title"] = title
    structured["full_name"] = name
    structured["preferred_roles"] = [title, f"Senior {title}", f"{title} Specialist"]
    structured["summary"] = f"{name} is a {title} with {years_int} years of experience specializing in {', '.join(parsed_skills[:3])}."

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
        title=title,
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

