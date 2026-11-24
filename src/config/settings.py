"""Application Settings Configuration using Pydantic Settings."""

import os
from typing import List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = Field(default="")
    TELEGRAM_WEBHOOK_URL: Optional[str] = Field(default=None)
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = Field(default=None)
    TELEGRAM_WEBAPP_URL: Optional[str] = Field(default=None)

    # Gemini AI
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = Field(default="gemini-1.5-flash")
    EMBEDDING_MODEL: str = Field(default="text-embedding-004")

    # Database (PostgreSQL with pgvector)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://jobsniper:jobsniper_secure_password@localhost:5434/jobsniper_db"
    )

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Security (AES-256-GCM encryption key for raw CV texts)
    # Default 32-byte key for local development
    CV_ENCRYPTION_KEY: str = Field(
        default="dGhpc19pc19hXzMyX2J5dGVfZHVtbXlfa2V5X2Zvcl9kZXZlbG9wbWVudF8="
    )

    # MTProto Listener (Telegram Client)
    TELEGRAM_API_ID: Optional[int] = Field(default=None)
    TELEGRAM_API_HASH: Optional[str] = Field(default=None)
    TELEGRAM_SESSION_NAME: str = Field(default="jobsniper_listener")

    @field_validator("TELEGRAM_API_ID", mode="before")
    @classmethod
    def parse_api_id(cls, v):
        if v == "" or v is None:
            return None
        return int(v)

    # Engine Thresholds
    DEFAULT_MIN_MATCH_SCORE: int = Field(default=80)
    STAGE1_VECTOR_THRESHOLD: float = Field(default=0.55)
    DEDUPLICATION_SIMILARITY_THRESHOLD: float = Field(default=0.92)
    OUTBOUND_RATE_LIMIT_PER_SEC: int = Field(default=25)


# Global cached settings instance
settings = Settings()

