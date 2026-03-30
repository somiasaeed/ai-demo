"""Unified application settings loaded from environment variables.

Merges LLM config, Telegram settings, API security, and service-specific
options into a single pydantic-settings model.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def project_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """All application configuration loaded from ``.env``."""

    # ---- LLM ----
    openai_api_key: str = Field(..., description="OpenAI-compatible API key")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI-compatible API base URL",
    )
    openai_model: str = Field(default="gpt-4o-mini", description="Model name")
    openai_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    openai_max_tokens: int = Field(default=4096, ge=1)

    # ---- Telegram ----
    telegram_bot_token: str | None = Field(
        default=None,
        description="Bot token from @BotFather",
    )
    telegram_webhook_secret: str | None = Field(
        default=None,
        description="X-Telegram-Bot-Api-Secret-Token for webhook verification",
    )

    # ---- API security ----
    api_key_header: str | None = Field(
        default=None,
        description="If set, require X-API-Key header on protected endpoints",
    )

    # ---- CORS ----
    cors_origins: str = Field(
        default="*",
        description="Comma-separated allowed origins",
    )

    # ---- Weather agent ----
    weather_api_key: str | None = Field(
        default=None,
        description="OpenWeatherMap API key (optional; falls back to Open-Meteo)",
    )

    # ---- CV pipeline ----
    cv_photo_path: str | None = Field(
        default=None,
        description="Override path for CV photo image",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_model_id(self) -> str:
        return f"openai/{self.openai_model}"

    def get_client_args(self) -> dict:
        return {"api_key": self.openai_api_key, "api_base": self.openai_base_url}

    def get_model_params(self) -> dict:
        return {
            "temperature": self.openai_temperature,
            "max_tokens": self.openai_max_tokens,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
