from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from src.core.enums import SubscriptionStatus
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanSnapshotDto,
    SubscriptionDto,
    UserDto,
    WebAccountDto,
)
from src.services.web_cabinet_admin import WebCabinetAdminService


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_user(telegram_id: int, name: str, current_subscription_id: int | None = None) -> UserDto:
    user = UserDto(telegram_id=telegram_id, name=name)
    if current_subscription_id is not None:
        user.current_subscription = SimpleNamespace(id=current_subscription_id)
    return user


def build_subscription(
    subscription_id: int, owner_telegram_id: int, plan_name: str
) -> SubscriptionDto:
    plan = PlanDto(
        id=subscription_id, name=plan_name, durations=[], allowed_user_ids=[], internal_squads=[]
    )
    return SubscriptionDto(
        id=subscription_id,
        user_remna_id=uuid4(),
        user_telegram_id=owner_telegram_id,
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=100,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now() + timedelta(days=30),
        url="https://example.test/sub",
        plan=PlanSnapshotDto.from_plan(plan, 30),
    )


def test_build_bind_preview_splits_web_and_telegram_subscriptions() -> None:
    source_user = build_user(-12, "web-user", current_subscription_id=1)
    target_user = build_user(12, "tg-user", current_subscription_id=2)
    web_account = WebAccountDto(id=7, user_telegram_id=-12, username="alice", password_hash="hash")
    source_subscription = build_subscription(1, -12, "Starter")
    target_subscription = build_subscription(2, 12, "Family")
    remnawave_service = SimpleNamespace(
        get_user=AsyncMock(
            side_effect=[
                SimpleNamespace(username="rs_web_sub"),
                SimpleNamespace(username="rs_tg_sub"),
            ]
        )
    )
    service = WebCabinetAdminService(
        user_service=SimpleNamespace(
            get=AsyncMock(
                side_effect=lambda telegram_id: source_user if telegram_id == -12 else target_user
            )
        ),
        web_account_service=SimpleNamespace(
            get_by_user_telegram_id=AsyncMock(return_value=web_account),
            inspect_telegram_account_occupancy=AsyncMock(
                return_value=SimpleNamespace(
                    web_account=None,
                    has_material_data=False,
                    is_reclaimable_provisional=False,
                )
            ),
        ),
        subscription_service=SimpleNamespace(
            get_all_by_user=AsyncMock(
                side_effect=lambda telegram_id: (
                    [source_subscription] if telegram_id == -12 else [target_subscription]
                )
            )
        ),
        remnawave_service=remnawave_service,
        telegram_link_service=SimpleNamespace(),
    )

    preview = run_async(
        service.build_bind_preview(source_user_telegram_id=-12, target_telegram_id=12)
    )

    assert preview.web_account.username == "alice"
    assert preview.target_bind_blocked_reason is None
    assert [item.subscription_id for item in preview.source_subscriptions] == [1]
    assert [item.subscription_id for item in preview.target_subscriptions] == [2]
    assert preview.source_subscriptions[0].profile_name == "rs_web_sub"
    assert preview.target_subscriptions[0].profile_name == "rs_tg_sub"


def test_build_bind_preview_marks_reclaimable_target_web_account() -> None:
    source_user = build_user(-12, "web-user")
    target_user = build_user(12, "tg-user")
    web_account = WebAccountDto(id=7, user_telegram_id=-12, username="alice", password_hash="hash")
    target_web_account = WebAccountDto(
        id=9,
        user_telegram_id=12,
        username="tg_12",
        password_hash="hash",
        credentials_bootstrapped_at=None,
    )
    service = WebCabinetAdminService(
        user_service=SimpleNamespace(
            get=AsyncMock(
                side_effect=lambda telegram_id: source_user if telegram_id == -12 else target_user
            )
        ),
        web_account_service=SimpleNamespace(
            get_by_user_telegram_id=AsyncMock(return_value=web_account),
            inspect_telegram_account_occupancy=AsyncMock(
                return_value=SimpleNamespace(
                    web_account=target_web_account,
                    has_material_data=False,
                    is_reclaimable_provisional=True,
                )
            ),
        ),
        subscription_service=SimpleNamespace(
            get_all_by_user=AsyncMock(return_value=[])
        ),
        remnawave_service=SimpleNamespace(get_user=AsyncMock(return_value=None)),
        telegram_link_service=SimpleNamespace(),
    )

    preview = run_async(
        service.build_bind_preview(source_user_telegram_id=-12, target_telegram_id=12)
    )

    assert preview.target_web_account is not None
    assert preview.target_account_reclaimable is True
    assert preview.target_bind_blocked_reason is None


