from typing import Union

from pydantic import SecretStr, ValidationInfo, field_validator

from src.core.constants import API_V1, BOT_WEBHOOK_PATH, URL_PATTERN

from .base import BaseConfig
from .validators import validate_not_change_me, validate_username


class BotConfig(BaseConfig, env_prefix="BOT_"):
    token: SecretStr
    secret_token: SecretStr
    dev_id: list[int]
    support_username: SecretStr
    mini_app: Union[bool, SecretStr] = False

    reset_webhook: bool = False
    drop_pending_updates: bool = False
    setup_commands: bool = True
    setup_webhook: bool = True
    fetch_me_on_startup: bool = True
    use_banners: bool = True

    @property
    def webhook_path(self) -> str:
        return f"{API_V1}{BOT_WEBHOOK_PATH}"

    @property
    def is_mini_app(self) -> bool:
        return bool(self.mini_app_url)

    @property
    def has_configured_mini_app_url(self) -> bool:
        return bool(self.mini_app_url)

    @property
    def mini_app_url(self) -> Union[bool, str]:
        if isinstance(self.mini_app, SecretStr):
            value = self.mini_app.get_secret_value().strip()
            if value and URL_PATTERN.match(value):
                return value
        return False

    def webhook_url(self, domain: SecretStr) -> SecretStr:
        url = f"https://{domain.get_secret_value()}{self.webhook_path}"
        return SecretStr(url)

    def safe_webhook_url(self, domain: SecretStr) -> str:
        return f"https://{domain}{self.webhook_path}"

    @field_validator("dev_id", mode="before")
    @classmethod
    def validate_dev_id(cls, field: object) -> list[int]:
        if isinstance(field, int):
            return [field]
        if isinstance(field, str):
            return [int(x.strip()) for x in field.split(",") if x.strip()]
        if isinstance(field, list):
            return [int(x) for x in field]
        raise ValueError("dev_id must be an integer or comma-separated list of integers")

    @field_validator("token", "secret_token", "support_username")
    @classmethod
    def validate_bot_fields(cls, field: object, info: ValidationInfo) -> object:
        validate_not_change_me(field, info)
        return field

    @field_validator("support_username")
    @classmethod
    def validate_bot_support_username(cls, field: object, info: ValidationInfo) -> object:
        validate_username(field, info)
        return field

    @field_validator("mini_app")
    @classmethod
    def validate_mini_app(
        cls,
        field: Union[bool, SecretStr],
        info: ValidationInfo,
    ) -> Union[bool, SecretStr]:
        if isinstance(field, SecretStr):
            raw_value = field.get_secret_value().strip()
            normalized = raw_value.lower()
            if normalized == "false" or not raw_value:
                return False
            if normalized == "true":
                raise ValueError("BOT_MINI_APP must be empty, false, or an exact Mini App URL")
            if URL_PATTERN.match(raw_value):
                return SecretStr(raw_value)
            raise ValueError("BOT_MINI_APP must be empty, false, or an exact Mini App URL")
        return field
