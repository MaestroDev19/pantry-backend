from __future__ import annotations

from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "pantry-backend"
    app_version: str = "0.1.0"

    cors_allow_origins: list[str] = ["*"]

    supabase_url: AnyHttpUrl | None = None
    supabase_publishable_key: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None

    google_genai_api_key: str | None = Field(
        default=None,
        alias="GOOGLE_GENERATIVE_AI_API_KEY",
    )
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.0
    gemini_max_tokens: int = 1000
    gemini_max_retries: int = 2
    gemini_embeddings_model: str = "gemini-embedding-001"
    gemini_embeddings_output_dimensionality: int = 768

    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")

    embedding_batch_size: int = Field(
        default=50,
        alias="EMBEDDING_BATCH_SIZE",
    )
    embedding_worker_interval: int = Field(
        default=5,
        alias="EMBEDDING_WORKER_INTERVAL",
    )
    enable_background_workers: bool = Field(
        default=True,
        alias="ENABLE_BACKGROUND_WORKERS",
    )
    embedding_worker_secret: str = Field(
        default="",
        alias="EMBEDDING_WORKER_SECRET",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

