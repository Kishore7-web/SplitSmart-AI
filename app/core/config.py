
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    app_name: str = "SplitSmart AI"
    app_version: str = "1.0.0"
    debug: bool = True

    database_url: str = "sqlite:///./splitsmart.db"

    gemini_api_key: str | None = None

    paypal_client_id: str | None = None
    paypal_client_secret: str | None = None
    paypal_mode: str = "sandbox"


settings = Settings()
