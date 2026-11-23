"""Common Keyboards (Main Menu, Language Selection)."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def get_language_inline_kb() -> InlineKeyboardMarkup:
    """Language selection keyboard for first-time launch."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
                InlineKeyboardButton(text="🇪🇹 አማርኛ (Amharic)", callback_data="lang:am"),
            ],
            [
                InlineKeyboardButton(text="🌳 Afaan Oromoo", callback_data="lang:om"),
            ]
        ]
    )


def get_onboarding_choice_kb(lang: str = "en") -> InlineKeyboardMarkup:
    """Prompt for CV file upload vs 4-step wizard."""
    labels = {
        "en": ("📎 Upload CV (PDF/Word)", "✍️ Guided 4-Step Builder"),
        "am": ("📎 ሲቪ (CV) ይላኩ (PDF/Word)", "✍️ ያለ ሲቪ በቀላሉ ይመዝገቡ"),
        "om": ("📎 CV Ergaa (PDF/Word)", "✍️ CV Malee Galmaa'aa"),
    }
    cv_label, wiz_label = labels.get(lang, labels["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=cv_label, callback_data="onboard:upload_cv")],
            [InlineKeyboardButton(text=wiz_label, callback_data="onboard:wizard")],
        ]
    )


def get_main_menu_reply_kb(lang: str = "en") -> ReplyKeyboardMarkup:
    """Persistent bottom quick-action menu."""
    labels = {
        "en": ("👤 My Profile", "🎙️ Mock Interview", "⚙️ Preferences", "ℹ️ Help"),
        "am": ("👤 የኔ መረጃ", "🎙️ ቃለ መጠይቅ", "⚙️ ምርጫዎች", "ℹ️ እገዛ"),
        "om": ("👤 Profile Koo", "🎙️ Shaakala", "⚙️ Filannoo", "ℹ️ Gargaarsa"),
    }
    b1, b2, b3, b4 = labels.get(lang, labels["en"])
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=b1), KeyboardButton(text=b2)],
            [KeyboardButton(text=b3), KeyboardButton(text=b4)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def get_cancel_kb(lang: str = "en") -> InlineKeyboardMarkup:
    text = "❌ Cancel" if lang == "en" else ("❌ ሰርዝ" if lang == "am" else "❌ Haqi")
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data="cancel_action")]]
    )

