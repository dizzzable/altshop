import re
from pathlib import Path
from typing import Any, Self

from pydantic import Field, SecretStr, ValidationInfo, field_validator

from src.core.constants import API_V1, ASSETS_DIR, DOMAIN_REGEX, PAYMENTS_WEBHOOK_PATH
from src.core.enums import Locale, PaymentGatewayType
from src.core.utils.types import LocaleList, StringList

from .backup import BackupConfig
from .base import BaseConfig
from .bot import BotConfig
from .database import DatabaseConfig
from .email import EmailConfig
from .redis import RedisConfig
from .remnawave import RemnawaveConfig
from .validators import validate_not_change_me
from .web_app import WebAppConfig


class AppConfig(BaseConfig, env_prefix="APP_"):
    domain: SecretStr
    host: str = "0.0.0.0"
    port: int = 5000

    locales: LocaleList = LocaleList([Locale.EN])
    default_locale: Locale = Locale.EN

    crypt_key: SecretStr
    assets_dir: Path = ASSETS_DIR
    origins: StringList = StringList("")
    trusted_proxy_ips: list[str] = Field(default_factory=lambda: ["127.0.0.1", "::1"])

    bot: BotConfig = Field(default_factory=BotConfig)
    remnawave: RemnawaveConfig = Field(default_factory=RemnawaveConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    backup: BackupConfig = Field(default_factory=BackupConfig)
    web_app: WebAppConfig = Field(default_factory=WebAppConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)

    @property
    def banners_dir(self) -> Path:
        return self.assets_dir / "banners"

    @property
    def translations_dir(self) -> Path:
        return self.assets_dir / "translations"

    def get_webhook(self, gateway_type: PaymentGatewayType) -> str:
        domain = f"https://{self.domain.get_secret_value()}"
        path = f"{API_V1 + PAYMENTS_WEBHOOK_PATH}/{gateway_type.lower()}"
        return domain + path

    @property
    def forwarded_allow_ips(self) -> str:
        if not self.trusted_proxy_ips:
            return "127.0.0.1,::1"
        return ",".join(self.trusted_proxy_ips)

    @classmethod
    def get(cls) -> Self:
        return cls()

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, field: SecretStr, info: ValidationInfo) -> SecretStr:
        validate_not_change_me(field, info)

        if not re.match(DOMAIN_REGEX, field.get_secret_value()):
            raise ValueError("APP_DOMAIN has invalid format")

        return field

    @field_validator("crypt_key")
    @classmethod
    def validate_crypt_key(cls, field: SecretStr, info: ValidationInfo) -> SecretStr:
        validate_not_change_me(field, info)

        if not re.match(r"^[A-Za-z0-9+/=]{44}$", field.get_secret_value()):
            raise ValueError("APP_CRYPT_KEY must be a valid 44-character Base64 string")

        return field

    @field_validator("trusted_proxy_ips", mode="before")
    @classmethod
    def validate_trusted_proxy_ips(cls, field: Any) -> list[str]:
        if field is None:
            return ["127.0.0.1", "::1"]

        if isinstance(field, str):
            values = [value.strip() for value in field.split(",")]
            cleaned = [value for value in values if value]
            return cleaned or ["127.0.0.1", "::1"]

        if isinstance(field, (list, tuple, set)):
            cleaned = [str(value).strip() for value in field if str(value).strip()]
            return cleaned or ["127.0.0.1", "::1"]

        raise ValueError("APP_TRUSTED_PROXY_IPS must be a comma-separated string or list")
