from pydantic import PostgresDsn, SecretStr, ValidationInfo, field_validator

from .base import BaseConfig
from .validators import validate_not_change_me


class DatabaseConfig(BaseConfig, env_prefix="DATABASE_"):
    host: str = "altshop-db"
    port: int = 5432
    name: str = "altshop"
    user: str = "altshop"
    password: SecretStr

    echo: bool = False
    echo_pool: bool = False
    pool_size: int = 25
    max_overflow: int = 25
    pool_timeout: int = 10
    pool_recycle: int = 3600

    @property
    def dsn(self) -> str:
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            path=self.name,
        ).unicode_string()

    @field_validator("password")
    @classmethod
    def validate_database_password(cls, field: SecretStr, info: ValidationInfo) -> SecretStr:
        validate_not_change_me(field, info)
        return field
