from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "PricePulse"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "dev-secret-key-change-in-production-pricepulse-2026-auth"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pricepulse"
    SYNC_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/pricepulse"
    SQLITE_DEV_FALLBACK: bool = True
    SQLITE_URL: str = "sqlite+aiosqlite:///./pricepulse_dev.db"

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Search (Meilisearch)
    MEILISEARCH_URL: str = "http://localhost:7700"
    MEILISEARCH_KEY: str = "masterKey123456"
    MEILISEARCH_INDEX_PRODUCTS: str = "products"

    # Notifications
    SENDGRID_API_KEY: Optional[str] = None
    EMAIL_FROM: str = "alerts@pricepulse.local"
    FCM_SERVER_KEY: Optional[str] = None
    WEBHOOK_TIMEOUT_SECONDS: int = 10

    # LLM / Chat
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Scraping & Polling
    PLAYWRIGHT_HEADLESS: bool = True
    DEFAULT_POLL_INTERVAL_S: int = 21600       # 6 hours
    MIN_POLL_INTERVAL_S: int = 3600            # 1 hour
    MAX_POLL_INTERVAL_S: int = 172800          # 48 hours
    DORMANCY_THRESHOLD_DAYS: int = 30
    UNCHANGED_THRESHOLD_DAYS: int = 14

    # ML & Feature Constants
    V_HI: float = 0.10                         # High volatility coefficient of variation
    V_LO: float = 0.02                         # Low volatility coefficient of variation
    TARGET_PROXIMITY_THRESHOLD: float = 0.05   # 5% gap to closest user target
    W_MIN: int = 30                            # Min observations for learned model
    DISCOUNT_THRESHOLD: float = 0.07           # 7% drop below 14-day max
    HORIZON_H: int = 14                        # Forward window (days)
    TOLERANCE_DELTA: float = 0.03              # 3% threshold for label
    CLASSIFICATION_THRESHOLD_TAU: float = 0.5  # BUY if prob >= tau
    MAX_PRICE_DEVIATION: float = 0.50          # 50% deviation flags quarantine
    GBDT_N_ESTIMATORS: int = 400
    GBDT_MAX_DEPTH: int = 5
    GBDT_LEARNING_RATE: float = 0.06
    GBDT_REG_LAMBDA: float = 1.0


settings = Settings()
