from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from .base import BaseConfig


class BackupConfig(BaseConfig, env_prefix="BACKUP_"):
    """Configuration for automated backups and Telegram delivery."""

    auto_enabled: bool = Field(default=False, description="Enable automatic backups")
    interval_hours: int = Field(default=24, description="Hours between automatic backups")
    time: str = Field(default="03:00", description="Automatic backup time in HH:MM format")
    max_keep: int = Field(default=7, description="Maximum number of backups to keep")

    compression: bool = Field(default=True, description="Enable backup compression")
    include_logs: bool = Field(default=False, description="Include logs in backup archives")

    location: Path = Field(
        default=Path("/app/data/backups"), description="Directory used to store backups"
    )

    send_enabled: bool = Field(default=False, description="Send backups to Telegram")
    send_chat_id: str | None = Field(
        default=None, description="Telegram chat or channel ID used for backup delivery"
    )
    send_topic_id: int | None = Field(
        default=None, description="Telegram forum topic ID used for backup delivery"
    )

    @field_validator("send_chat_id", "send_topic_id", mode="before")
    @classmethod
    def normalize_blank_optional_values(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def is_send_enabled(self) -> bool:
        return self.send_enabled and self.send_chat_id is not None

    def get_backup_dir(self) -> Path:
        path = self.location.expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path
