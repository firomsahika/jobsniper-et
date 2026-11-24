"""Main Application Entrypoint for JobSniper ET.

Supports running:
--service bot         : Telegram Bot service (aiogram v3)
--service ingestion   : Channel listener & Ingestion Engine (Telethon)
--service dashboard   : Web Admin Dashboard & Telemetry UI (FastAPI)
--service all         : Runs Bot + Channel Ingestion + Dashboard concurrently
"""

import argparse
import asyncio
import logging
import os
import sys
import uvicorn
from src.config.settings import settings
from src.bot.bot import create_bot, create_dispatcher, setup_bot_commands
from src.ingestion.listener import channel_listener
from src.dashboard.app import dashboard_app

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("jobsniper")


async def run_bot():
    """Runs the Telegram Bot via Long Polling."""
    logger.info("Initializing JobSniper ET Telegram Bot...")
    bot = create_bot()
    dp = await create_dispatcher()

    try:
        await setup_bot_commands(bot)
        from src.queue.dispatcher import run_alert_scheduler
        scheduler_task = asyncio.create_task(run_alert_scheduler(bot))
        logger.info("Starting bot polling loop...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            polling_timeout=20,
        )
    finally:
        if 'scheduler_task' in locals():
            scheduler_task.cancel()
        await bot.session.close()


async def run_ingestion():
    """Runs the Telethon MTProto Channel Listener."""
    logger.info("Initializing JobSniper ET Channel Ingestion Listener...")
    await channel_listener.start()


async def run_dashboard():
    """Runs the FastAPI Admin Dashboard & Telemetry API."""
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    logger.info(f"Starting JobSniper ET Dashboard on http://localhost:{port}...")
    config = uvicorn.Config(dashboard_app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def run_all():
    """Runs Bot, Ingestion, and Dashboard concurrently."""
    logger.info("Starting Telegram Bot, Ingestion Worker, and Dashboard concurrently...")
    await asyncio.gather(
        run_bot(),
        run_ingestion(),
        run_dashboard(),
        return_exceptions=True
    )


def main():
    parser = argparse.ArgumentParser(description="JobSniper ET - AI Job Matcher & Mock Interview Coach")
    parser.add_argument(
        "--service",
        type=str,
        default="bot",
        choices=["bot", "ingestion", "dashboard", "all"],
        help="Service to launch: 'bot', 'ingestion', 'dashboard', or 'all'",
    )
    args = parser.parse_args()

    logger.info(f"Launching service: {args.service} in environment: {settings.ENVIRONMENT}")

    try:
        if args.service == "bot":
            asyncio.run(run_bot())
        elif args.service == "ingestion":
            asyncio.run(run_ingestion())
        elif args.service == "dashboard":
            asyncio.run(run_dashboard())
        elif args.service == "all":
            asyncio.run(run_all())
    except (KeyboardInterrupt, SystemExit):
        logger.info("JobSniper ET terminated gracefully.")


if __name__ == "__main__":
    main()
