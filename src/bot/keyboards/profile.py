"""Profile Management Keyboards."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_profile_actions_kb(is_active: bool, current_threshold: int, lang: str = "en") -> InlineKeyboardMarkup:
    toggle_txt = "⏸️ Pause Alerts" if is_active else "▶️ Resume Alerts"
    if lang == "am":
        toggle_txt = "⏸️ ማሳወቂያዎችን አቁም" if is_active else "▶️ ማሳወቂያዎችን አስጀምር"
    elif lang == "om":
        toggle_txt = "⏸️ Dhaabi" if is_active else "▶️ Eegali"

    threshold_txt = f"🎯 Min Match: {current_threshold}%"
    quiet_txt = "🌙 Quiet Hours (22:00-07:00)"
    del_txt = "🗑️ Delete All My Data"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=threshold_txt, callback_data="settings:threshold"),
                InlineKeyboardButton(text=quiet_txt, callback_data="settings:quiet_hours"),
            ],
            [
                InlineKeyboardButton(text=toggle_txt, callback_data="settings:toggle_active"),
            ],
            [
                InlineKeyboardButton(text=del_txt, callback_data="settings:delete_confirm"),
            ]
        ]
    )


def get_threshold_selection_kb() -> InlineKeyboardMarkup:
    """Inline choices for minimum match percentage."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="70%", callback_data="set_thresh:70"),
                InlineKeyboardButton(text="75%", callback_data="set_thresh:75"),
                InlineKeyboardButton(text="80% (Default)", callback_data="set_thresh:80"),
            ],
            [
                InlineKeyboardButton(text="85%", callback_data="set_thresh:85"),
                InlineKeyboardButton(text="90%", callback_data="set_thresh:90"),
                InlineKeyboardButton(text="95% (Strict)", callback_data="set_thresh:95"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Back", callback_data="settings:back"),
            ]
        ]
    )


def get_delete_confirmation_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚠️ YES, Purge Everything", callback_data="delete:confirm_yes"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="settings:back"),
            ]
        ]
    )

