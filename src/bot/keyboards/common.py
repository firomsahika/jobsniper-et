"""Common & Afriwork-Inspired Keyboards for JobSniper ET."""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
)
from src.config.settings import settings


# -----------------------------------------------------------------
# 1. Main Navigation Reply Keyboard (Sleek 2x2 + Action Grid)
# -----------------------------------------------------------------
def get_main_menu_reply_kb(lang: str = "en") -> ReplyKeyboardMarkup:
    """Main persistent bottom navigation keyboard."""
    labels = {
        "en": (
            "🎯 Job Matches",
            "👤 Profile",
            "🎙️ Mock Interview",
            "⚙️ Settings",
        ),
        "am": (
            "🎯 የስራ እድሎች",
            "👤 የኔ ፕሮፋይል",
            "🎙️ ቃለ-መጠይቅ",
            "⚙️ ቅንብሮች",
        ),
        "om": (
            "🎯 Carraa Hojii",
            "👤 Pirofaayilii",
            "🎙️ Shaakala",
            "⚙️ Filannoowwan",
        ),
    }
    b1, b2, b3, b4 = labels.get(lang, labels["en"])

    rows = [
        [KeyboardButton(text=f"{b1}"), KeyboardButton(text=f"{b2}")],
        [KeyboardButton(text=f"{b3}"), KeyboardButton(text=f"{b4}")],
    ]

    # If Mini App URL is configured, add a 1-tap WebApp launcher button
    if settings.TELEGRAM_WEBAPP_URL:
        app_title = "📱 Open Mini App" if lang == "en" else ("📱 አፑን ክፈት" if lang == "am" else "📱 App Bani")
        rows.append([KeyboardButton(text=app_title, web_app=WebAppInfo(url=settings.TELEGRAM_WEBAPP_URL))])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
    )


# -----------------------------------------------------------------
# 2. Settings Sub-Menu Reply Keyboard (Matching Afriwork Design)
# -----------------------------------------------------------------
def get_settings_reply_kb(lang: str = "en") -> ReplyKeyboardMarkup:
    """Settings navigation keyboard matching Afriwork's structure."""
    labels = {
        "en": ("Language/ቋንቋ", "Profile", "Terms and Conditions", "Back"),
        "am": ("Language/ቋንቋ", "ፕሮፋይል", "ውሎች እና ደንቦች", "ተመለስ"),
        "om": ("Language/ቋንቋ", "Pirofaayilii", "Seeraa fi Dambiiwwan", "Deebi'i"),
    }
    lang_btn, prof_btn, terms_btn, back_btn = labels.get(lang, labels["en"])
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=lang_btn), KeyboardButton(text=prof_btn)],
            [KeyboardButton(text=terms_btn), KeyboardButton(text=back_btn)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# -----------------------------------------------------------------
# 3. Language Selection Keyboards
# -----------------------------------------------------------------
def get_language_inline_kb() -> InlineKeyboardMarkup:
    """Inline language picker."""
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


# -----------------------------------------------------------------
# 4. Onboarding Choice Keyboard
# -----------------------------------------------------------------
def get_onboarding_choice_kb(lang: str = "en") -> InlineKeyboardMarkup:
    """Prompt for CV file upload vs 5-step wizard."""
    labels = {
        "en": ("📎 Upload CV (PDF/Word)", "✍️ Guided 5-Step Builder (No CV)"),
        "am": ("📎 ሲቪ (CV) ይላኩ (PDF/Word)", "✍️ ያለ ሲቪ በቀላሉ ይመዝገቡ (5 ደረጃዎች)"),
        "om": ("📎 CV Ergaa (PDF/Word)", "✍️ CV Malee Galmaa'aa (Tarkaanfii 5)"),
    }
    cv_label, wiz_label = labels.get(lang, labels["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=cv_label, callback_data="onboard:upload_cv")],
            [InlineKeyboardButton(text=wiz_label, callback_data="onboard:wizard")],
        ]
    )


# -----------------------------------------------------------------
# 5. Cancel Keyboard
# -----------------------------------------------------------------
def get_cancel_kb(lang: str = "en") -> InlineKeyboardMarkup:
    text = "❌ Cancel" if lang == "en" else ("❌ ሰርዝ" if lang == "am" else "❌ Haqi")
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data="cancel_action")]]
    )
