from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.core.enums import SubscriptionStatus
from src.infrastructure.database.models.dto.subscription import SubscriptionDto

SELECTED_SUBSCRIPTION_ID_KEY = "selected_subscription_id"
SELECTED_SUBSCRIPTION_INDEX_KEY = "selected_subscription_index"


def get_visible_subscriptions(
    subscriptions: Sequence[SubscriptionDto],
) -> list[SubscriptionDto]:
    return [
        subscription
        for subscription in subscriptions
        if subscription.status != SubscriptionStatus.DELETED
    ]


def get_subscription_index(
    subscription_id: int | None,
    subscriptions: Sequence[SubscriptionDto],
) -> int:
    if subscription_id is None:
        return 1

    for index, subscription in enumerate(get_visible_subscriptions(subscriptions), start=1):
        if subscription.id == subscription_id:
            return index

    return 1


def set_selected_subscription(
    dialog_manager: Any,
    subscription_id: int,
    subscriptions: Sequence[SubscriptionDto],
) -> None:
    dialog_manager.dialog_data[SELECTED_SUBSCRIPTION_ID_KEY] = subscription_id
    dialog_manager.dialog_data[SELECTED_SUBSCRIPTION_INDEX_KEY] = get_subscription_index(
        subscription_id,
        subscriptions,
    )


def clear_selected_subscription(dialog_manager: Any) -> None:
    dialog_manager.dialog_data.pop(SELECTED_SUBSCRIPTION_ID_KEY, None)
    dialog_manager.dialog_data.pop(SELECTED_SUBSCRIPTION_INDEX_KEY, None)


def resolve_selected_subscription(
    dialog_manager: Any,
    subscriptions: Sequence[SubscriptionDto],
    preferred_subscription_id: int | None = None,
) -> tuple[list[SubscriptionDto], SubscriptionDto | None]:
    visible_subscriptions = get_visible_subscriptions(subscriptions)
    selected_subscription_id = dialog_manager.dialog_data.get(SELECTED_SUBSCRIPTION_ID_KEY)

    selected_subscription = next(
        (
            subscription
            for subscription in visible_subscriptions
            if subscription.id == selected_subscription_id
        ),
        None,
    )

    if selected_subscription is None and preferred_subscription_id is not None:
        selected_subscription = next(
            (
                subscription
                for subscription in visible_subscriptions
                if subscription.id == preferred_subscription_id
            ),
            None,
        )

    if selected_subscription is None and visible_subscriptions:
        selected_subscription = visible_subscriptions[0]

    if selected_subscription and selected_subscription.id is not None:
        set_selected_subscription(dialog_manager, selected_subscription.id, visible_subscriptions)
    else:
        clear_selected_subscription(dialog_manager)

    return visible_subscriptions, selected_subscription
