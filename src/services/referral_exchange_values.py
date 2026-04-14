from __future__ import annotations

from src.core.enums import PointsExchangeType
from src.infrastructure.database.models.dto.settings import ExchangeTypeSettingsDto


def get_effective_points(*, user_points: int, max_points: int) -> int:
    if max_points > 0:
        return min(user_points, max_points)
    return user_points


def compute_value(
    exchange_type: PointsExchangeType,
    points: int,
    type_settings: ExchangeTypeSettingsDto,
) -> int:
    points_cost = type_settings.points_cost
    if points_cost <= 0:
        return 0

    if exchange_type == PointsExchangeType.SUBSCRIPTION_DAYS:
        return points // points_cost
    if exchange_type == PointsExchangeType.GIFT_SUBSCRIPTION:
        return type_settings.gift_duration_days if points >= points_cost else 0
    if exchange_type == PointsExchangeType.DISCOUNT:
        discount = points // points_cost
        if type_settings.max_discount_percent > 0:
            discount = min(discount, type_settings.max_discount_percent)
        return discount
    if exchange_type == PointsExchangeType.TRAFFIC:
        traffic = points // points_cost
        if type_settings.max_traffic_gb > 0:
            traffic = min(traffic, type_settings.max_traffic_gb)
        return traffic
    return 0
