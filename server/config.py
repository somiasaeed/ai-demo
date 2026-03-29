"""Server-only settings (extends repo root and optional Telegram)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


class ServerSettings(BaseSettings):
    """Telegram and server options. LLM vars still come from root `Settings` / `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str | None = Field(default=None, description="Bot token from @BotFather")
    telegram_webhook_secret: str | None = Field(
        default=None,
        description="Optional X-Telegram-Bot-Api-Secret-Token value for webhook verification",
    )
    api_key_header: str | None = Field(
        default=None,
        description="If set, require X-API-Key header on /api/* (except /health)",
    )
    cors_origins: str = Field(
        default="http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:8000,http://localhost:8000",
        description="Comma-separated allowed origins for browser dashboard",
    )


@lru_cache
def get_server_settings() -> ServerSettings:
    return ServerSettings()
