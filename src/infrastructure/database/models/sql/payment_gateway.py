from typing import Optional

from sqlalchemy import JSON, Boolean, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.core.enums import Currency, PaymentGatewayType
from src.infrastructure.database.models.dto import AnyGatewaySettingsDto

from .base import BaseSql


class PaymentGateway(BaseSql):
    __tablename__ = "payment_gateways"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[PaymentGatewayType] = mapped_column(
        Enum(
            PaymentGatewayType,
            name="payment_gateway_type",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        unique=True,
    )
    currency: Mapped[Currency] = mapped_column(
        Enum(
            Currency,
            name="currency",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    settings: Mapped[Optional[AnyGatewaySettingsDto]] = mapped_column(JSON, nullable=True)
