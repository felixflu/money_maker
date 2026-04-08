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

    # CORS
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
