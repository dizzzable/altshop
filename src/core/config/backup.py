from pathlib import Path
from typing import Optional

from pydantic import Field

from .base import BaseConfig


class BackupConfig(BaseConfig, env_prefix="BACKUP_"):
    """Конфигурация системы бэкапов."""
    
    # Автоматические бэкапы
    auto_enabled: bool = Field(default=False, description="Включить автоматические бэкапы")
    interval_hours: int = Field(default=24, description="Интервал между бэкапами в часах")
    time: str = Field(default="03:00", description="Время запуска автоматического бэкапа (HH:MM)")
    max_keep: int = Field(default=7, description="Максимальное количество хранимых бэкапов")
    
    # Сжатие и содержимое
    compression: bool = Field(default=True, description="Включить сжатие бэкапов")
    include_logs: bool = Field(default=False, description="Включать логи в бэкап")
    
    # Расположение
    location: Path = Field(default=Path("/app/data/backups"), description="Директория для хранения бэкапов")
    
    # Отправка в Telegram
    send_enabled: bool = Field(default=False, description="Отправлять бэкапы в Telegram")
    send_chat_id: Optional[str] = Field(default=None, description="ID чата/канала для отправки бэкапов")
    send_topic_id: Optional[int] = Field(default=None, description="ID топика в супергруппе (для форумов)")
    
    def is_send_enabled(self) -> bool:
        """Проверяет, включена ли отправка бэкапов в Telegram."""
        return self.send_enabled and self.send_chat_id is not None
    
    def get_backup_dir(self) -> Path:
        """Возвращает путь к директории бэкапов."""
        path = self.location.expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path