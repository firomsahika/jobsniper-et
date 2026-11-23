"""Internationalization (I18n) Middleware for JobSniper ET."""

import json
import os
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from src.db.session import async_session_factory
from src.db.repositories.candidate_repo import CandidateRepository


class I18nManager:
    def __init__(self, locales_dir: str = "src/locales"):
        self.locales: Dict[str, Dict[str, str]] = {}
        for lang in ["en", "am", "om"]:
            path = os.path.join(locales_dir, f"{lang}.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    self.locales[lang] = json.load(f)
            else:
                self.locales[lang] = {}

    def get(self, key: str, lang: str = "en", **kwargs) -> str:
        text = self.locales.get(lang, {}).get(key)
        if not text:
            # Fallback to English
            text = self.locales.get("en", {}).get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text


i18n = I18nManager()


class I18nMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: User = data.get("event_from_user")
        lang = "en"
        if user:
            # Check if user has a preference in DB
            try:
                async with async_session_factory() as session:
                    repo = CandidateRepository(session)
                    candidate = await repo.get_by_telegram_id(user.id)
                    if candidate and candidate.ui_language:
                        lang = candidate.ui_language
                    elif user.language_code in ["am", "om", "en"]:
                        lang = user.language_code
            except Exception:
                lang = "en"

        data["lang"] = lang
        data["i18n"] = i18n
        return await handler(event, data)

