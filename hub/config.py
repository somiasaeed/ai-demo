"""Unified settings — LLM configuration, security, and Telegram bot token from .env."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application settings loaded from .env."""

    # ── LLM ──────────────────────────────────────────────────────────────
    openai_api_key: str = Field(..., description="OpenAI-compatible API key")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI-compatible API base URL",
    )
    openai_model: str = Field(default="gpt-4o-mini", description="Model name")
    openai_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    openai_max_tokens: int = Field(default=4096, ge=1)

    # ── Security ─────────────────────────────────────────────────────────
    jwt_secret: str = Field(
        ...,
        description="Secret key used to sign JWTs. Generate with: python -m hub.core.security",
    )
    admin_username: str = Field(default="admin", description="Admin username")
    admin_password_hash: str = Field(
        ...,
        description="Bcrypt hash of the admin password. Generate with: python -m hub.core.security",
    )
    production: bool = Field(
        default=False,
        description="Set to true to disable /docs and /redoc",
    )

    # ── Telegram ─────────────────────────────────────────────────────────
    telegram_bot_token: str | None = Field(
        default=None,
        description="Required for POST /webhook/telegram to send replies",
    )
    telegram_webhook_secret: str | None = Field(
        default=None,
        description="Value of X-Telegram-Bot-Api-Secret-Token header that Telegram sends",
    )

    # ── Job search (Adzuna) — optional; job alerts disabled if app_id is unset ──
    adzuna_app_id: str | None = Field(default=None, description="Adzuna API app_id (free, developer.adzuna.com).")
    adzuna_app_key: str | None = Field(default=None, description="Adzuna API app_key.")
    job_search_country: str = Field(default="de", description="Adzuna country code; 'de' = all Germany.")
    job_search_keywords: str = Field(
        default="Werkstudent,Praktikum,Working Student,internship",
        description="Comma-separated search terms.",
    )
    job_search_interval_minutes: int = Field(default=120, ge=10, description="How often to poll for new jobs.")
    job_search_max_cvs: int = Field(default=3, ge=0, description="Max CVs auto-generated per cycle; rest get a link only.")

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