def test_apply_bind_merge_deletes_unselected_and_reassigns_current_subscription() -> None:
    source_user = build_user(-12, "web-user", current_subscription_id=1)
    target_user = build_user(12, "tg-user", current_subscription_id=2)
    updated_account = WebAccountDto(
        id=7, user_telegram_id=12, username="alice", password_hash="hash"
    )
    kept_subscription = build_subscription(1, 12, "Starter")
    preview_service = WebCabinetAdminService(
        user_service=SimpleNamespace(
            get=AsyncMock(
                side_effect=lambda telegram_id: source_user if telegram_id == -12 else target_user
            ),
            create_placeholder_user=AsyncMock(),
            set_current_subscription=AsyncMock(),
            delete_current_subscription=AsyncMock(),
        ),
        web_account_service=SimpleNamespace(
            get_by_user_telegram_id=AsyncMock(
                return_value=WebAccountDto(
                    id=7, user_telegram_id=-12, username="alice", password_hash="hash"
                )
            ),
            inspect_telegram_account_occupancy=AsyncMock(
                return_value=SimpleNamespace(
                    web_account=None,
                    has_material_data=False,
                    is_reclaimable_provisional=False,
                )
            ),
            delete_reclaimable_account_for_telegram_id=AsyncMock(return_value=False),
        ),
        subscription_service=SimpleNamespace(
            get_all_by_user=AsyncMock(
                side_effect=[
                    [build_subscription(1, -12, "Starter")],
                    [build_subscription(2, 12, "Family")],
                    [kept_subscription],
                ]
            ),
            get_by_ids=AsyncMock(
                side_effect=[
                    [build_subscription(1, -12, "Starter"), build_subscription(2, 12, "Family")],
                    [kept_subscription],
                ]
            ),
            delete_subscription=AsyncMock(),
        ),
        remnawave_service=SimpleNamespace(
            get_user=AsyncMock(return_value=SimpleNamespace(username="rs_12_sub")),
            delete_user=AsyncMock(),
            updated_user=AsyncMock(),
            _pick_group_sync_current_subscription_id=staticmethod(
                lambda subs: subs[0].id if subs else None
            ),
        ),
        telegram_link_service=SimpleNamespace(
            bind_existing_account=AsyncMock(return_value=updated_account)
        ),
    )

    result = run_async(
        preview_service.apply_bind_merge(
            source_user_telegram_id=-12,
            target_telegram_id=12,
            kept_subscription_ids=[1],
        )
    )

    assert result.web_account.user_telegram_id == 12
    assert result.kept_subscription_ids == (1,)
    assert result.deleted_subscription_ids == (2,)
    preview_service.subscription_service.delete_subscription.assert_awaited_once_with(2)
    preview_service.telegram_link_service.bind_existing_account.assert_awaited_once_with(
        web_account_id=7, telegram_id=12
    )
    preview_service.user_service.set_current_subscription.assert_awaited_once_with(12, 1)


def test_apply_bind_merge_reclaims_provisional_target_account_before_bind() -> None:
    source_user = build_user(-12, "web-user", current_subscription_id=1)
    target_user = build_user(12, "tg-user")
    source_subscription = build_subscription(1, -12, "Starter")
    target_web_account = WebAccountDto(
        id=9,
        user_telegram_id=12,
        username="tg_12",
        password_hash="hash",
        credentials_bootstrapped_at=None,
    )
    updated_account = WebAccountDto(
        id=7,
        user_telegram_id=12,
        username="alice",
        password_hash="hash",
    )
    service = WebCabinetAdminService(
        user_service=SimpleNamespace(
            get=AsyncMock(
                side_effect=[source_user, target_user, source_user, target_user, target_user]
            ),
            create_placeholder_user=AsyncMock(),
            set_current_subscription=AsyncMock(),
            delete_current_subscription=AsyncMock(),
        ),
        web_account_service=SimpleNamespace(
            get_by_user_telegram_id=AsyncMock(
                return_value=WebAccountDto(
                    id=7, user_telegram_id=-12, username="alice", password_hash="hash"
                )
            ),
            inspect_telegram_account_occupancy=AsyncMock(
                return_value=SimpleNamespace(
                    web_account=target_web_account,
                    has_material_data=False,
                    is_reclaimable_provisional=True,
                )
            ),
            delete_reclaimable_account_for_telegram_id=AsyncMock(return_value=True),
        ),
        subscription_service=SimpleNamespace(
            get_all_by_user=AsyncMock(
                side_effect=[[source_subscription], [], [source_subscription]]
            ),
            get_by_ids=AsyncMock(side_effect=[[source_subscription], [source_subscription]]),
            delete_subscription=AsyncMock(),
        ),
        remnawave_service=SimpleNamespace(
            get_user=AsyncMock(return_value=None),
            delete_user=AsyncMock(),
            updated_user=AsyncMock(),
            _pick_group_sync_current_subscription_id=staticmethod(
                lambda subs: subs[0].id if subs else None
            ),
        ),
        telegram_link_service=SimpleNamespace(
            bind_existing_account=AsyncMock(return_value=updated_account)
        ),
    )

    result = run_async(
        service.apply_bind_merge(
            source_user_telegram_id=-12,
            target_telegram_id=12,
            kept_subscription_ids=[1],
        )
    )

    assert result.web_account.user_telegram_id == 12
    service.web_account_service.delete_reclaimable_account_for_telegram_id.assert_awaited_once_with(
        telegram_id=12,
        exclude_account_id=7,
    )
