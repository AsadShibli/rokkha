from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Rokkha"
    app_env: str = "local"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://rokkha:rokkha@localhost:5433/rokkha"
    test_database_url: str = "postgresql+asyncpg://rokkha:rokkha@localhost:5433/rokkha_test"

    bcrypt_rounds: int = 12


@lru_cache
def get_settings() -> Settings:
    return Settings()
