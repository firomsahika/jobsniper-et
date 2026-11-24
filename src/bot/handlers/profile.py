"""Handler for Afriwork-Style Navigation: Settings, Account, Terms, and Job Matches."""

import logging
from datetime import time
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.bot.keyboards.common import (
    get_main_menu_reply_kb,
    get_settings_reply_kb,
    get_language_inline_kb,
)
from src.bot.keyboards.profile import (
    get_profile_actions_kb,
    get_threshold_selection_kb,
    get_alert_timing_kb,
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
async def handle_settings_menu(message: Message, lang: str, i18n: I18nManager):
    """Displays settings overview card and switches bottom keyboard to Settings mode."""
    settings_text = i18n.get("settings_overview", lang=lang)
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
        "🌐 <b>Select your preferred language / እባክዎ ቋንቋ ይምረጡ / Afaan filadhaa:</b>",
        reply_markup=get_language_inline_kb(),
        parse_mode="HTML"
    )


# -----------------------------------------------------------------
# 3. Terms and Conditions Handler
# -----------------------------------------------------------------
@router.message(Command("terms"))
@router.message(F.text.in_([
    "Terms and Conditions", "Terms and conditions", "Terms",
    "ውሎች እና ደንቦች", "Seeraa fi Dambiiwwan"
]))
async def handle_terms_and_conditions(message: Message, lang: str, i18n: I18nManager):
    terms_text = i18n.get("terms_and_conditions", lang=lang)
    await message.answer(terms_text, parse_mode="HTML")


# -----------------------------------------------------------------
# 4. Back Button Handler (Returns to Main Menu Keyboard)
# -----------------------------------------------------------------
@router.message(F.text.in_(["Back", "back", "🔙 Back", "ተመለስ", "Deebi'i"]))
async def handle_back_button(message: Message, lang: str, i18n: I18nManager):
    """Returns smoothly to the primary navigation grid."""
    await message.answer(
        i18n.get("main_menu_prompt", lang=lang),
        reply_markup=get_main_menu_reply_kb(lang=lang),
        parse_mode="HTML"
    )


# -----------------------------------------------------------------
# 5. Account / Profile Handler (Afriwork-Inspired Staying Updated Banner)
# -----------------------------------------------------------------
@router.message(Command("profile"))
@router.message(Command("account"))
@router.message(F.text.in_([
    "Profile", "profile", "👤 Profile", "👤 My Profile", "👤 የኔ ፕሮፋይል",
    "👤 የኔ አካውንት", "👤 የኔ መረጃ", "👤 Pirofaayilii", "👤 Profile Koo",
    "Account", "account", "👤 Account", "👤 Account Koo", "ፕሮፋይል", "Pirofaayilii"
]))
async def view_account_handler(message: Message, lang: str, i18n: I18nManager):
    user_id = message.from_user.id
    async with async_session_factory() as session:
        repo = CandidateRepository(session)
        candidate = await repo.get_by_telegram_id(user_id)

    if not candidate:
        await message.answer(i18n.get("profile_not_found", lang=lang))
        return

    # Afriwork-style motivational callout
    banner_text = i18n.get("profile_staying_updated", lang=lang)
    await message.answer(banner_text, parse_mode="HTML")

    # Send detailed profile card
    await show_profile_card(user_id, message, lang, i18n, is_edit=False)


