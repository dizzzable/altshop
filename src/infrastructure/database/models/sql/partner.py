from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from .user import User

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import PartnerLevel

from .base import BaseSql
from .timestamp import TimestampMixin


# Дефолтные индивидуальные настройки партнера
DEFAULT_PARTNER_INDIVIDUAL_SETTINGS: Dict[str, Any] = {
    "use_global_settings": True,
    "accrual_strategy": "ON_EACH_PAYMENT",
    "reward_type": "PERCENT",
    "level1_percent": None,
    "level2_percent": None,
    "level3_percent": None,
    "level1_fixed_amount": None,
    "level2_fixed_amount": None,
    "level3_fixed_amount": None,
}


class Partner(BaseSql, TimestampMixin):
    """Модель партнера - пользователь с активированной партнерской программой."""
    __tablename__ = "partners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    
    # Партнерский баланс (в копейках/центах для точности)
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_withdrawn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Статистика рефералов
    referrals_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level2_referrals_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level3_referrals_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Активность партнерки
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    # Индивидуальные настройки партнера (JSON)
    individual_settings: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=DEFAULT_PARTNER_INDIVIDUAL_SETTINGS,
    )
    
    # Связи
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_telegram_id],
        lazy="selectin",
    )
    
    transactions: Mapped[list["PartnerTransaction"]] = relationship(
        "PartnerTransaction",
        back_populates="partner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    withdrawals: Mapped[list["PartnerWithdrawal"]] = relationship(
        "PartnerWithdrawal",
        back_populates="partner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PartnerTransaction(BaseSql, TimestampMixin):
    """Транзакция партнера - начисление процента от оплаты реферала."""
    __tablename__ = "partner_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    partner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Пользователь, который оплатил (реферал)
    referral_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Уровень партнера (1, 2 или 3)
    level: Mapped[PartnerLevel] = mapped_column(
        Enum(
            PartnerLevel,
            name="partner_level",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    
    # Сумма оплаты от которой начислен процент (в копейках)
    payment_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Процент партнера на момент транзакции
    percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    
    # Начисленная сумма партнеру (в копейках)
    earned_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # ID транзакции оплаты (для связи)
    source_transaction_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Описание
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Связи
    partner: Mapped["Partner"] = relationship(
        "Partner",
        back_populates="transactions",
        foreign_keys=[partner_id],
        lazy="selectin",
    )
    
    referral: Mapped["User"] = relationship(
        "User",
        foreign_keys=[referral_telegram_id],
        lazy="selectin",
    )


class PartnerWithdrawal(BaseSql, TimestampMixin):
    """Вывод средств партнером."""
    __tablename__ = "partner_withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    partner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Сумма вывода (в копейках)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Статус вывода
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    
    # Способ вывода (например: card, usdt, bank_transfer)
    method: Mapped[str] = mapped_column(String, nullable=False)
    
    # Реквизиты для вывода
    requisites: Mapped[str] = mapped_column(String, nullable=False)
    
    # Комментарий администратора
    admin_comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # ID админа, обработавшего вывод
    processed_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    
    # Связи
    partner: Mapped["Partner"] = relationship(
        "Partner",
        back_populates="withdrawals",
        foreign_keys=[partner_id],
        lazy="selectin",
    )


class PartnerReferral(BaseSql, TimestampMixin):
    """Связь партнер -> реферал с указанием уровня."""
    __tablename__ = "partner_referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Партнер
    partner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Реферал (пользователь, пришедший по ссылке)
    referral_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Уровень (1 - прямой реферал, 2 - реферал реферала, 3 - третий уровень)
    level: Mapped[PartnerLevel] = mapped_column(
        Enum(
            PartnerLevel,
            name="partner_level",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    
    # Партнер 1-го уровня (если есть) - промежуточный партнер
    parent_partner_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("partners.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Связи
    partner: Mapped["Partner"] = relationship(
        "Partner",
        foreign_keys=[partner_id],
        lazy="selectin",
    )
    
    referral: Mapped["User"] = relationship(
        "User",
        foreign_keys=[referral_telegram_id],
        lazy="selectin",
    )