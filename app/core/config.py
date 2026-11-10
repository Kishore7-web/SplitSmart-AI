from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings for SplitSmart AI 2.0."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    app_name: str = "SplitSmart AI 2.0"
    app_version: str = "2.0.0"
    debug: bool = True

    database_url: str = "sqlite:///./splitsmart.db"

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    paypal_client_id: str | None = None
    paypal_client_secret: str | None = None
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    paypal_mode: str = "sandbox"
    paypal_webhook_id: str | None = None

    upload_dir: str = "uploads"
    max_upload_size_mb: int = 50


settings = Settings()