async def show_profile_card(user_id: int, target_msg: Message, lang: str, i18n: I18nManager, is_edit: bool = False):
    async with async_session_factory() as session:
        repo = CandidateRepository(session)
        candidate = await repo.get_by_telegram_id(user_id)

    if not candidate:
        text = i18n.get("profile_not_found", lang=lang)
        if is_edit:
            await target_msg.edit_text(text)
        else:
            await target_msg.answer(text)
        return

    profile = candidate.structured_profile or {}
    skills_list = profile.get("skills", [])
    skills_str = ", ".join(skills_list) if skills_list else "General Professional"
    status_badge = i18n.get("status_active" if candidate.is_active else "status_paused", lang=lang)

    mode = getattr(candidate, "notification_mode", "quiet_standard") or "quiet_standard"
    timing_map = {
        "en": {
            "instant": "⚡ 24/7 Instant (Any Time)",
            "quiet_standard": "🌙 Quiet Hours (22:00 - 07:00 EAT)",
            "quiet_extended": "🌙 Extended Quiet (21:00 - 08:00 EAT)",
            "work_hours": "💼 Work Hours (08:30 - 18:00 EAT)",
            "digest_morning": "☕ Daily Morning Digest (08:30 EAT)",
            "digest_evening": "🌆 Daily Evening Digest (18:30 EAT)",
        },
        "am": {
            "instant": "⚡ 24/7 ፈጣን (በማንኛውም ሰዓት)",
            "quiet_standard": "🌙 መደበኛ ጸጥታ (22:00 - 07:00 EAT)",
            "quiet_extended": "🌙 ረጅም ጸጥታ (21:00 - 08:00 EAT)",
            "work_hours": "💼 የስራ ሰዓት ብቻ (08:30 - 18:00 EAT)",
            "digest_morning": "☕ የጠዋት ማጠቃለያ (08:30 EAT)",
            "digest_evening": "🌆 የማታ ማጠቃለያ (18:30 EAT)",
        },
        "om": {
            "instant": "⚡ 24/7 Battalatti (Yeroo Hundaa)",
            "quiet_standard": "🌙 Cal-dhaha (22:00 - 07:00 EAT)",
            "quiet_extended": "🌙 Cal-dhaha Dheeraa (21:00 - 08:00 EAT)",
            "work_hours": "💼 Sa'aatii Hojii Qofa (08:30 - 18:00 EAT)",
            "digest_morning": "☕ Cuunfaa Ganamaa (08:30 EAT)",
            "digest_evening": "🌆 Cuunfaa Galgalaa (18:30 EAT)",
        },
    }
    lang_timings = timing_map.get(lang, timing_map["en"])
    timing_display = lang_timings.get(mode, lang_timings["quiet_standard"])

    card_text = i18n.get(
        "profile_card",
        lang=lang,
        name=candidate.full_name,
        title=profile.get("primary_title", "Specialist"),
        education=profile.get("highest_education", "Higher Education"),
        experience=profile.get("years_of_experience", 0),
        skills=skills_str,
        threshold=candidate.min_match_score,
        timing=timing_display,
        status_badge=status_badge,
    )

    kb = get_profile_actions_kb(
        candidate.is_active,
        candidate.min_match_score,
        notification_mode=mode,
        lang=lang
    )

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
async def handle_job_matches_button(message: Message, lang: str, i18n: I18nManager):
    """Displays recent active matches or prompts radar status."""
    user_id = message.from_user.id
    async with async_session_factory() as session:
        cand_repo = CandidateRepository(session)
        candidate = await cand_repo.get_by_telegram_id(user_id)

        if not candidate:
            await message.answer(i18n.get("profile_not_found", lang=lang))
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
        empty_card = i18n.get("matches_empty", lang=lang, threshold=candidate.min_match_score)
        await message.answer(empty_card, parse_mode="HTML")
    else:
        from sqlalchemy.orm import selectinload
        from src.ingestion.web_scraper import get_channel_display_name, build_telegram_post_url
        
        # Load jobs with matches
        stmt_full = (
            select(JobMatch)
            .options(selectinload(JobMatch.job))
            .where(JobMatch.candidate_id == candidate.id)
            .order_by(desc(JobMatch.sent_at))
            .limit(5)
        )
        res_full = await session.execute(stmt_full)
        full_matches = res_full.scalars().all()

        await message.answer(i18n.get("matches_header", lang=lang, count=len(full_matches)), parse_mode="HTML")

        for m in full_matches:
            job = m.job
            if not job:
                continue
            post_url = build_telegram_post_url(job.source_channel, job.source_message_id, job.structured_data)
            ch_name = get_channel_display_name(job.source_channel)
            strengths = "\n".join(f"• {s}" for s in (m.match_reasoning or [])[:2]) if m.match_reasoning else "• Strong qualification alignment."
            structured_info = job.structured_data or {}
            job_type = structured_info.get("employment_type", "Full-time")
            req_skills = structured_info.get("required_skills", [])
            skills_display = ", ".join(req_skills[:8]) if req_skills else "Engineering & Technical Skills"
            salary = structured_info.get("salary_range", "Negotiable")
            exp_years = structured_info.get("required_experience_years")
            exp_display = f"{exp_years}+ years" if exp_years else "Open / Fresh Graduate"

            card = i18n.get(
                "match_card",
                lang=lang,
                title=job.title,
                company=job.company,
                job_type=job_type,
                location=job.location,
                exp_display=exp_display,
                skills_display=skills_display,
                deadline=job.deadline or "Open",
                salary=salary,
                score=m.match_score,
                strengths=strengths,
                post_url=post_url,
                ch_name=ch_name,
            )

            apply_btn_txt = i18n.get("btn_view_original", lang=lang)
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text=apply_btn_txt, url=post_url),
                    ],
                    [
                        InlineKeyboardButton(text=i18n.get("btn_generate_cover", lang=lang), callback_data=f"cvletter:{job.id}"),
                        InlineKeyboardButton(text=i18n.get("btn_mock_interview", lang=lang), callback_data=f"mockint:{job.id}"),
                    ]
                ]
            )
            await message.answer(card, reply_markup=kb, parse_mode="HTML")


