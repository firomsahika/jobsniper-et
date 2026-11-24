"""Profile & Account Management Keyboards (Afriwork-Inspired)."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from src.config.settings import settings


def get_profile_actions_kb(
    is_active: bool,
    current_threshold: int,
    notification_mode: str = "quiet_standard",
    lang: str = "en"
) -> InlineKeyboardMarkup:
    """Action buttons for candidate account overview card."""
    toggle_txt = "⏸️ Pause Alerts" if is_active else "▶️ Resume Alerts"
    if lang == "am":
        toggle_txt = "⏸️ ማሳወቂያ አቁም" if is_active else "▶️ አስጀምር"
    elif lang == "om":
        toggle_txt = "⏸️ Dhaabi" if is_active else "▶️ Eegali"

    threshold_txt = f"🎯 Min: {current_threshold}%"
    
    # Mode-specific label
    timing_labels = {
        "instant": ("⚡ Instant (24/7)", "⚡ ፈጣን (24/7)", "⚡ Battalatti (24/7)"),
        "quiet_standard": ("🌙 Quiet (22-07)", "🌙 ጸጥታ (22-07)", "🌙 Cal-dhaha (22-07)"),
        "quiet_extended": ("🌙 Quiet (21-08)", "🌙 ጸጥታ (21-08)", "🌙 Cal-dhaha (21-08)"),
        "work_hours": ("💼 Work Hours", "💼 የስራ ሰዓት", "💼 Sa'aatii Hojii"),
        "digest_morning": ("☕ Morning Digest", "☕ የጠዋት ማጠቃለያ", "☕ Ganama"),
        "digest_evening": ("🌆 Evening Digest", "🌆 የማታ ማጠቃለያ", "🌆 Galgala"),
    }
    lbl_idx = 0 if lang == "en" else (1 if lang == "am" else 2)
    timing_txt = timing_labels.get(notification_mode, timing_labels["quiet_standard"])[lbl_idx]

    update_cv_txt = "✏️ Update Profile / CV"
    if lang == "am":
        update_cv_txt = "✏️ ፕሮፋይል / ሲቪ አዘምን"
    elif lang == "om":
        update_cv_txt = "✏️ Profile Haaromsi"

    del_txt = "🗑️ Delete Account Data"
    if lang == "am":
        del_txt = "🗑️ መረጃዬን አጥፋ"
    elif lang == "om":
        del_txt = "🗑️ Odeeffannoo Haqaa"

    rows = []

    # If Telegram Mini App URL is set, add Afriwork-style "View Profile" WebApp button at the top
    if settings.TELEGRAM_WEBAPP_URL:
        rows.append([
            InlineKeyboardButton(text="View Profile 🗖", web_app=WebAppInfo(url=settings.TELEGRAM_WEBAPP_URL))
        ])

    rows.extend([
        [
            InlineKeyboardButton(text=threshold_txt, callback_data="settings:threshold"),
            InlineKeyboardButton(text=timing_txt, callback_data="settings:quiet_hours"),
        ],
        [
            InlineKeyboardButton(text=update_cv_txt, callback_data="profile:update_choice"),
            InlineKeyboardButton(text=toggle_txt, callback_data="settings:toggle_active"),
        ],
        [
            InlineKeyboardButton(text=del_txt, callback_data="settings:delete_confirm"),
        ]
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_alert_timing_kb(current_mode: str = "quiet_standard", lang: str = "en") -> InlineKeyboardMarkup:
    """Inline choices for alert timing, quiet hours, and digest delivery."""
    def mark(mode_name: str, label: str) -> str:
        return f"✅ {label}" if current_mode == mode_name else label

    if lang == "am":
        options = [
            ("timing:instant", mark("instant", "⚡ 24/7 ፈጣን (በማንኛውም ሰዓት)")),
            ("timing:quiet_standard", mark("quiet_standard", "🌙 መደበኛ ጸጥታ (ከምሽቱ 10 - ጠዋት 1 ሰዓት)")),
            ("timing:quiet_extended", mark("quiet_extended", "🌙 ረጅም ጸጥታ (ከምሽቱ 9 - ጠዋት 2 ሰዓት)")),
            ("timing:work_hours", mark("work_hours", "💼 የስራ ሰዓት ብቻ (2:30 - 12:00)")),
            ("timing:digest_morning", mark("digest_morning", "☕ የጠዋት ማጠቃለያ (በየቀኑ 2:30)")),
            ("timing:digest_evening", mark("digest_evening", "🌆 የማታ ማጠቃለያ (በየቀኑ 12:30)")),
        ]
        back_txt = "⬅️ ወደ ፕሮፋይል ተመለስ"
    elif lang == "om":
        options = [
            ("timing:instant", mark("instant", "⚡ 24/7 Battalatti (Yeroo Hundaa)")),
            ("timing:quiet_standard", mark("quiet_standard", "🌙 Cal-dhaha (22:00 - 07:00 EAT)")),
            ("timing:quiet_extended", mark("quiet_extended", "🌙 Cal-dhaha Dheeraa (21:00 - 08:00)")),
            ("timing:work_hours", mark("work_hours", "💼 Sa'aatii Hojii Qofa (08:30 - 18:00)")),
            ("timing:digest_morning", mark("digest_morning", "☕ Cuunfaa Ganamaa (08:30 EAT)")),
            ("timing:digest_evening", mark("digest_evening", "🌆 Cuunfaa Galgalaa (18:30 EAT)")),
        ]
        back_txt = "⬅️ Gara Pirofaayiliitti"
    else:
        options = [
            ("timing:instant", mark("instant", "⚡ 24/7 Instant (Immediate Alerts)")),
            ("timing:quiet_standard", mark("quiet_standard", "🌙 Standard Quiet (22:00 - 07:00 EAT)")),
            ("timing:quiet_extended", mark("quiet_extended", "🌙 Extended Quiet (21:00 - 08:00 EAT)")),
            ("timing:work_hours", mark("work_hours", "💼 Work Hours Only (08:30 - 18:00 EAT)")),
            ("timing:digest_morning", mark("digest_morning", "☕ Morning Digest (Daily 08:30 EAT)")),
            ("timing:digest_evening", mark("digest_evening", "🌆 Evening Digest (Daily 18:30 EAT)")),
        ]
        back_txt = "⬅️ Back to Profile"

    keyboard_rows = [[InlineKeyboardButton(text=label, callback_data=code)] for code, label in options]
    keyboard_rows.append([InlineKeyboardButton(text=back_txt, callback_data="settings:back")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


def get_threshold_selection_kb(lang: str = "en") -> InlineKeyboardMarkup:
    """Inline choices for minimum match percentage."""
    rec_lbl = "80% (Recommended)" if lang == "en" else ("80% (የሚመከር)" if lang == "am" else "80% (Kan Gorfamu)")
    strict_lbl = "95% (Strict)" if lang == "en" else ("95% (ጥብቅ)" if lang == "am" else "95% (Cimaa)")
    back_lbl = "⬅️ Back to Profile" if lang == "en" else ("⬅️ ወደ ፕሮፋይል ተመለስ" if lang == "am" else "⬅️ Gara Pirofaayiliitti")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="70%", callback_data="set_thresh:70"),
                InlineKeyboardButton(text="75%", callback_data="set_thresh:75"),
                InlineKeyboardButton(text=rec_lbl, callback_data="set_thresh:80"),
            ],
            [
                InlineKeyboardButton(text="85%", callback_data="set_thresh:85"),
                InlineKeyboardButton(text="90%", callback_data="set_thresh:90"),
                InlineKeyboardButton(text=strict_lbl, callback_data="set_thresh:95"),
            ],
            [
                InlineKeyboardButton(text=back_lbl, callback_data="settings:back"),
            ]
        ]
    )


def get_delete_confirmation_kb(lang: str = "en") -> InlineKeyboardMarkup:
    yes_lbl = "⚠️ YES, Purge Everything" if lang == "en" else ("⚠️ አዎ፣ ሁሉንም አጥፋ" if lang == "am" else "⚠️ EEYYEE, Hunda Haqi")
    cancel_lbl = "❌ Cancel" if lang == "en" else ("❌ ሰርዝ" if lang == "am" else "❌ Haqi")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=yes_lbl, callback_data="delete:confirm_yes"),
                InlineKeyboardButton(text=cancel_lbl, callback_data="settings:back"),
            ]
        ]
    )
