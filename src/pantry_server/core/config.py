from __future__ import annotations

from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

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

    households_join_rate_limit_enabled: bool = Field(
        default=True,
        alias="HOUSEHOLDS_JOIN_RATE_LIMIT_ENABLED",
    )
    households_join_rate_limit_ip_per_minute: int = Field(
        default=30,
        ge=0,
        alias="HOUSEHOLDS_JOIN_RATE_LIMIT_IP_PER_MINUTE",
    )
    households_join_rate_limit_user_per_minute: int = Field(
        default=10,
        ge=0,
        alias="HOUSEHOLDS_JOIN_RATE_LIMIT_USER_PER_MINUTE",
    )
    ai_rate_limit_enabled: bool = Field(default=True, alias="AI_RATE_LIMIT_ENABLED")
    ai_rate_limit_ip_per_minute: int = Field(
        default=20,
        ge=0,
        alias="AI_RATE_LIMIT_IP_PER_MINUTE",
    )
    household_mutations_rate_limit_enabled: bool = Field(
        default=True,
        alias="HOUSEHOLD_MUTATIONS_RATE_LIMIT_ENABLED",
    )
    household_mutations_user_per_minute: int = Field(
        default=30,
        ge=0,
        alias="HOUSEHOLD_MUTATIONS_USER_PER_MINUTE",
    )
    trust_x_forwarded_for: bool = Field(
        default=False,
        alias="TRUST_X_FORWARDED_FOR",
    )
    embedding_worker_secret: str | None = Field(default=None, alias="EMBEDDING_WORKER_SECRET")

    pantry_read_cache_enabled: bool = Field(default=True, alias="PANTRY_READ_CACHE_ENABLED")
    pantry_read_cache_ttl_seconds: int = Field(default=45, ge=0, alias="PANTRY_READ_CACHE_TTL_SECONDS")

    auth_allow_x_user_id_header: bool = Field(default=False, alias="AUTH_ALLOW_X_USER_ID")

    metrics_enabled: bool = Field(default=True, alias="METRICS_ENABLED")


@lru_cache
def get_settings() -> Settings:
    return Settings()
