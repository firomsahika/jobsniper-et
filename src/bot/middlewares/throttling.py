"""Throttling / Flood-wait Middleware for Telegram Bot."""

import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User, Message

RATE_LIMIT_SECONDS = 0.5


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self):
        self._user_last_action: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: User = data.get("event_from_user")
        if user:
            now = time.time()
            last = self._user_last_action.get(user.id, 0.0)
            if now - last < RATE_LIMIT_SECONDS:
                # Silently ignore rapid duplicate button taps
                if isinstance(event, Message):
                    # Could inform user if necessary
                    pass
                return None
            self._user_last_action[user.id] = now

        return await handler(event, data)

