from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "local-dev-secret-change-me-in-production-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Rokkha"
    app_env: str = "local"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://rokkha:rokkha@localhost:5433/rokkha"
    test_database_url: str = "postgresql+asyncpg://rokkha:rokkha@localhost:5433/rokkha_test"
    redis_url: str = "redis://localhost:6379/0"

    bcrypt_rounds: int = 12

    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    # An available officer counts as reachable only if seen this recently (BR Officers 8).
    officer_reachable_minutes: int = 10

    # BR Incidents-creation 8 and Lifecycle 11.
    sos_rate_limit: int = 3
    sos_rate_window_seconds: int = 600
    sos_accept_timeout_seconds: int = 120

    # AI GD draft (optional: without a key the endpoint answers 503 AI_UNAVAILABLE).
    anthropic_api_key: str | None = None
    ai_model: str = "claude-opus-5-5"
    ai_timeout_seconds: float = 20.0
    ai_draft_rate_limit: int = 10
    ai_draft_rate_window_seconds: int = 3600

    @field_validator("database_url", "test_database_url")
    @classmethod
    def use_asyncpg_driver(cls, url: str) -> str:
        """Hosts (Render, Railway, Heroku) hand out postgres:// URLs; we need asyncpg."""
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url.removeprefix(prefix)
        return url

    @model_validator(mode="after")
    def real_secret_outside_local(self) -> "Settings":
        if self.app_env not in {"local", "test"} and self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET must be set outside local development")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
