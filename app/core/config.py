from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "local-dev-secret-change-me-in-production-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Rokkha"
    app_env: str = "local"
    api_prefix: str = "/api/v1"

    # Browser origins allowed to call the API (comma-separated), e.g. the Vercel frontend.
    cors_origins: str = "http://localhost:3000"
    # Optional regex for preview deployments, e.g. https://rokkha-.*\.vercel\.app
    cors_origin_regex: str | None = None

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
    # Run the ARQ worker inside the API process (single-service free hosting).
    run_worker_in_process: bool = False
    # Load demo data on startup if missing, and mark seeded on-duty officers as seen
    # (free hosting has no shell to run scripts/seed.py).
    seed_demo_data: bool = False

    # AI GD draft (optional: without a key the endpoint answers 503 AI_UNAVAILABLE).
    ai_provider: str = "auto"  # auto | groq | anthropic
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"  # Llama models moved to Groq Enterprise
    anthropic_api_key: str | None = None
    ai_model: str = "claude-opus-5-5"
    ai_timeout_seconds: float = 20.0
    ai_draft_rate_limit: int = 10
    ai_draft_rate_window_seconds: int = 3600

    @field_validator("database_url", "test_database_url")
    @classmethod
    def use_asyncpg_driver(cls, url: str) -> str:
        """Hosts hand out libpq URLs (postgres://...?sslmode=require); convert for asyncpg."""
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                url = "postgresql+asyncpg://" + url.removeprefix(prefix)
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query))
        if "sslmode" in query:  # libpq name -> asyncpg name
            query["ssl"] = query.pop("sslmode")
        query.pop("channel_binding", None)  # libpq-only option (Neon adds it)
        return urlunsplit(parts._replace(query=urlencode(query)))

    @model_validator(mode="after")
    def real_secret_outside_local(self) -> "Settings":
        if self.app_env not in {"local", "test"} and self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET must be set outside local development")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
