from functools import lru_cache

from pydantic import model_validator
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

    @model_validator(mode="after")
    def real_secret_outside_local(self) -> "Settings":
        if self.app_env not in {"local", "test"} and self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET must be set outside local development")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
