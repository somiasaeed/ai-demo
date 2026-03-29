"""Hub-specific settings (Telegram). LLM keys use root `settings.py`."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HubSettings(BaseSettings):
    """Loaded from `.env` in the project root."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str | None = Field(
        default=None,
        description="Required for POST /webhook/telegram to send replies",
    )


@lru_cache
def get_hub_settings() -> HubSettings:
    return HubSettings()
