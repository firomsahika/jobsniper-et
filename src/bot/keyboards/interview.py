"""Mock Interview Session Keyboards."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.bot.middlewares.i18n import i18n


def get_interview_mode_kb(job_id: str = "general", lang: str = "en") -> InlineKeyboardMarkup:
    """Choose Text Mode or Voice Note Mode."""
    cancel_lbl = "❌ Cancel" if lang == "en" else ("❌ ሰርዝ" if lang == "am" else "❌ Haqi")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=i18n.get("btn_mode_text", lang=lang), callback_data=f"start_int:text:{job_id}"),
                InlineKeyboardButton(text=i18n.get("btn_mode_voice", lang=lang), callback_data=f"start_int:voice:{job_id}"),
            ],
            [
                InlineKeyboardButton(text=cancel_lbl, callback_data="cancel_action"),
            ]
        ]
    )


def get_interview_question_kb(question_num: int, lang: str = "en") -> InlineKeyboardMarkup:
    """Controls during active interview: skip question or end session."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=i18n.get("btn_skip_q", lang=lang), callback_data=f"int_skip:{question_num}"),
                InlineKeyboardButton(text=i18n.get("btn_end_int", lang=lang), callback_data="int_end"),
            ]
        ]
    )

