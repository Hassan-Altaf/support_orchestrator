"""Application configuration loaded from environment / .env via pydantic-settings.

Settings are validated at construction time:
  * provider-specific API keys are required when that provider is selected
  * `cors_origins` accepts a comma-separated string in `.env`
    (e.g. `CORS_ORIGINS=*,https://app.example.com`)

`get_settings()` is `lru_cache`-d so the rest of the app can call it freely
without re-parsing env vars on every request.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _split_csv(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value.strip():
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


# `NoDecode` stops pydantic-settings from JSON-parsing the env var before our
# `BeforeValidator` runs, so CORS_ORIGINS can be `*,https://app.example.com`
# in a .env file instead of requiring JSON syntax.
CSVList = Annotated[list[str], NoDecode, BeforeValidator(_split_csv)]


LLMProviderName = Literal["openai", "anthropic", "mock"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["json", "console"]


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- LLM -------------------------------------------------------------
    llm_provider: LLMProviderName = "openai"
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-sonnet-4-5"

    # ---- Orchestration ---------------------------------------------------
    max_retries: int = Field(default=2, ge=0, le=5)
    request_timeout_seconds: int = Field(default=30, ge=1, le=300)

    # ---- App -------------------------------------------------------------
    app_version: str = "0.1.0"
    log_level: LogLevel = "INFO"
    log_format: LogFormat = "json"
    cors_origins: CSVList = Field(default_factory=lambda: ["*"])

    @model_validator(mode="after")
    def _check_provider_credentials(self) -> Settings:
        if self.llm_provider == "openai" and self.openai_api_key is None:
            raise ValueError(
                "LLM_PROVIDER=openai requires OPENAI_API_KEY "
                "(set it in .env or as an environment variable, or use LLM_PROVIDER=mock)."
            )
        if self.llm_provider == "anthropic" and self.anthropic_api_key is None:
            raise ValueError(
                "LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY "
                "(set it in .env or as an environment variable, or use LLM_PROVIDER=mock)."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance.

    Cached so dependency-injection in FastAPI handlers is cheap. Tests can
    bypass the cache by instantiating `Settings(...)` directly or by calling
    `get_settings.cache_clear()`.
    """
    return Settings()
