"""Handler for Help, Commands & System Status."""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from src.bot.middlewares.i18n import I18nManager

router = Router()


@router.message(Command("help"))
@router.message(F.text.in_(["ℹ️ Help", "Help", "help", "ℹ️ እገዛ", "እገዛ", "ℹ️ Gargaarsa", "Gargaarsa"]))
async def show_help(message: Message, lang: str, i18n: I18nManager):
    help_card = i18n.get("help_guide", lang=lang)
    await message.answer(help_card, parse_mode="HTML")

