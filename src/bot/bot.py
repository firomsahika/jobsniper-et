"""Central Telegram Bot Factory and Dispatcher Setup for JobSniper ET."""

import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand
from src.config.settings import settings
from src.bot.middlewares.i18n import I18nMiddleware
from src.bot.middlewares.throttling import ThrottlingMiddleware
from src.bot.handlers import start, onboarding, profile, alerts, cover_letter, interview, help

logger = logging.getLogger(__name__)


def create_bot() -> Bot:
    """Creates configured Bot instance with resilient network timeout settings."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or token == "your_telegram_bot_token_here":
        token = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"

    # Generous 60s client timeout for resilient operation on high-latency/slow network connections
    session = AiohttpSession(timeout=60.0)

    return Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )


async def create_dispatcher() -> Dispatcher:
    """Configures Dispatcher with FSM storage, middlewares, and routers."""
    try:
        storage = RedisStorage.from_url(settings.REDIS_URL)
    except Exception as e:
        logger.warning(f"Could not connect to Redis for FSM ({e}). Falling back to in-memory storage.")
        storage = MemoryStorage()

    dp = Dispatcher(storage=storage)

    # Register Middlewares
    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())
    dp.message.middleware(I18nMiddleware())
    dp.callback_query.middleware(I18nMiddleware())

    # Register Routers
    dp.include_router(start.router)
    dp.include_router(onboarding.router)
    dp.include_router(profile.router)
    dp.include_router(alerts.router)
    dp.include_router(cover_letter.router)
    dp.include_router(interview.router)
    dp.include_router(help.router)

    return dp


async def setup_bot_commands(bot: Bot):
    """Registers bot description, short description, and slash commands in Telegram."""
    commands = [
        BotCommand(command="start", description="Launch JobSniper & configure profile"),
        BotCommand(command="profile", description="View profile, match threshold & settings"),
        BotCommand(command="interview", description="Practice 5-question STAR mock interview"),
        BotCommand(command="help", description="How JobSniper works & commands guide"),
        BotCommand(command="delete_data", description="Permanently delete all your personal data"),
    ]
    try:
        await bot.set_my_commands(commands)

        bot_description = (
            "🎯 Welcome to JobSniper ET — Ethiopia's Premier AI Career Radar & Mock Interview Coach!\n\n"
            "⚡ Why JobSniper ET?\n"
            "Finding a job in Ethiopia shouldn't mean scrolling through dozens of Telegram channels every day. JobSniper ET continuously monitors 31+ top Ethiopian channels 24/7 so you never miss an opportunity.\n\n"
            "🚀 How It Works:\n"
            "1️⃣ Upload your CV or enter your skills in 4 simple steps.\n"
            "2️⃣ AI continuously analyzes new vacancies from 31+ channels.\n"
            "3️⃣ Receive instant alerts only for roles matching 80%+ with your exact qualifications.\n"
            "4️⃣ Generate 1-tap tailored cover letters.\n"
            "5️⃣ Practice 5-question STAR mock interviews with instant voice or text feedback.\n\n"
            "🔒 100% Free & AES-256-GCM Encrypted.\n\n"
            "Tap 'Start' below to activate your personal job radar!"
        )
        await bot.set_my_description(description=bot_description)
        await bot.set_my_short_description(short_description="AI Job Matcher & STAR Mock Interview Coach for 31+ Ethiopian channels. 100% Free.")
    except Exception as e:
        logger.warning(f"Note on Telegram bot descriptions/commands: {e}")

