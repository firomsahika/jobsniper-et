"""Handler for 1-Tap Tailored Cover Letter Generator."""

import html
import logging
from uuid import UUID
from aiogram import Router, F
from aiogram.types import CallbackQuery
from src.bot.middlewares.i18n import I18nManager
from src.core.gemini import gemini_service
from src.db.session import async_session_factory
from src.db.repositories.candidate_repo import CandidateRepository
from src.db.repositories.job_repo import JobRepository
from src.db.repositories.match_repo import MatchRepository

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("cvletter:"))
async def handle_generate_cover_letter(callback: CallbackQuery, lang: str, i18n: I18nManager):
    parts = callback.data.split(":")
    job_id_str = parts[1]
    match_id_str = parts[2] if len(parts) > 2 else None

    await callback.answer("Drafting your personalized cover letter...")
    status_msg = await callback.message.reply(i18n.get("cover_letter_generating", lang=lang), parse_mode="HTML")

    try:
        job_id = UUID(job_id_str)
        async with async_session_factory() as session:
            cand_repo = CandidateRepository(session)
            job_repo = JobRepository(session)
            match_repo = MatchRepository(session)

            candidate = await cand_repo.get_by_telegram_id(callback.from_user.id)
            job = await job_repo.get_by_id(job_id)

            if not candidate or not job:
                await status_msg.edit_text("⚠️ Could not locate job or candidate profile.")
                return

            job_context_data = dict(job.structured_data or {})
            job_context_data["title"] = job.title
            job_context_data["company"] = job.company
            job_context_data["location"] = job.location
            job_context_data["deadline"] = job.deadline
            job_context_data["raw_text"] = job.raw_text

            # Generate high-converting 3-paragraph draft
            cover_letter = await gemini_service.generate_cover_letter(
                candidate_name=candidate.full_name,
                candidate_profile=candidate.structured_profile or {},
                job_data=job_context_data
            )

            # Save draft in match table
            if match_id_str:
                try:
                    await match_repo.save_cover_letter(UUID(match_id_str), cover_letter)
                except Exception:
                    pass

        # Escape html chars inside the code block
        safe_letter = html.escape(cover_letter)
        ready_text = (
            f"📄 <b>Tailored Cover Letter for {html.escape(job.company)}</b>\n"
            f"🎯 <b>Role:</b> {html.escape(job.title)}\n\n"
            f"<code>{safe_letter}</code>\n\n"
            f"💡 <i>Tap the text above to copy it instantly to your clipboard!</i>"
        )
        if lang == "am":
            ready_text = (
                f"📄 <b>ለ{html.escape(job.company)} የተዘጋጀ የማመልከቻ ደብዳቤ</b>\n"
                f"🎯 <b>የስራ መደብ:</b> {html.escape(job.title)}\n\n"
                f"<code>{safe_letter}</code>\n\n"
                f"💡 <i>ጽሑፉን በመጫን ኮፒ አድርገው ማመልከት ይችላሉ!</i>"
            )
        elif lang == "om":
            ready_text = (
                f"📄 <b>Xalayaa Iyyannoo {html.escape(job.company)}f Qophaa'e</b>\n"
                f"🎯 <b>Hojii:</b> {html.escape(job.title)}\n\n"
                f"<code>{safe_letter}</code>\n\n"
                f"💡 <i>Barreeffamicha tuquun koppii godhaa fayyadamaa!</i>"
            )

        await status_msg.edit_text(ready_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error generating cover letter: {e}", exc_info=True)
        await status_msg.edit_text("⚠️ Failed to generate cover letter. Please try again.")

