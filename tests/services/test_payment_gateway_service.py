from __future__ import annotations

import asyncio
from itertools import count
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from src.core.constants import ENCRYPTED_PREFIX
from src.core.enums import Currency, PaymentGatewayType
from src.infrastructure.database.models.dto import (
    CryptopayGatewaySettingsDto,
    PaymentGatewayDto,
    PlategaGatewaySettingsDto,
    YookassaGatewaySettingsDto,
)
from src.infrastructure.database.models.sql import PaymentGateway
from src.services.payment_gateway import PaymentGatewayService


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_db_gateway(
    *,
    gateway_id: int,
    order_index: int,
    gateway_type: PaymentGatewayType,
    currency: Currency,
    is_active: bool,
    settings: dict | None,
) -> PaymentGateway:
    return PaymentGateway(
        id=gateway_id,
        order_index=order_index,
        type=gateway_type,
        currency=currency,
        is_active=is_active,
        settings=settings,
    )


def build_service() -> tuple[PaymentGatewayService, SimpleNamespace]:
    gateways_repo = SimpleNamespace(
        create=AsyncMock(),
        update=AsyncMock(),
        get=AsyncMock(return_value=None),
        get_by_type=AsyncMock(return_value=None),
        get_all=AsyncMock(return_value=[]),
        filter_active=AsyncMock(return_value=[]),
        get_max_index=AsyncMock(return_value=0),
    )
    uow = SimpleNamespace(repository=SimpleNamespace(gateways=gateways_repo))
    service = PaymentGatewayService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        uow=uow,
        transaction_service=MagicMock(),
        subscription_service=MagicMock(),
        payment_gateway_factory=MagicMock(),
        payment_webhook_event_service=MagicMock(),
        referral_service=MagicMock(),
        partner_service=MagicMock(),
        user_service=MagicMock(),
        settings_service=MagicMock(),
    )
    return service, gateways_repo


def test_create_default_bootstraps_expected_defaults_for_missing_gateways() -> None:
    service, gateways_repo = build_service()
    next_index = count(start=0)
    created_gateways: list[PaymentGateway] = []
    gateways_repo.get_max_index = AsyncMock(side_effect=lambda: next(next_index))
    gateways_repo.create = AsyncMock(
        side_effect=lambda gateway: created_gateways.append(gateway) or gateway
    )
    service.get_by_type = AsyncMock(return_value=None)  # type: ignore[method-assign]

    run_async(service.create_default())

    assert gateways_repo.create.await_count == len(PaymentGatewayType)
    assert [gateway.order_index for gateway in created_gateways] == list(
        range(1, len(PaymentGatewayType) + 1)
    )

    by_type = {gateway.type: gateway for gateway in created_gateways}
    telegram_stars = by_type[PaymentGatewayType.TELEGRAM_STARS]
    yookassa = by_type[PaymentGatewayType.YOOKASSA]
    platega = by_type[PaymentGatewayType.PLATEGA]

    assert telegram_stars.is_active is True
    assert telegram_stars.settings is None
    assert yookassa.is_active is False
    assert isinstance(yookassa.settings, dict)
    assert yookassa.settings["type"] == YookassaGatewaySettingsDto().type
    assert platega.is_active is False
    assert platega.currency == Currency.RUB
    assert platega.settings["type"] == PlategaGatewaySettingsDto().type
    assert platega.settings["payment_method"] == 2


def test_create_default_skips_existing_gateways() -> None:
    service, gateways_repo = build_service()
    next_index = count(start=0)
    gateways_repo.get_max_index = AsyncMock(side_effect=lambda: next(next_index))

    async def get_by_type(gateway_type: PaymentGatewayType):
        if gateway_type == PaymentGatewayType.TELEGRAM_STARS:
            return SimpleNamespace(id=1)
        return None

    service.get_by_type = AsyncMock(side_effect=get_by_type)  # type: ignore[method-assign]

    run_async(service.create_default())

    assert gateways_repo.create.await_count == len(PaymentGatewayType) - 1


