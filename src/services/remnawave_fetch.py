# mypy: disable-error-code=attr-defined

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from loguru import logger
from remnawave import RemnawaveSDK
from remnawave.exceptions import NotFoundError
from remnawave.models import (
    DeleteUserHwidDeviceResponseDto,
    GetUserHwidDevicesResponseDto,
    HWIDDeleteRequest,
    TelegramUserResponseDto,
    UserResponseDto,
)
from remnawave.models.hwid import HwidDeviceDto


class RemnawaveFetchMixin:
    remnawave: RemnawaveSDK

    async def get_user(self, uuid: UUID) -> Optional[UserResponseDto]:
        logger.info(f"Fetching RemnaUser '{uuid}'")
        try:
            remna_user = await self.remnawave.users.get_user_by_uuid(str(uuid))
        except NotFoundError:
            logger.warning(f"RemnaUser '{uuid}' not found (NotFoundError)")
            return None

        if not isinstance(remna_user, UserResponseDto):
            logger.warning(f"RemnaUser '{uuid}' not found")
            return None

        logger.info(f"RemnaUser '{remna_user.telegram_id}' fetched successfully")
        return remna_user

    async def get_users_by_telegram_id(self, telegram_id: int) -> list[UserResponseDto]:
        logger.info(f"Fetching RemnaUsers by telegram_id '{telegram_id}'")
        users_result = await self.remnawave.users.get_users_by_telegram_id(
            telegram_id=str(telegram_id)
        )

        if not isinstance(users_result, TelegramUserResponseDto):
            raise ValueError("Unexpected response fetching users by telegram_id")

        users = list(users_result.root)
        logger.info(
            f"Fetched '{len(users)}' RemnaUser(s) by telegram_id '{telegram_id}' successfully"
        )
        return users

    async def get_users_map_by_telegram_id(self, telegram_id: int) -> dict[UUID, UserResponseDto]:
        users = await self.get_users_by_telegram_id(telegram_id)
        return {
            user.uuid: user
            for user in users
            if getattr(user, "uuid", None) is not None
        }

    async def get_subscription_url(self, uuid: UUID) -> Optional[str]:
        remna_user = await self.get_user(uuid)

        if remna_user is None:
            logger.warning(f"RemnaUser '{uuid}' has not subscription url")
            return None

        return remna_user.subscription_url

    async def get_devices_by_subscription_uuid(self, user_remna_id: UUID) -> list[HwidDeviceDto]:
        logger.info(f"Fetching devices for Remna subscription '{user_remna_id}'")

        result = await self.remnawave.hwid.get_hwid_user(uuid=str(user_remna_id))

        if not isinstance(result, GetUserHwidDevicesResponseDto):
            raise ValueError("Unexpected response fetching devices")

        if result.total:
            logger.info(
                f"Found '{result.total}' device(s) for Remna subscription '{user_remna_id}'"
            )
            return result.devices

        logger.info(f"No devices found for Remna subscription '{user_remna_id}'")
        return []

    async def get_devices_user(self, user: Any) -> list[HwidDeviceDto]:
        logger.info(f"Fetching devices for RemnaUser '{user.telegram_id}'")

        if not user.current_subscription:
            logger.warning(f"No subscription found for user '{user.telegram_id}'")
            return []

        return await self.get_devices_by_subscription_uuid(user.current_subscription.user_remna_id)

    async def delete_device_by_subscription_uuid(
        self,
        user_remna_id: UUID,
        hwid: str,
    ) -> Optional[int]:
        logger.info(f"Deleting device '{hwid}' for Remna subscription '{user_remna_id}'")

        result = await self.remnawave.hwid.delete_hwid_to_user(
            HWIDDeleteRequest(
                user_uuid=str(user_remna_id),
                hwid=hwid,
            )
        )

        if not isinstance(result, DeleteUserHwidDeviceResponseDto):
            raise ValueError("Unexpected response deleting device")

        logger.info(f"Deleted device '{hwid}' for Remna subscription '{user_remna_id}'")
        return int(result.total)

    async def delete_device(self, user: Any, hwid: str) -> Optional[int]:
        logger.info(f"Deleting device '{hwid}' for RemnaUser '{user.telegram_id}'")

        if not user.current_subscription:
            logger.warning(f"No subscription found for user '{user.telegram_id}'")
            return None

        return await self.delete_device_by_subscription_uuid(
            user_remna_id=user.current_subscription.user_remna_id,
            hwid=hwid,
        )
