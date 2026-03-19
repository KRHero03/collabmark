"""Application configuration loaded from environment variables."""

import logging
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_DEFAULT_JWT_SECRET = "CHANGE-ME-in-production-use-openssl-rand-hex-32"

AUTH_COOKIE_NAME = "access_token"


class Settings(BaseSettings):
    """Pydantic settings for app config: MongoDB, Redis, Google OAuth, JWT, CORS."""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "CollabMark"
    debug: bool = False

    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "collabmark"

    redis_url: str = "redis://localhost:6379"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    jwt_secret_key: str = _DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    session_secret_key: str = ""

    frontend_url: str = "http://localhost:5173"
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:8000",
    ]
    super_admin_emails: list[str] = []

    s3_endpoint_url: str = ""
    s3_access_key: str = "collabmark"
    s3_secret_key: str = "collabmark-secret"
    s3_bucket: str = "collabmark-media"
    s3_region: str = "us-east-1"

    notifications_enabled: bool = True
    notification_email_provider: str = "smtp"
    notification_from_email: str = "noreply@collabmark.app"
    notification_delay_seconds: int = 60

    resend_api_key: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""


settings = Settings()

if not settings.debug and settings.jwt_secret_key == _DEFAULT_JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET_KEY must be changed from the default value in production (set DEBUG=true for development)"
    )

if not settings.session_secret_key:
    logging.getLogger(__name__).warning("SESSION_SECRET_KEY not set — generating a random ephemeral key")
    settings.session_secret_key = secrets.token_hex(32)