def test_normalize_gateway_settings_updates_only_legacy_values() -> None:
    service, gateways_repo = build_service()
    cryptopay_gateway = build_db_gateway(
        gateway_id=1,
        order_index=1,
        gateway_type=PaymentGatewayType.CRYPTOPAY,
        currency=Currency.RUB,
        is_active=False,
        settings={"type": PaymentGatewayType.CRYPTOPAY.value},
    )
    legacy_platega_gateway = build_db_gateway(
        gateway_id=2,
        order_index=2,
        gateway_type=PaymentGatewayType.PLATEGA,
        currency=Currency.RUB,
        is_active=False,
        settings={"payment_method": "SBPQR"},
    )
    canonical_platega_gateway = build_db_gateway(
        gateway_id=3,
        order_index=3,
        gateway_type=PaymentGatewayType.PLATEGA,
        currency=Currency.RUB,
        is_active=False,
        settings={"type": PaymentGatewayType.PLATEGA.value, "payment_method": 2},
    )
    gateways_repo.get_all = AsyncMock(
        return_value=[cryptopay_gateway, legacy_platega_gateway, canonical_platega_gateway]
    )

    run_async(service.normalize_gateway_settings())

    assert gateways_repo.update.await_count == 2
    first_call = gateways_repo.update.await_args_list[0].kwargs
    second_call = gateways_repo.update.await_args_list[1].kwargs

    assert first_call == {"gateway_id": 1, "currency": Currency.USD}
    assert second_call["gateway_id"] == 2
    assert second_call["settings"]["type"] == PaymentGatewayType.PLATEGA.value
    assert second_call["settings"]["payment_method"] == 2


def test_get_and_get_by_type_return_none_for_missing_gateways() -> None:
    service, gateways_repo = build_service()
    gateways_repo.get = AsyncMock(return_value=None)
    gateways_repo.get_by_type = AsyncMock(return_value=None)

    assert run_async(service.get(1)) is None
    assert run_async(service.get_by_type(PaymentGatewayType.PLATEGA)) is None


def test_get_and_get_by_type_return_hydrated_dto_for_existing_gateway() -> None:
    service, gateways_repo = build_service()
    db_gateway = build_db_gateway(
        gateway_id=1,
        order_index=1,
        gateway_type=PaymentGatewayType.PLATEGA,
        currency=Currency.RUB,
        is_active=True,
        settings={
            "type": PaymentGatewayType.PLATEGA.value,
            "merchant_id": "merchant-id",
            "payment_method": 2,
        },
    )
    gateways_repo.get = AsyncMock(return_value=db_gateway)
    gateways_repo.get_by_type = AsyncMock(return_value=db_gateway)

    by_id = run_async(service.get(1))
    by_type = run_async(service.get_by_type(PaymentGatewayType.PLATEGA))

    assert by_id is not None and by_type is not None
    assert by_id.type == PaymentGatewayType.PLATEGA
    assert by_type.type == PaymentGatewayType.PLATEGA
    assert by_id.settings is not None
    assert by_id.settings.payment_method == 2


def test_update_encrypts_changed_settings_before_repository_call() -> None:
    service, gateways_repo = build_service()
    gateway = PaymentGatewayDto(
        id=1,
        order_index=1,
        type=PaymentGatewayType.CRYPTOPAY,
        currency=Currency.USD,
        is_active=False,
        settings=CryptopayGatewaySettingsDto(
            shop_id="shop-id",
            api_key=SecretStr("api-key"),
            secret_key=SecretStr("secret-key"),
        ),
    )
    assert gateway.settings is not None
    gateway.settings.api_key = SecretStr("updated-api-key")
    updated_gateway = build_db_gateway(
        gateway_id=1,
        order_index=1,
        gateway_type=PaymentGatewayType.CRYPTOPAY,
        currency=Currency.USD,
        is_active=False,
        settings={
            "type": PaymentGatewayType.CRYPTOPAY.value,
            "shop_id": "shop-id",
            "api_key": "persisted",
            "secret_key": "persisted",
        },
    )
    gateways_repo.update = AsyncMock(return_value=updated_gateway)

    result = run_async(service.update(gateway))

    assert result is not None
    settings_payload = gateways_repo.update.await_args.kwargs["settings"]
    assert settings_payload["shop_id"] == "shop-id"
    assert settings_payload["api_key"].startswith(ENCRYPTED_PREFIX)
    assert settings_payload["secret_key"].startswith(ENCRYPTED_PREFIX)


