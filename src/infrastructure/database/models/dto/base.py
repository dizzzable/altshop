from typing import Any, Iterable, Optional, Type, TypeVar

from pydantic import BaseModel as _BaseModel
from pydantic import ConfigDict, PrivateAttr, SecretStr

from src.core.security.crypto import deep_decrypt
from src.core.security.crypto import encrypt as encrypt_func
from src.infrastructure.database.models.sql import BaseSql

SqlModel = TypeVar("SqlModel", bound=BaseSql)
DtoModel = TypeVar("DtoModel", bound="BaseDto")


class BaseDto(_BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        from_attributes=True,
        populate_by_name=True,
    )

    @classmethod
    def from_model(
        cls: Type[DtoModel],
        model_instance: Optional[SqlModel],
        *,
        decrypt: bool = False,
    ) -> Optional[DtoModel]:
        if model_instance is None:
            return None

        data = model_instance.__dict__.copy()
        if decrypt:
            data = deep_decrypt(data)

        return cls.model_validate(data)

    @classmethod
    def from_model_list(
        cls: Type[DtoModel],
        model_instances: Iterable[SqlModel],
        *,
        decrypt: bool = False,
    ) -> list[DtoModel]:
        return [
            dto
            for model in model_instances
            if (dto := cls.from_model(model, decrypt=decrypt)) is not None
        ]


class TrackableDto(BaseDto):
    __changed_data: dict[str, Any] = PrivateAttr(default_factory=dict)

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        self.__changed_data[name] = value

    @property
    def changed_data(self) -> dict[str, Any]:
        return self.__changed_data

    def _process_value(self, value: Any, encrypt: bool = False) -> Any:
        if isinstance(value, SecretStr):
            raw = value.get_secret_value()
            if encrypt:
                raw = encrypt_func(raw)
            return raw
        if isinstance(value, list):
            return [self._process_value(v, encrypt) for v in value]
        if isinstance(value, dict):
            return {k: self._process_value(v, encrypt) for k, v in value.items()}
        if isinstance(value, TrackableDto):
            return value.prepare_init_data(encrypt)
        return value

    def prepare_init_data(self, encrypt: bool = False) -> dict[str, Any]:
        return {
            k: self._process_value(v, encrypt)
            for k, v in self.model_dump().items()
            if not k.startswith("_")
        }

    def prepare_changed_data(self, encrypt: bool = False) -> dict[str, Any]:
        return {
            k: self._process_value(v, encrypt)
            for k, v in self.changed_data.items()
            if not k.startswith("_")
        }
