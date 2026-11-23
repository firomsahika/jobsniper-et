"""Handler for Help, Commands & System Status."""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from src.bot.middlewares.i18n import I18nManager

router = Router()


@router.message(Command("help"))
@router.message(F.text.in_(["ℹ️ Help", "Help", "help", "ℹ️ እገዛ", "እገዛ", "ℹ️ Gargaarsa", "Gargaarsa"]))
async def show_help(message: Message, lang: str, i18n: I18nManager):
    help_card = (
        "📖 <b>JobSniper ET — User Guide & Commands</b>\n\n"
        "<b>Available Commands:</b>\n"
        "• /start — Set up or view your account and choose your language.\n"
        "• /profile — View your structured CV profile and match settings.\n"
        "• /interview — Launch the 5-question STAR AI mock interview coach (Text or Voice).\n"
        "• /delete_data — Permanently purge all your data and CV records.\n"
        "• /help — Display this help manual.\n\n"
        "🎯 <b>How Sniper Matching Works:</b>\n"
        "1. We continuously monitor 50+ Ethiopian Telegram channels 24/7.\n"
        "2. When a new job appears, our deduplication engine filters out cross-posts.\n"
        "3. A 2-stage hybrid AI matcher compares the job against your skills.\n"
        "4. If alignment reaches 80%+ (or your custom threshold), you receive an instant alert card with tailor-made application tools.\n\n"
        "🔒 <b>Privacy & Security:</b>\n"
        "All uploaded resumes are encrypted with bank-grade AES-256-GCM. We never share your data with third parties."
    )
    await message.answer(help_card, parse_mode="HTML")

