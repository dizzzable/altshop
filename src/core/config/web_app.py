from typing import Optional

from pydantic import Field, SecretStr, ValidationInfo, field_validator

from src.core.constants import URL_PATTERN
from src.core.utils.types import StringList

from .base import BaseConfig
from .validators import validate_not_change_me


class WebAppConfig(BaseConfig, env_prefix="WEB_APP_"):
    """Configuration for Web Application (Mini App)."""

    # Main settings
    enabled: bool = True
    url: Optional[SecretStr] = None

    # JWT settings
    jwt_secret: SecretStr = Field(default_factory=lambda: SecretStr(""))
    jwt_expiry: int = 604800  # 7 days in seconds
    jwt_refresh_enabled: bool = True

    # CORS settings
    cors_origins: StringList = Field(default_factory=StringList)

    # API settings
    api_secret_token: SecretStr = Field(default_factory=lambda: SecretStr(""))
    # Auth challenge defaults
    telegram_link_code_ttl_seconds: int = 600
    email_verify_ttl_seconds: int = 1800
    password_reset_ttl_seconds: int = 1800
    auth_challenge_attempts: int = 5
    link_prompt_snooze_days: int = 3

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_max_requests: int = 60  # requests per minute
    rate_limit_window: int = 60  # seconds

    @property
    def url_str(self) -> str:
        """Get web app URL as string."""
        if self.url:
            return self.url.get_secret_value()
        return ""

    @property
    def is_enabled(self) -> bool:
        """Check if web app is enabled."""
        return self.enabled and bool(self.url_str)

    @field_validator("url")
    @classmethod
    def validate_url(
        cls, field: Optional[SecretStr], info: ValidationInfo
    ) -> Optional[SecretStr]:
        """Validate web app URL format."""
        if field is None:
            return None

        value = field.get_secret_value()
        if not value:
            return None

        if not URL_PATTERN.match(value):
            raise ValueError("WEB_APP_URL must be a valid URL (http:// or https://)")

        return field

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, field: SecretStr, info: ValidationInfo) -> SecretStr:
        """Validate JWT secret is strong enough."""
        validate_not_change_me(field, info)

        value = field.get_secret_value()
        if len(value) < 32:
            raise ValueError("WEB_APP_JWT_SECRET must be at least 32 characters long")

        return field

    @field_validator("api_secret_token")
    @classmethod
    def validate_api_secret_token(cls, field: SecretStr, info: ValidationInfo) -> SecretStr:
        """Validate API secret token."""
        validate_not_change_me(field, info)

        value = field.get_secret_value()
        if len(value) < 16:
            raise ValueError("WEB_APP_API_SECRET_TOKEN must be at least 16 characters long")

        return field

    @field_validator(
        "telegram_link_code_ttl_seconds",
        "email_verify_ttl_seconds",
        "password_reset_ttl_seconds",
        "auth_challenge_attempts",
        "link_prompt_snooze_days",
        "rate_limit_max_requests",
        "rate_limit_window",
    )
    @classmethod
    def validate_rate_limit(cls, field: int, info: ValidationInfo) -> int:
        """Validate numeric web-app limits."""
        if field <= 0:
            raise ValueError("Web app numeric settings must be positive integers")
        return field
