"""Application settings loaded from environment variables."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DeploymentMode(str, Enum):
    SINGLE_TENANT = "single_tenant"
    MULTI_TENANT = "multi_tenant"


class Settings(BaseSettings):
    """Process-wide settings. Provider credentials are NOT stored here in production —
    they live encrypted in the DB per tenant. These env vars are dev/Phase 1 fallbacks."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Mode + secrets
    deployment_mode: DeploymentMode = DeploymentMode.SINGLE_TENANT
    master_key: str = ""
    jwt_secret: str = ""
    admin_email: str = "admin@example.com"
    admin_password: str = ""

    # LLM
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Image
    pexels_api_key: str = ""
    unsplash_access_key: str = ""

    # Voice / music
    elevenlabs_api_key: str = ""

    # Topic sources
    newsdata_api_key: str = ""
    newscatcher_api_key: str = ""

    # Social platforms
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_page_token: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    youtube_api_key: str = ""
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""

    # Storage
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_public_base_url: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""

    # Logging
    log_level: str = "INFO"
    log_dir: Path = Path("logs")
    log_json: bool = False

    # Paths (Phase 1 dev defaults)
    data_dir: Path = Path("data")
    templates_dir: Path = Path("templates")

    @property
    def usage_log_path(self) -> Path:
        return self.data_dir / "usage" / "events.jsonl"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
