from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from src.bot.routers.dashboard.users.user.subscription_selection import (
    clear_selected_subscription,
    get_subscription_index,
    resolve_selected_subscription,
    set_selected_subscription,
)
from src.core.enums import SubscriptionStatus
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto.plan import PlanSnapshotDto
from src.infrastructure.database.models.dto.subscription import SubscriptionDto


class DummyDialogManager:
    def __init__(self) -> None:
        self.dialog_data: dict[str, object] = {}


def _subscription(
    subscription_id: int,
    *,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    user_telegram_id: int = 1,
) -> SubscriptionDto:
    return SubscriptionDto(
        id=subscription_id,
        user_remna_id=uuid4(),
        user_telegram_id=user_telegram_id,
        status=status,
        traffic_limit=100,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now() + timedelta(days=30),
        url="https://example.test/sub",
        plan=PlanSnapshotDto.test(),
    )


def test_set_selected_subscription_uses_visible_index() -> None:
    dialog_manager = DummyDialogManager()
    subscriptions = [
        _subscription(1),
        _subscription(2, status=SubscriptionStatus.DELETED),
        _subscription(3),
    ]

    set_selected_subscription(dialog_manager, 3, subscriptions)

    assert dialog_manager.dialog_data["selected_subscription_id"] == 3
    assert dialog_manager.dialog_data["selected_subscription_index"] == 2


def test_resolve_selected_subscription_prefers_preferred_subscription() -> None:
    dialog_manager = DummyDialogManager()
    subscriptions = [_subscription(1), _subscription(2), _subscription(3)]

    visible_subscriptions, selected_subscription = resolve_selected_subscription(
        dialog_manager,
        subscriptions,
        preferred_subscription_id=2,
    )

    assert [subscription.id for subscription in visible_subscriptions] == [1, 2, 3]
    assert selected_subscription is not None
    assert selected_subscription.id == 2
    assert dialog_manager.dialog_data["selected_subscription_index"] == 2


def test_resolve_selected_subscription_replaces_stale_deleted_selection() -> None:
    dialog_manager = DummyDialogManager()
    dialog_manager.dialog_data["selected_subscription_id"] = 2

    subscriptions = [
        _subscription(1),
        _subscription(2, status=SubscriptionStatus.DELETED),
        _subscription(3),
    ]

    _, selected_subscription = resolve_selected_subscription(dialog_manager, subscriptions)

    assert selected_subscription is not None
    assert selected_subscription.id == 1
    assert dialog_manager.dialog_data["selected_subscription_id"] == 1


def test_clear_selected_subscription_removes_dialog_keys() -> None:
    dialog_manager = DummyDialogManager()
    dialog_manager.dialog_data["selected_subscription_id"] = 3
    dialog_manager.dialog_data["selected_subscription_index"] = 1

    clear_selected_subscription(dialog_manager)

    assert "selected_subscription_id" not in dialog_manager.dialog_data
    assert "selected_subscription_index" not in dialog_manager.dialog_data


def test_get_subscription_index_defaults_to_first_when_missing() -> None:
    subscriptions = [_subscription(10), _subscription(11)]

    assert get_subscription_index(999, subscriptions) == 1
