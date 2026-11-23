"""Mock Interview Session Keyboards."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_interview_mode_kb(job_id: str = "general") -> InlineKeyboardMarkup:
    """Choose Text Mode or Voice Note Mode."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⌨️ Text Mode", callback_data=f"start_int:text:{job_id}"),
                InlineKeyboardButton(text="🎙️ Voice Note Mode", callback_data=f"start_int:voice:{job_id}"),
            ],
            [
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_action"),
            ]
        ]
    )


def get_interview_question_kb(question_num: int) -> InlineKeyboardMarkup:
    """Controls during active interview: skip question or end session."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏭️ Skip Question", callback_data=f"int_skip:{question_num}"),
                InlineKeyboardButton(text="🛑 End Session", callback_data="int_end"),
            ]
        ]
    )

