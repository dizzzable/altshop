from pydantic import RedisDsn, SecretStr, ValidationInfo, field_validator

from .base import BaseConfig
from .validators import validate_not_change_me


class RedisConfig(BaseConfig, env_prefix="REDIS_"):
    host: str = "altshop-redis"
    port: int = 6379
    name: str = "0"
    password: SecretStr

    @property
    def dsn(self) -> str:
        return RedisDsn.build(
            scheme="redis",
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            path=self.name,
        ).unicode_string()

    @field_validator("password")
    @classmethod
    def validate_redis_password(cls, field: SecretStr, info: ValidationInfo) -> SecretStr:
        validate_not_change_me(field, info)
        return field