# -----------------------------------------------------------------
# 7. Profile Update Choice Callback (Upload CV vs Enter Manually)
# -----------------------------------------------------------------
@router.callback_query(F.data == "profile:update_choice")
async def handle_profile_update_choice(callback: CallbackQuery, lang: str):
    """Presents user with a choice to either upload a CV file or enter details manually."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📎 Upload Resume / CV (PDF/DOCX)" if lang == "en" else ("📎 ሲቪ (PDF/DOCX) ይላኩ" if lang == "am" else "📎 CV Ergaa (PDF/DOCX)"),
                callback_data="onboard:upload_cv"
            )],
            [InlineKeyboardButton(
                text="✍️ Enter Details Manually" if lang == "en" else ("✍️ በራስዎ ሞልተው ያስመዝግቡ" if lang == "am" else "✍️ Ofiin Guutaa"),
                callback_data="onboard:wizard"
            )],
            [InlineKeyboardButton(
                text="❌ Cancel" if lang == "en" else ("❌ ሰርዝ" if lang == "am" else "❌ Haqi"),
                callback_data="cancel_action"
            )],
        ]
    )
    prompt_text = (
        "<b>✏️ Update Your Career Profile</b>\n\n"
        "How would you like to update your qualifications and career details?\n\n"
        "• <b>Upload Resume / CV:</b> Upload a PDF or Word document to parse your skills automatically.\n"
        "• <b>Enter Details Manually:</b> Fill in your role, education, experience, and skills directly in 5 simple steps."
    )
    if lang == "am":
        prompt_text = (
            "<b>✏️ የሥራ መረጃዎን (Profile) ያዘምኑ</b>\n\n"
            "መረጃዎን እንዴት ማዘመን ይፈልጋሉ?\n\n"
            "• <b>ሲቪ (CV) በመላክ:</b> የ PDF ወይም DOCX ፋይል በመላክ መረጃዎን በቀጥታ ያስመዝግቡ።\n"
            "• <b>በራስዎ በመሙላት:</b> ሙያዎን፣ ትምህርትዎን፣ ልምድዎን እና ክህሎቶችዎን በ 5 ቀላል ደረጃዎች ይሙሉ።"
        )
    elif lang == "om":
        prompt_text = (
            "<b>✏️ Profile Hojii Keessanii Haaromsaa</b>\n\n"
            "Odeeffannoo keessan akkamitti haaromsuu barbaaddu?\n\n"
            "• <b>CV Erguun:</b> Faayilii PDF ykn DOCX erguun ofumaan akka guutamu gochuu.\n"
            "• <b>Ofiin Guutuun:</b> Ogummaa, barnoota, muuxannoo fi dandeettii keessan tarkaanfii 5n guutuu."
        )

    await callback.message.edit_text(prompt_text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# -----------------------------------------------------------------
# 7. Inline Actions Callbacks (Threshold, Toggle Active, Delete Data)
# -----------------------------------------------------------------
@router.callback_query(F.data == "settings:threshold")
async def open_threshold_menu(callback: CallbackQuery, lang: str, i18n: I18nManager):
    await callback.message.edit_text(
        i18n.get("threshold_menu", lang=lang),
        reply_markup=get_threshold_selection_kb(lang=lang),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_thresh:"))
async def save_threshold(callback: CallbackQuery, lang: str, i18n: I18nManager):
    new_thresh = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        repo = CandidateRepository(session)
        await repo.update_threshold(callback.from_user.id, new_thresh)

    await callback.answer(i18n.get("threshold_updated", lang=lang, threshold=new_thresh))
    await show_profile_card(callback.from_user.id, callback.message, lang, i18n, is_edit=True)


# -----------------------------------------------------------------
# Alert Delivery Timing / Quiet Hours Callbacks
# -----------------------------------------------------------------
@router.callback_query(F.data == "settings:quiet_hours")
async def open_alert_timing_menu(callback: CallbackQuery, lang: str):
    """Presents interactive alert delivery timing selection."""
    user_id = callback.from_user.id
    async with async_session_factory() as session:
        repo = CandidateRepository(session)
        candidate = await repo.get_by_telegram_id(user_id)
        current_mode = getattr(candidate, "notification_mode", "quiet_standard") or "quiet_standard"

    desc = (
        "🔔 <b>Select Your Preferred Alert Delivery Timing:</b>\n\n"
        "Customize when and how often you want to receive job notifications:\n\n"
        "• <b>⚡ 24/7 Instant:</b> Immediate alerts for every match, day or night.\n"
        "• <b>🌙 Standard Quiet (22:00 - 07:00):</b> Real-time during the day, silent at night.\n"
        "• <b>🌙 Extended Quiet (21:00 - 08:00):</b> Early evening to morning quiet period.\n"
        "• <b>💼 Work Hours Only:</b> Alerts delivered only during business hours (08:30 - 18:00).\n"
        "• <b>☕ Morning Digest:</b> Consolidated summary of all matches delivered daily at 08:30 EAT.\n"
        "• <b>🌆 Evening Digest:</b> Consolidated summary of all matches delivered daily at 18:30 EAT."
    )
    if lang == "am":
        desc = (
            "🔔 <b>የማሳወቂያ ሰዓት እና አቀባበል ምርጫ:</b>\n\n"
            "የስራ እድሎች ማሳወቂያ መቼ እና እንዴት እንዲደርስዎት ይፈልጋሉ?\n\n"
            "• <b>⚡ 24/7 ፈጣን:</b> በማንኛውም ሰዓት አዲስ ስራ ሲወጣ ወዲያውኑ ማሳወቂያ ይደርሳል።\n"
            "• <b>🌙 መደበኛ ጸጥታ:</b> በቀን ፈጣን ማሳወቂያ፣ በሌሊት (ከምሽቱ 10 - ጠዋት 1 ሰዓት) ጸጥታ።\n"
            "• <b>🌙 ረጅም ጸጥታ:</b> ከምሽቱ 9:00 እስከ ጠዋት 2:00 ጸጥታ።\n"
            "• <b>💼 የስራ ሰዓት ብቻ:</b> በስራ ሰዓት ብቻ (2:30 - 12:00) ማሳወቂያዎች ይላካሉ።\n"
            "• <b>☕ የጠዋት ማጠቃለያ:</b> በየቀኑ ጠዋት 2:30 ላይ የተጣጣሙ ስራዎች በአንድ ላይ ይላካሉ።\n"
            "• <b>🌆 የማታ ማጠቃለያ:</b> በየቀኑ ማታ 12:30 ላይ የተጣጣሙ ስራዎች በአንድ ላይ ይላካሉ።"
        )
    elif lang == "om":
        desc = (
            "🔔 <b>Yeroo fi Haala Beeksisa Hojii Filadhaa:</b>\n\n"
            "Beeksisni carraa hojii yoom akka isin ga'u barbaaddu?\n\n"
            "• <b>⚡ 24/7 Battalatti:</b> Yeroo kamiyyuu battalumatti akka isin ga'u.\n"
            "• <b>🌙 Cal-dhaha:</b> Guyyaa battalatti, halkan (22:00 - 07:00) sagalee malee.\n"
            "• <b>🌙 Cal-dhaha Dheeraa:</b> 21:00 hanga 08:00tti sagalee malee.\n"
            "• <b>💼 Sa'aatii Hojii Qofa:</b> Sa'aatii hojii qofa (08:30 - 18:00) keessatti.\n"
            "• <b>☕ Cuunfaa Ganamaa:</b> Guyyaa hundumaa ganama 08:30tti walitti qabamee.\n"
            "• <b>🌆 Cuunfaa Galgalaa:</b> Guyyaa hundumaa galgala 18:30tti walitti qabamee."
        )

    await callback.message.edit_text(
        desc,
        reply_markup=get_alert_timing_kb(current_mode=current_mode, lang=lang),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("timing:"))
async def save_alert_timing(callback: CallbackQuery, lang: str, i18n: I18nManager):
    """Saves candidate's alert delivery timing preference."""
    mode = callback.data.split(":")[1]
    user_id = callback.from_user.id

    time_map = {
        "instant": (time(0, 0), time(0, 0)),
        "quiet_standard": (time(22, 0), time(7, 0)),
        "quiet_extended": (time(21, 0), time(8, 0)),
        "work_hours": (time(18, 0), time(8, 30)),
        "digest_morning": (time(22, 0), time(7, 0)),
        "digest_evening": (time(22, 0), time(7, 0)),
    }
    start_t, end_t = time_map.get(mode, (time(22, 0), time(7, 0)))

    async with async_session_factory() as session:
        repo = CandidateRepository(session)
        await repo.update_notification_mode(user_id, mode=mode, start_t=start_t, end_t=end_t)

    ack = "Alert delivery timing updated!"
    if lang == "am":
        ack = "የማሳወቂያ ሰዓት ተስተካክሏል!"
    elif lang == "om":
        ack = "Yeroon beeksisaa haaromfameera!"
    await callback.answer(ack)
    await show_profile_card(user_id, callback.message, lang, i18n, is_edit=True)


