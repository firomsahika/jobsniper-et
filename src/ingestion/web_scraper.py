"""Web-based HTTP Scraper for Public Ethiopian Telegram Job Channels.

Operates with zero API credentials by leveraging Telegram's public web preview (https://t.me/s/{channel}).
Guarantees continuous ingestion of vacancies across 31+ Ethiopian job channels even when MTProto credentials are not set.
"""

import asyncio
import html
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional
import httpx
from src.db.session import async_session_factory
from src.ingestion.channels import ETHIOPIAN_JOB_CHANNELS, get_monitored_channel_handles
from src.ingestion.parser import IngestionPipeline

logger = logging.getLogger(__name__)


def get_channel_display_name(handle: str) -> str:
    """Returns human-readable channel title from channel handle registry."""
    clean = handle.lstrip("@").strip().lower()
    for ch in ETHIOPIAN_JOB_CHANNELS:
        if ch["handle"].lstrip("@").strip().lower() == clean:
            return f"{ch['name']} (@{ch['handle']})"
    return f"@{clean}"


def build_telegram_post_url(source_channel: str, message_id: Optional[int] = None, structured_data: Optional[dict] = None) -> str:
    """Constructs a direct clickable link to the exact Telegram channel job posting.
    
    Guarantees linking directly to the specific message (e.g. https://t.me/awrajobs/15420)
    rather than just the channel root landing page.
    """
    clean = (source_channel or "").strip()
    handle = clean.lstrip("@").replace("https://t.me/", "").rstrip("/")
    if "/" in handle:
        handle = handle.split("/")[0]

    # Priority 1: Exact message link in the channel
    if handle and message_id:
        return f"https://t.me/{handle}/{message_id}"

    # Priority 2: External application portal / form if specified
    if structured_data:
        app_contact = (structured_data.get("application_contact") or "").strip()
        if app_contact.startswith("http://") or app_contact.startswith("https://"):
            return app_contact
        elif app_contact.startswith("@") and message_id:
            ch = app_contact.lstrip("@").strip()
            return f"https://t.me/{ch}/{message_id}"

    # Priority 3: Fallback to channel link
    return f"https://t.me/{handle}" if handle else "https://t.me"


class WebChannelScraper:
    def __init__(self, bot=None):
        self.bot = bot
        self.channels = get_monitored_channel_handles()
        self._headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def fetch_channel_posts(self, client: httpx.AsyncClient, channel_handle: str) -> List[Dict]:
        """Fetches recent vacancy posts from a public Telegram channel web preview.
        
        Only accepts fresh posts posted within the last 48 hours to prevent ingesting stale/closed jobs.
        """
        url = f"https://t.me/s/{channel_handle}"
        posts = []
        now = datetime.now(timezone.utc)
        max_age_seconds = 48 * 3600  # 48 hours max age

        try:
            res = await client.get(url, headers=self._headers, timeout=12.0, follow_redirects=True)
            if res.status_code != 200:
                logger.debug(f"Channel @{channel_handle} returned HTTP {res.status_code}")
                return []

            raw_html = res.text
            # Regex to match each message block between data-post markers
            block_pattern = re.compile(
                r'data-post=\"(?P<channel>[^/\"]+)/(?P<msg_id>\d+)\"(?P<block>.*?)(?=(?:data-post=\"[^/\"]+/\d+\"|\Z))',
                re.DOTALL
            )

            for m in block_pattern.finditer(raw_html):
                msg_id = int(m.group("msg_id"))
                block_content = m.group("block")

                # Extract text
                text_match = re.search(r'<div class=\"[^\"]*tgme_widget_message_text[^\"]*\"[^>]*>(?P<text>.*?)</div>', block_content, re.DOTALL)
                if not text_match:
                    continue

                raw_snippet = text_match.group("text")
                clean_text = re.sub(r'<br\s*/?>', '\n', raw_snippet)
                clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
                clean_text = html.unescape(clean_text).strip()

                if len(clean_text) < 40:
                    continue

                # Extract post timestamp: <time datetime="2026-11-24T08:15:00+00:00"
                time_match = re.search(r'<time[^>]*datetime=[\"\'](?P<time>[^\"\']+)[\"\']', block_content)
                posted_at = now
                if time_match:
                    try:
                        time_str = time_match.group("time")
                        parsed_dt = datetime.fromisoformat(time_str)
                        if parsed_dt.tzinfo is None:
                            parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                        posted_at = parsed_dt

                        # Freshness check: Skip jobs posted > 48 hours ago
                        age = (now - parsed_dt).total_seconds()
                        if age > max_age_seconds:
                            logger.debug(f"Skipping stale post @{channel_handle}/{msg_id} posted {age/3600:.1f}h ago")
                            continue
                    except Exception as e:
                        logger.debug(f"Failed parsing post time for @{channel_handle}/{msg_id}: {e}")

                posts.append({
                    "channel": f"@{channel_handle}",
                    "message_id": msg_id,
                    "raw_text": clean_text,
                    "posted_at": posted_at,
                })

        except Exception as e:
            logger.debug(f"Error scraping @{channel_handle}: {e}")

        return posts

    async def run_once(self) -> int:
        """Runs a complete ingestion sweep across all monitored Ethiopian channels."""
        total_ingested = 0
        logger.info(f"Starting web ingestion sweep across {len(self.channels)} Ethiopian job channels...")

        async with httpx.AsyncClient(limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)) as client:
            for handle in self.channels:
                posts = await self.fetch_channel_posts(client, handle)
                for post in posts:
                    try:
                        async with async_session_factory() as session:
                            pipeline = IngestionPipeline(session, bot=self.bot)
                            job = await pipeline.process_incoming_post(
                                source_channel=post["channel"],
                                message_id=post["message_id"],
                                raw_text=post["raw_text"],
                                posted_at=post["posted_at"],
                            )
                            if job:
                                total_ingested += 1
                    except Exception as e:
                        logger.error(f"Error processing post from {handle}: {e}")

                # Gentle pacing between channels to respect Telegram rate limits
                await asyncio.sleep(1.0)

        logger.info(f"Ingestion sweep complete. Ingested & indexed {total_ingested} new vacancy posts.")
        return total_ingested

    async def start_polling(self, interval_seconds: int = 180):
        """Continuously scrapes channels in background every interval_seconds (default 3 mins)."""
        logger.info(f"WebChannelScraper continuous polling active (Interval: {interval_seconds}s).")
        while True:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Error in WebChannelScraper polling loop: {e}")

            await asyncio.sleep(interval_seconds)