def test_get_all_and_filter_active_preserve_repository_passthrough_semantics() -> None:
    service, gateways_repo = build_service()
    gateways = [
        build_db_gateway(
            gateway_id=1,
            order_index=1,
            gateway_type=PaymentGatewayType.PLATEGA,
            currency=Currency.RUB,
            is_active=True,
            settings={"type": PaymentGatewayType.PLATEGA.value, "payment_method": 2},
        )
    ]
    gateways_repo.get_all = AsyncMock(return_value=gateways)
    gateways_repo.filter_active = AsyncMock(return_value=gateways)

    all_gateways = run_async(service.get_all(sorted=True))
    active_gateways = run_async(service.filter_active(is_active=True))

    gateways_repo.get_all.assert_awaited_once_with(True)
    gateways_repo.filter_active.assert_awaited_once_with(True)
    assert len(all_gateways) == 1
    assert len(active_gateways) == 1
    assert all_gateways[0].type == PaymentGatewayType.PLATEGA
    assert active_gateways[0].type == PaymentGatewayType.PLATEGA


def test_move_gateway_up_swaps_neighbors_and_wraps_top_to_bottom() -> None:
    service, gateways_repo = build_service()
    gateways = [
        SimpleNamespace(id=1, order_index=1),
        SimpleNamespace(id=2, order_index=2),
        SimpleNamespace(id=3, order_index=3),
    ]
    gateways_repo.get_all = AsyncMock(return_value=gateways)

    moved = run_async(service.move_gateway_up(2))

    assert moved is True
    assert [gateway.id for gateway in gateways] == [2, 1, 3]
    assert [gateway.order_index for gateway in gateways] == [1, 2, 3]

    gateways = [
        SimpleNamespace(id=1, order_index=1),
        SimpleNamespace(id=2, order_index=2),
        SimpleNamespace(id=3, order_index=3),
    ]
    gateways_repo.get_all = AsyncMock(return_value=gateways)

    moved = run_async(service.move_gateway_up(1))

    assert moved is True
    assert [gateway.id for gateway in gateways] == [2, 3, 1]
    assert [gateway.order_index for gateway in gateways] == [1, 2, 3]


def test_move_gateway_up_returns_false_for_unknown_id() -> None:
    service, gateways_repo = build_service()
    gateways_repo.get_all = AsyncMock(return_value=[SimpleNamespace(id=1, order_index=1)])

    moved = run_async(service.move_gateway_up(999))

    assert moved is False


def test_get_gateway_instance_uses_factory_and_raises_when_missing() -> None:
    service, _gateways_repo = build_service()
    gateway = PaymentGatewayDto(
        id=1,
        order_index=1,
        type=PaymentGatewayType.PLATEGA,
        currency=Currency.RUB,
        is_active=True,
        settings=PlategaGatewaySettingsDto(merchant_id="merchant", secret=SecretStr("secret")),
    )
    service.get_by_type = AsyncMock(return_value=gateway)  # type: ignore[method-assign]
    service.payment_gateway_factory = MagicMock(return_value="gateway-instance")  # type: ignore[assignment]

    result = run_async(service._get_gateway_instance(PaymentGatewayType.PLATEGA))

    assert result == "gateway-instance"
    service.payment_gateway_factory.assert_called_once_with(gateway)

    service.get_by_type = AsyncMock(return_value=None)  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="Payment gateway of type 'PLATEGA' not found"):
        run_async(service._get_gateway_instance(PaymentGatewayType.PLATEGA))
