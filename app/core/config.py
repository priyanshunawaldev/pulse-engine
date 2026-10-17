from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application
    APP_NAME: str = "PulseEngine"
    APP_ENV: str = "development"  # development | production | testing
    DEBUG: bool = False
    SECRET_KEY: str = "dev_secret_key_change_in_production_0123456789abcdef"
    API_KEY_HEADER: str = "X-API-Key"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pulseengine"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_LOCK_TTL_SECONDS: int = 30

    # Rate Limiting (Token Bucket)
    RATE_LIMIT_REQUESTS: int = 1000
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Webhook
    WEBHOOK_SECRET: str = "default_webhook_signing_secret_dev"
    WEBHOOK_MAX_RETRIES: int = 3
    WEBHOOK_RETRY_BACKOFF: list[int] = [5, 30, 120]  # seconds


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
