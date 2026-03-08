from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.endpoints.user_subscription import (
    GenerateDeviceRequest,
    generate_device_link,
    list_devices,
    revoke_device,
)
from src.core.enums import DeviceType
from src.services.subscription_device import (
    GeneratedSubscriptionDeviceLink,
    RevokedSubscriptionDevice,
    SubscriptionDeviceAccessDeniedError,
    SubscriptionDeviceItem,
    SubscriptionDeviceLimitReachedError,
    SubscriptionDeviceListResult,
    SubscriptionDeviceNotFoundError,
)

LIST_DEVICES_ENDPOINT = getattr(
    inspect.unwrap(list_devices),
    "__dishka_orig_func__",
    inspect.unwrap(list_devices),
)
GENERATE_DEVICE_ENDPOINT = getattr(
    inspect.unwrap(generate_device_link),
    "__dishka_orig_func__",
    inspect.unwrap(generate_device_link),
)
REVOKE_DEVICE_ENDPOINT = getattr(
    inspect.unwrap(revoke_device),
    "__dishka_orig_func__",
    inspect.unwrap(revoke_device),
)


def _build_current_user(telegram_id: int) -> SimpleNamespace:
    return SimpleNamespace(telegram_id=telegram_id)


def test_list_devices_delegates_to_subscription_device_service() -> None:
    current_user = _build_current_user(telegram_id=1001)
    subscription_device_service = SimpleNamespace(
        list_devices=AsyncMock(
            return_value=SubscriptionDeviceListResult(
                devices=[
                    SubscriptionDeviceItem(
                        hwid="HWID-001",
                        device_type="WINDOWS",
                        first_connected="2026-03-01T10:00:00+00:00",
                        last_connected="2026-03-02T11:30:00+00:00",
                    )
                ],
                subscription_id=77,
                device_limit=3,
                devices_count=1,
            )
        )
    )

    response = asyncio.run(
        LIST_DEVICES_ENDPOINT(
            subscription_id=77,
            current_user=current_user,
            subscription_device_service=subscription_device_service,
        )
    )

    assert response.subscription_id == 77
    assert response.devices_count == 1
    assert response.devices[0].hwid == "HWID-001"
    subscription_device_service.list_devices.assert_awaited_once_with(
        subscription_id=77,
        user_telegram_id=current_user.telegram_id,
    )


def test_list_devices_maps_access_denied_to_403() -> None:
    current_user = _build_current_user(telegram_id=2002)
    subscription_device_service = SimpleNamespace(
        list_devices=AsyncMock(
            side_effect=SubscriptionDeviceAccessDeniedError(
                "Access denied to this subscription"
            )
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            LIST_DEVICES_ENDPOINT(
                subscription_id=88,
                current_user=current_user,
                subscription_device_service=subscription_device_service,
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Access denied to this subscription"


def test_generate_device_link_delegates_to_subscription_device_service() -> None:
    current_user = _build_current_user(telegram_id=3003)
    subscription_device_service = SimpleNamespace(
        generate_device_link=AsyncMock(
            return_value=GeneratedSubscriptionDeviceLink(
                hwid="abc123",
                connection_url="https://runtime.local/subscription",
                device_type=DeviceType.WINDOWS.value,
            )
        )
    )

    response = asyncio.run(
        GENERATE_DEVICE_ENDPOINT(
            request=GenerateDeviceRequest(
                subscription_id=99,
                device_type=DeviceType.WINDOWS,
            ),
            current_user=current_user,
            subscription_device_service=subscription_device_service,
        )
    )

    assert response.hwid == "abc123"
    assert response.connection_url == "https://runtime.local/subscription"
    assert response.device_type == DeviceType.WINDOWS.value
    subscription_device_service.generate_device_link.assert_awaited_once_with(
        subscription_id=99,
        user_telegram_id=current_user.telegram_id,
        device_type=DeviceType.WINDOWS,
    )


def test_generate_device_link_maps_limit_error_to_400() -> None:
    current_user = _build_current_user(telegram_id=4004)
    subscription_device_service = SimpleNamespace(
        generate_device_link=AsyncMock(
            side_effect=SubscriptionDeviceLimitReachedError(devices_count=3, device_limit=3)
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            GENERATE_DEVICE_ENDPOINT(
                request=GenerateDeviceRequest(subscription_id=101),
                current_user=current_user,
                subscription_device_service=subscription_device_service,
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Device limit reached: 3/3"


def test_revoke_device_delegates_to_subscription_device_service() -> None:
    current_user = _build_current_user(telegram_id=5005)
    subscription_device_service = SimpleNamespace(
        revoke_device=AsyncMock(
            return_value=RevokedSubscriptionDevice(
                success=True,
                message="Device HWID-001 revoked successfully",
            )
        )
    )

    response = asyncio.run(
        REVOKE_DEVICE_ENDPOINT(
            hwid="HWID-001",
            subscription_id=123,
            current_user=current_user,
            subscription_device_service=subscription_device_service,
        )
    )

    assert response == {
        "success": True,
        "message": "Device HWID-001 revoked successfully",
    }
    subscription_device_service.revoke_device.assert_awaited_once_with(
        subscription_id=123,
        user_telegram_id=current_user.telegram_id,
        hwid="HWID-001",
    )


def test_revoke_device_maps_not_found_to_404() -> None:
    current_user = _build_current_user(telegram_id=6006)
    subscription_device_service = SimpleNamespace(
        revoke_device=AsyncMock(
            side_effect=SubscriptionDeviceNotFoundError("Device HWID-404 not found")
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            REVOKE_DEVICE_ENDPOINT(
                hwid="HWID-404",
                subscription_id=124,
                current_user=current_user,
                subscription_device_service=subscription_device_service,
            )
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Device HWID-404 not found"
