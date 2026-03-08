from __future__ import annotations

from src.core.enums import AccessMode
from src.infrastructure.database.models.dto import UserDto

from .settings import SettingsService

ACCESS_DENIED_SERVICE_RESTRICTED = "Access denied: service is currently restricted"
ACCESS_DENIED_PURCHASES_DISABLED = "Access denied: purchases are currently disabled"


class PurchaseAccessError(Exception):
    def __init__(self, *, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class PurchaseAccessService:
    def __init__(self, settings_service: SettingsService) -> None:
        self.settings_service = settings_service

    async def assert_can_purchase(self, current_user: UserDto) -> None:
        if current_user.is_privileged:
            return

        mode = await self.settings_service.get_access_mode()
        if mode == AccessMode.RESTRICTED:
            raise PurchaseAccessError(
                status_code=403,
                detail=ACCESS_DENIED_SERVICE_RESTRICTED,
            )

        if mode == AccessMode.PURCHASE_BLOCKED:
            raise PurchaseAccessError(
                status_code=403,
                detail=ACCESS_DENIED_PURCHASES_DISABLED,
            )