@router.callback_query(F.data == "settings:toggle_active")
async def toggle_active_status(callback: CallbackQuery, lang: str, i18n: I18nManager):
    async with async_session_factory() as session:
        repo = CandidateRepository(session)
        is_now_active = await repo.toggle_active(callback.from_user.id)

    status_msg = i18n.get("radar_resumed" if is_now_active else "radar_paused", lang=lang)
    await callback.answer(status_msg, show_alert=True)
    await show_profile_card(callback.from_user.id, callback.message, lang, i18n, is_edit=True)


@router.callback_query(F.data == "settings:back")
async def back_to_profile(callback: CallbackQuery, lang: str, i18n: I18nManager):
    await show_profile_card(callback.from_user.id, callback.message, lang, i18n, is_edit=True)


@router.callback_query(F.data == "settings:delete_confirm")
@router.message(Command("delete_data"))
async def prompt_delete_data(event: [Message, CallbackQuery], lang: str, i18n: I18nManager):
    warn_text = i18n.get("delete_confirm_prompt", lang=lang)
    kb = get_delete_confirmation_kb(lang=lang)
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(warn_text, reply_markup=kb, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(warn_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "delete:confirm_yes")
async def execute_data_deletion(callback: CallbackQuery, lang: str, i18n: I18nManager):
    async with async_session_factory() as session:
        repo = CandidateRepository(session)
        await repo.delete_all_candidate_data(callback.from_user.id)

    await callback.message.edit_text(
        i18n.get("delete_success", lang=lang),
        parse_mode="HTML"
    )
    await callback.answer("Data purged.")
