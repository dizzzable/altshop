from typing import Optional

from pydantic import SecretStr, ValidationInfo, field_validator

from .base import BaseConfig


class EmailConfig(BaseConfig, env_prefix="EMAIL_"):
    """SMTP settings used by web auth flows (verify/reset emails)."""

    enabled: bool = False
    host: str = ""
    port: int = 587
    username: Optional[SecretStr] = None
    password: Optional[SecretStr] = None
    from_address: str = ""
    from_name: str = "AltShop"
    use_tls: bool = True
    use_ssl: bool = False

    @field_validator("port")
    @classmethod
    def validate_port(cls, field: int, info: ValidationInfo) -> int:
        if field <= 0:
            raise ValueError("EMAIL_PORT must be a positive integer")
        return field

    @field_validator("host", "from_address")
    @classmethod
    def strip_text_fields(cls, field: str, info: ValidationInfo) -> str:
        return field.strip()
