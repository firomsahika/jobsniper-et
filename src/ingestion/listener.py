"""Telethon MTProto Channel Listener for Ethiopian Job Channels.

Monitors 50+ channels 24/7 with FloodWait error recovery and reconnection management.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, ChannelPrivateError
from src.config.settings import settings
from src.db.session import async_session_factory
from src.ingestion.channels import get_monitored_channel_handles
from src.ingestion.parser import IngestionPipeline

logger = logging.getLogger(__name__)


class ChannelListener:
    def __init__(self):
        self.api_id = settings.TELEGRAM_API_ID
        self.api_hash = settings.TELEGRAM_API_HASH
        self.session_name = settings.TELEGRAM_SESSION_NAME
        self.client: Optional[TelegramClient] = None
        self.monitored_channels = get_monitored_channel_handles()

    def is_configured(self) -> bool:
        return bool(self.api_id and self.api_hash)

    async def start(self):
        """Starts the Telethon MTProto client listener."""
        if not self.is_configured():
            logger.warning(
                "TELEGRAM_API_ID or TELEGRAM_API_HASH not set. MTProto listener running in idle/simulation mode."
            )
            return

        logger.info(f"Connecting Telethon client for session '{self.session_name}'...")
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        await self.client.start()
        logger.info("Telethon client connected successfully!")

        # Register event handler for incoming channel messages
        @self.client.on(events.NewMessage(chats=self.monitored_channels))
        async def handle_new_post(event):
            try:
                chat = await event.get_chat()
                channel_username = getattr(chat, "username", str(event.chat_id))
                raw_text = event.raw_text or ""
                message_id = event.id
                posted_at = event.date or datetime.now(timezone.utc)

                logger.info(f"Incoming post from @{channel_username} (msg_id: {message_id})")

                # Process in database session
                async with async_session_factory() as session:
                    pipeline = IngestionPipeline(session)
                    await pipeline.process_incoming_post(
                        source_channel=f"@{channel_username}",
                        message_id=message_id,
                        raw_text=raw_text,
                        posted_at=posted_at
                    )
            except FloodWaitError as e:
                logger.warning(f"Telegram FloodWait encountered: sleeping for {e.seconds} seconds.")
                await asyncio.sleep(e.seconds + 2)
            except Exception as e:
                logger.error(f"Error handling channel event: {e}", exc_info=True)

        logger.info(f"Listening to {len(self.monitored_channels)} channels...")
        await self.client.run_until_disconnected()


channel_listener = ChannelListener()

