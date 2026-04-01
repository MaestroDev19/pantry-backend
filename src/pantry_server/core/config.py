from __future__ import annotations

from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "pantry-backend"
    app_version: str = "0.1.0"

    # Keep runtime fields used by app bootstrap.
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    cors_allow_origins: list[str] = ["*"]

    supabase_url: AnyHttpUrl | None = None
    supabase_publishable_key: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_secret: str | None = None

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
    embedding_worker_secret: str | None = Field(default=None, alias="EMBEDDING_WORKER_SECRET")

    pantry_read_cache_enabled: bool = Field(default=True, alias="PANTRY_READ_CACHE_ENABLED")
    pantry_read_cache_ttl_seconds: int = Field(default=45, ge=0, alias="PANTRY_READ_CACHE_TTL_SECONDS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
