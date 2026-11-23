"""Central Telegram Bot Factory and Dispatcher Setup for JobSniper ET."""

import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
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
    """Creates configured Bot instance."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or token == "your_telegram_bot_token_here":
        # Safe dummy token for local build/testing if not yet supplied
        token = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
    
    return Bot(
        token=token,
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
    """Registers slash commands in Telegram client menu."""
    commands = [
        BotCommand(command="start", description="Launch JobSniper & configure profile"),
        BotCommand(command="profile", description="View profile, change match % & quiet hours"),
        BotCommand(command="interview", description="Practice 5-question STAR mock interview"),
        BotCommand(command="help", description="How JobSniper works & commands guide"),
        BotCommand(command="delete_data", description="Permanently delete all your personal data"),
    ]
    try:
        await bot.set_my_commands(commands)
    except Exception as e:
        logger.warning(f"Could not register Telegram bot commands: {e}")

