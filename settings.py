"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """LLM configuration loaded from `.env`.

    `extra="ignore"` allows hub keys (e.g. TELEGRAM_BOT_TOKEN) in the same file without
    breaking `get_settings()` when Strands agents load.
    """

    openai_api_key: str = Field(..., description="OpenAI-compatible API key")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI-compatible API base URL",
    )
    openai_model: str = Field(default="gpt-4o-mini", description="Model name")
    openai_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    openai_max_tokens: int = Field(default=4096, ge=1)

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
