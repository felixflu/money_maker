"""
Application configuration using pydantic-settings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App settings
    app_name: str = Field(default="Money Maker API", alias="APP_NAME")
    debug: bool = Field(default=False, alias="DEBUG")
    env: str = Field(default="development", alias="ENV")

    # Database settings
    database_url: str = Field(
        default="postgresql://postgres:postgres@db:5432/money_maker",
        alias="DATABASE_URL",
    )

    # Security
    secret_key: str = Field(
        default="dev-secret-key-change-in-production", alias="SECRET_KEY"
    )
    access_token_expire_minutes: int = Field(
        default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # CORS
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # WealthAPI
    wealthapi_client_id: str = Field(default="", alias="WEALTHAPI_CLIENT_ID")
    wealthapi_client_secret: str = Field(default="", alias="WEALTHAPI_CLIENT_SECRET")
    wealthapi_base_url: str = Field(
        default="https://sandbox.wealthapi.eu", alias="WEALTHAPI_BASE_URL"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
