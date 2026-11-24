"""AI Mock Interview & Communication Coach Handler (STAR Framework)."""

import io
import logging
from uuid import UUID
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, Voice
from aiogram.fsm.context import FSMContext
from src.bot.states.interview import InterviewStates
from src.bot.keyboards.interview import get_interview_mode_kb, get_interview_question_kb
from src.bot.middlewares.i18n import I18nManager
from src.core.gemini import gemini_service
from src.db.session import async_session_factory
from src.db.repositories.candidate_repo import CandidateRepository
from src.db.repositories.job_repo import JobRepository
from src.db.repositories.match_repo import InterviewRepository

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("interview"))
@router.message(F.text.in_([
    "🎙️ Mock Interview", "Mock Interview", "🎙️ ቃለ-መጠይቅ", "🎙️ ቃለ መጠይቅ",
    "ቃለ-መጠይቅ", "ቃለ መጠይቅ", "🎙️ Shaakala", "Shaakala"
]))
@router.callback_query(F.data.startswith("mockint:"))
async def prompt_interview_mode(event: [Message, CallbackQuery], lang: str, i18n: I18nManager):
    """Initiates interview: shows overview and prompts text vs voice mode."""
    job_id_str = "general"
    if isinstance(event, CallbackQuery):
        parts = event.data.split(":")
        if len(parts) > 1:
            job_id_str = parts[1]

    # Find context title
    job_title = "Senior Professional"
    company = "Target Organization"

    if job_id_str != "general":
        try:
            async with async_session_factory() as session:
                job_repo = JobRepository(session)
                job = await job_repo.get_by_id(UUID(job_id_str))
                if job:
                    job_title = job.title
                    company = job.company
        except Exception:
            pass

    intro_text = i18n.get("interview_intro", lang=lang, title=job_title, company=company)
    kb = get_interview_mode_kb(job_id=job_id_str, lang=lang)

    if isinstance(event, CallbackQuery):
        await event.message.answer(intro_text, reply_markup=kb, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(intro_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("start_int:"))
async def start_interview_simulation(callback: CallbackQuery, state: FSMContext, lang: str, i18n: I18nManager):
    parts = callback.data.split(":")
    mode = parts[1]  # "text" or "voice"
    job_id_str = parts[2] if len(parts) > 2 else "general"

    job_title = "Senior Professional"
    company = "Target Employer"
    job_uuid = None

    if job_id_str != "general":
        try:
            job_uuid = UUID(job_id_str)
            async with async_session_factory() as session:
                job_repo = JobRepository(session)
                job = await job_repo.get_by_id(job_uuid)
                if job:
                    job_title = job.title
                    company = job.company
        except Exception:
            pass

    user_id = callback.from_user.id
    async with async_session_factory() as session:
        cand_repo = CandidateRepository(session)
        int_repo = InterviewRepository(session)
        candidate = await cand_repo.get_by_telegram_id(user_id)
        if not candidate:
            await callback.message.edit_text(i18n.get("profile_not_found", lang=lang))
            return

        # Create session in DB
        interview_session = await int_repo.create_session(
            candidate_id=candidate.id,
            job_id=job_uuid,
            job_context=f"Role: {job_title} at {company}",
            mode=mode,
        )

    # Initialize FSM data
    await state.set_state(InterviewStates.waiting_for_answer)
    await state.update_data(
        session_id=str(interview_session.id),
        mode=mode,
        job_title=job_title,
        company=company,
        current_q=1,
        qa_history=[],
    )

    mode_display = i18n.get("btn_mode_text" if mode == "text" else "btn_mode_voice", lang=lang)
    start_banner = i18n.get("interview_started", lang=lang, mode_text=mode_display)
    await callback.message.edit_text(start_banner, parse_mode="HTML")

    # Present Question 1
    await ask_current_question(callback.message, state, lang, i18n)
    await callback.answer()


async def ask_current_question(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    data = await state.get_data()
    q_num = data.get("current_q", 1)
    job_title = data.get("job_title", "Professional")
    company = data.get("company", "Employer")
    mode = data.get("mode", "text")

    question_content = gemini_service.get_interview_question_prompt(q_num, job_title, company)
    mode_hint = i18n.get("interview_text_hint" if mode == "text" else "interview_voice_hint", lang=lang)

    q_card = i18n.get(
        "interview_q_header",
        lang=lang,
        num=q_num,
        question=question_content,
        mode_instruction=mode_hint
    )

    await state.update_data(current_question_text=question_content)
    await message.answer(q_card, reply_markup=get_interview_question_kb(q_num, lang=lang), parse_mode="HTML")


@router.message(InterviewStates.waiting_for_answer, F.voice)
@router.message(InterviewStates.waiting_for_answer, F.text)
async def handle_interview_answer(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    data = await state.get_data()
    mode = data.get("mode", "text")
    q_num = data.get("current_q", 1)
    q_text = data.get("current_question_text", "")
    job_title = data.get("job_title", "Professional")
    session_id_str = data.get("session_id")
    qa_history = data.get("qa_history", [])

    eval_msg = await message.answer(i18n.get("interview_evaluating", lang=lang), parse_mode="HTML")

    # Extract user answer text
    if message.voice:
        # Voice note mode
        voice: Voice = message.voice
        if voice.duration > 120:
            await eval_msg.edit_text(i18n.get("interview_voice_too_long", lang=lang))
            return

        voice_io = io.BytesIO()
        await message.bot.download(voice, destination=voice_io)
        voice_bytes = voice_io.getvalue()

        # Transcribe via Gemini
        user_answer = await gemini_service.transcribe_audio_voice_note(voice_bytes)
    else:
        user_answer = message.text.strip()

    # Evaluate with Gemini
    evaluation = await gemini_service.evaluate_interview_answer(
        question_num=q_num,
        question_text=q_text,
        user_answer=user_answer,
        job_title=job_title,
    )

    score = evaluation.get("score", 7.5)
    feedback = evaluation.get("quick_feedback", "Solid response.")
    star_rating = evaluation.get("star_rating", "Adequate")

    # Save turn in DB
    turn_record = {
        "question_num": q_num,
        "question": q_text,
        "answer": user_answer,
        "score": score,
        "feedback": feedback,
        "star_rating": star_rating,
    }
    qa_history.append(turn_record)

    if session_id_str:
        try:
            async with async_session_factory() as session:
                repo = InterviewRepository(session)
                await repo.append_transcript_turn(UUID(session_id_str), turn_record)
        except Exception as e:
            logger.error(f"Error saving interview turn: {e}")

    # Send instant per-question score card
    turn_feedback = i18n.get(
        "interview_turn_feedback",
        lang=lang,
        num=q_num,
        score=score,
        star_rating=star_rating,
        feedback=feedback,
    )
    await eval_msg.edit_text(turn_feedback, parse_mode="HTML")

    # Check if more questions remain
    if q_num < 5:
        await state.update_data(current_q=q_num + 1, qa_history=qa_history)
        await ask_current_question(message, state, lang, i18n)
    else:
        # Complete simulation! Generate comprehensive final performance report
        await finish_interview_session(message, state, lang, i18n)


@router.callback_query(F.data.startswith("int_skip:"))
async def skip_interview_question(callback: CallbackQuery, state: FSMContext, lang: str, i18n: I18nManager):
    data = await state.get_data()
    q_num = data.get("current_q", 1)
    qa_history = data.get("qa_history", [])

    qa_history.append({
        "question_num": q_num,
        "question": data.get("current_question_text", ""),
        "answer": "[Skipped by candidate]",
        "score": 0.0,
        "feedback": "Candidate skipped this question.",
    })

    await callback.answer(i18n.get("interview_skipped_ack", lang=lang))
    if q_num < 5:
        await state.update_data(current_q=q_num + 1, qa_history=qa_history)
        await ask_current_question(callback.message, state, lang, i18n)
    else:
        await finish_interview_session(callback.message, state, lang, i18n)


@router.callback_query(F.data == "int_end")
async def end_interview_early(callback: CallbackQuery, state: FSMContext, lang: str, i18n: I18nManager):
    await callback.answer(i18n.get("interview_ended_ack", lang=lang))
    await finish_interview_session(callback.message, state, lang, i18n)


async def finish_interview_session(message: Message, state: FSMContext, lang: str, i18n: I18nManager):
    data = await state.get_data()
    qa_history = data.get("qa_history", [])
    job_title = data.get("job_title", "Professional")
    session_id_str = data.get("session_id")

    final_report = await gemini_service.generate_final_interview_report(job_title, qa_history)

    final_score = final_report.get("overall_score", 8.0)
    tech_score = final_report.get("tech_score", 8.0)
    star_score = final_report.get("star_score", 7.5)
    comm_score = final_report.get("comm_score", 8.5)

    if session_id_str:
        try:
            async with async_session_factory() as session:
                repo = InterviewRepository(session)
                await repo.complete_session(UUID(session_id_str), final_score)
        except Exception as e:
            logger.error(f"Error completing session in DB: {e}")

    await state.clear()

    summary_text = i18n.get(
        "interview_completed",
        lang=lang,
        score=final_score,
        tech_score=tech_score,
        star_score=star_score,
        comm_score=comm_score,
        feedback=final_report.get("feedback", "Excellent preparation."),
        recommendation=final_report.get("recommendation", "Continue practicing concrete metrics."),
    )

    await message.answer(summary_text, parse_mode="HTML")

