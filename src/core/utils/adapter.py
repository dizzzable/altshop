from typing import Any, Optional, Type, TypeVar

from aiogram_dialog import DialogManager
from loguru import logger
from pydantic import ValidationError

from src.infrastructure.database.models.dto import BaseDto

DtoModel = TypeVar("DtoModel", bound="BaseDto")


class DialogDataAdapter:
    def __init__(self, dialog_manager: DialogManager) -> None:
        self.dialog_manager = dialog_manager

    def load(self, model_cls: Type[DtoModel]) -> Optional[DtoModel]:
        key = model_cls.__name__.lower()
        raw = self.dialog_manager.dialog_data.get(key)
        # logger.debug(f"Loading model '{key}' with data: {raw}")

        if raw is None:
            return None

        try:
            return model_cls.model_validate(raw)
        except ValidationError:
            return None

    def save(self, model: DtoModel) -> dict[str, Any]:
        key = model.__class__.__name__.lower()
        data = model.model_dump()
        try:
            self.dialog_manager.dialog_data[key] = data
            logger.debug(f"Model '{key}' data saved successfully")
        except Exception as exception:
            logger.error(f"Failed data save for model '{key}'. Error: {exception}")
        return data

    def clear(self, model_cls: Type[DtoModel] | None = None) -> None:
        """Clear stored model data from dialog_data.
        
        Args:
            model_cls: If provided, clears only the specific model's data.
                      If None, clears all dialog_data.
        """
        try:
            if model_cls is not None:
                key = model_cls.__name__.lower()
                if key in self.dialog_manager.dialog_data:
                    del self.dialog_manager.dialog_data[key]
                    logger.debug(f"Model '{key}' data cleared successfully")
            else:
                self.dialog_manager.dialog_data.clear()
                logger.debug("All dialog data cleared successfully")
        except Exception as exception:
            logger.error(f"Failed to clear dialog data. Error: {exception}")
