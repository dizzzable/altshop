from typing import Optional
from uuid import UUID

from loguru import logger
from remnawave import RemnawaveSDK
from remnawave.exceptions import NotFoundError
from remnawave.models import (
    GetAllUsersResponseDto,
    GetUserHwidDevicesResponseDto,
    TelegramUserResponseDto,
    UserResponseDto,
)
from remnawave.models.hwid import HwidDeviceDto


class RemnawaveUserDeviceLookup:
    def __init__(self, remnawave: RemnawaveSDK) -> None:
        self.remnawave = remnawave

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

    async def get_all_users(self, page_size: int = 50) -> list[UserResponseDto]:
        all_users: list[UserResponseDto] = []
        start = 0

        while True:
            response = await self.remnawave.users.get_all_users(start=start, size=page_size)
            if not isinstance(response, GetAllUsersResponseDto) or not response.users:
                return all_users

            all_users.extend(response.users)
            start += len(response.users)

            if len(response.users) < page_size:
                return all_users
