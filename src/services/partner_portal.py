from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from src.api.utils.user_identity import resolve_public_username
from src.api.utils.web_app_urls import build_web_referral_link
from src.core.config import AppConfig
from src.core.enums import (
    CryptoAsset,
    Currency,
    PartnerAccrualStrategy,
    PartnerLevel,
    PartnerRewardType,
)
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import (
    PartnerIndividualSettingsDto,
    PartnerReferralDto,
    PartnerSettingsDto,
    PartnerTransactionDto,
    PartnerWithdrawalDto,
    UserDto,
)

from .market_quote import MarketQuoteService
from .notification import NotificationService
from .partner import PartnerService
from .referral_portal import ReferralPortalService
from .web_account import WebAccountService

_WITHDRAWAL_STATUS_ALIASES = {
    "PENDING": "PENDING",
    "COMPLETED": "COMPLETED",
    "REJECTED": "REJECTED",
    "CANCELED": "CANCELED",
    "CANCELLED": "CANCELED",
    "APPROVED": "APPROVED",
}


class PartnerPortalError(Exception):
    """Base error for partner portal flows."""


class PartnerPortalNotPartnerError(PartnerPortalError):
    """Raised when a write operation requires an active partner record."""


class PartnerPortalStateError(PartnerPortalError):
    """Raised when the partner record is structurally invalid."""


class PartnerPortalWithdrawalDisabledError(PartnerPortalError):
    def __init__(self) -> None:
        self.code = "PARTNER_WITHDRAW_DISABLED"
        self.message = "Withdrawals are disabled for inactive partners"
        super().__init__(self.message)


class PartnerPortalBadRequestError(PartnerPortalError):
    """Raised for validation failures on partner actions."""


@dataclass(slots=True, frozen=True)
class PartnerLevelSettingSnapshot:
    level: int
    referrals_count: int
    earned_amount: int
    global_percent: float
    individual_percent: float | None
    individual_fixed_amount: int | None
    effective_percent: float | None
    effective_fixed_amount: int | None
    uses_global_value: bool


@dataclass(slots=True, frozen=True)
class PartnerInfoSnapshot:
    is_partner: bool
    is_active: bool
    can_withdraw: bool
    apply_support_url: str | None
    effective_currency: str
    min_withdrawal_rub: float
    min_withdrawal_display: float
    balance: int
    balance_display: float
    total_earned: int
    total_earned_display: float
    total_withdrawn: int
    total_withdrawn_display: float
    referrals_count: int
    level2_referrals_count: int
    level3_referrals_count: int
    referral_link: str | None
    telegram_referral_link: str | None
    web_referral_link: str | None
    use_global_settings: bool
    effective_reward_type: str
    effective_accrual_strategy: str
    level_settings: list[PartnerLevelSettingSnapshot]


@dataclass(slots=True, frozen=True)
class PartnerReferralItemSnapshot:
    telegram_id: int
    username: str | None
    name: str | None
    level: int
    joined_at: str
    invite_source: str
    is_active: bool
    is_paid: bool
    first_paid_at: str | None
    total_paid_amount: int
    total_paid_amount_display: float
    total_earned: int
    total_earned_display: float
    display_currency: str


@dataclass(slots=True, frozen=True)
class PartnerReferralsPageSnapshot:
    referrals: list[PartnerReferralItemSnapshot]
    total: int
    page: int
    limit: int


@dataclass(slots=True, frozen=True)
class PartnerEarningItemSnapshot:
    id: int
    referral_telegram_id: int
    referral_username: str | None
    level: int
    payment_amount: int
    payment_amount_display: float
    percent: float
    earned_amount: int
    earned_amount_display: float
    display_currency: str
    created_at: str


@dataclass(slots=True, frozen=True)
class PartnerEarningsPageSnapshot:
    earnings: list[PartnerEarningItemSnapshot]
    total: int
    page: int
    limit: int


@dataclass(slots=True, frozen=True)
class PartnerWithdrawalSnapshot:
    id: int
    amount: int
    display_amount: float
    display_currency: str
    requested_amount: float | None
    requested_currency: str | None
    quote_rate: float | None
    quote_source: str | None
    status: str
    method: str
    requisites: str
    admin_comment: str | None
    created_at: str
    updated_at: str


@dataclass(slots=True, frozen=True)
class PartnerWithdrawalsSnapshot:
    withdrawals: list[PartnerWithdrawalSnapshot]


class PartnerPortalService:
    def __init__(
        self,
        config: AppConfig,
        partner_service: PartnerService,
        referral_portal_service: ReferralPortalService,
        notification_service: NotificationService,
        web_account_service: WebAccountService,
        market_quote_service: MarketQuoteService,
    ) -> None:
        self.config = config
        self.partner_service = partner_service
        self.referral_portal_service = referral_portal_service
        self.notification_service = notification_service
        self.web_account_service = web_account_service
        self.market_quote_service = market_quote_service

    async def get_info(self, current_user: UserDto) -> PartnerInfoSnapshot:
        settings = await self.partner_service.settings_service.get()
        partner_settings = settings.partner
        min_withdrawal_rub = float(Decimal(partner_settings.min_withdrawal_amount) / Decimal(100))
        effective_currency = (
            await self.partner_service.settings_service.resolve_partner_balance_currency(
                current_user
            )
        )
        min_withdrawal_display = await self._convert_kopecks_to_display(
            partner_settings.min_withdrawal_amount,
            effective_currency,
        )
        support_username = self.config.bot.support_username.get_secret_value().strip().lstrip("@")
        apply_support_url = f"https://t.me/{support_username}" if support_username else None

        partner = await self.partner_service.get_partner_by_user(current_user.telegram_id)
        if not partner:
            return PartnerInfoSnapshot(
                is_partner=False,
                is_active=False,
                can_withdraw=False,
                apply_support_url=apply_support_url,
                effective_currency=effective_currency.value,
                min_withdrawal_rub=min_withdrawal_rub,
                min_withdrawal_display=float(min_withdrawal_display),
                balance=0,
                balance_display=0,
                total_earned=0,
                total_earned_display=0,
                total_withdrawn=0,
                total_withdrawn_display=0,
                referrals_count=0,
                level2_referrals_count=0,
                level3_referrals_count=0,
                referral_link=None,
                telegram_referral_link=None,
                web_referral_link=None,
                use_global_settings=True,
                effective_reward_type=PartnerRewardType.PERCENT.value,
                effective_accrual_strategy=PartnerAccrualStrategy.ON_EACH_PAYMENT.value,
                level_settings=[],
            )

        partner_stats = await self.partner_service.get_partner_statistics(partner=partner)
        current_user = await self.referral_portal_service.user_service.ensure_referral_code(
            current_user
        )
        telegram_referral_link = await self.referral_portal_service.referral_service.get_ref_link(
            current_user.referral_code
        )
        web_referral_link = build_web_referral_link(self.config, current_user.referral_code)

        individual_settings = partner.individual_settings
        use_global_settings = bool(individual_settings.use_global_settings)

        effective_reward_type = (
            PartnerRewardType.PERCENT if use_global_settings else individual_settings.reward_type
        )
        effective_accrual_strategy = (
            PartnerAccrualStrategy.ON_EACH_PAYMENT
            if use_global_settings
            else individual_settings.accrual_strategy
        )
        (
            balance_display,
            total_earned_display,
            total_withdrawn_display,
        ) = await self._convert_display_bundle(
            effective_currency=effective_currency,
            amounts_kopecks=(partner.balance, partner.total_earned, partner.total_withdrawn),
        )

        level_settings = [
            self._build_level_setting(
                level=level,
                referrals_count=referrals_count,
                earned_amount=earned_amount,
                partner_settings=partner_settings,
                use_global_settings=use_global_settings,
                individual_settings=individual_settings,
                effective_reward_type=effective_reward_type,
            )
            for level, referrals_count, earned_amount in [
                (
                    PartnerLevel.LEVEL_1,
                    partner.referrals_count,
                    int(partner_stats.get("level1_earnings", 0) or 0),
                ),
                (
                    PartnerLevel.LEVEL_2,
                    partner.level2_referrals_count,
                    int(partner_stats.get("level2_earnings", 0) or 0),
                ),
                (
                    PartnerLevel.LEVEL_3,
                    partner.level3_referrals_count,
                    int(partner_stats.get("level3_earnings", 0) or 0),
                ),
            ]
        ]

        return PartnerInfoSnapshot(
            is_partner=True,
            is_active=partner.is_active,
            can_withdraw=bool(
                partner.is_active and partner.balance >= partner_settings.min_withdrawal_amount
            ),
            apply_support_url=apply_support_url,
            effective_currency=effective_currency.value,
            min_withdrawal_rub=min_withdrawal_rub,
            min_withdrawal_display=float(min_withdrawal_display),
            balance=partner.balance,
            balance_display=float(balance_display),
            total_earned=partner.total_earned,
            total_earned_display=float(total_earned_display),
            total_withdrawn=partner.total_withdrawn,
            total_withdrawn_display=float(total_withdrawn_display),
            referrals_count=partner.referrals_count,
            level2_referrals_count=partner.level2_referrals_count,
                level3_referrals_count=partner.level3_referrals_count,
                referral_link=telegram_referral_link,
                telegram_referral_link=telegram_referral_link,
                web_referral_link=web_referral_link,
                use_global_settings=use_global_settings,
                effective_reward_type=effective_reward_type.value,
                effective_accrual_strategy=effective_accrual_strategy.value,
                level_settings=level_settings,
            )

    async def list_referrals(
        self,
        *,
        current_user: UserDto,
        page: int,
        limit: int,
    ) -> PartnerReferralsPageSnapshot:
        effective_currency = (
            await self.partner_service.settings_service.resolve_partner_balance_currency(
                current_user
            )
        )
        partner = await self.partner_service.get_partner_by_user(current_user.telegram_id)
        if not partner or not partner.id:
            return PartnerReferralsPageSnapshot(referrals=[], total=0, page=page, limit=limit)

        referrals = await self.partner_service.get_partner_referrals(partner.id)
        total = len(referrals)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_referrals = referrals[start_idx:end_idx]

        referral_telegram_ids = [ref.referral_telegram_id for ref in paginated_referrals]
        transaction_stats_map = await self.partner_service.get_partner_referral_transaction_stats(
            partner_id=partner.id,
            referral_telegram_ids=referral_telegram_ids,
        )
        invite_source_map = await self.partner_service.get_referral_invite_sources(
            referral_telegram_ids=referral_telegram_ids,
        )

        referral_items = [
            await self._build_referral_item(
                referral=ref,
                transaction_stats_map=transaction_stats_map,
                invite_source_map=invite_source_map,
                effective_currency=effective_currency,
            )
            for ref in paginated_referrals
        ]
        return PartnerReferralsPageSnapshot(
            referrals=referral_items,
            total=total,
            page=page,
            limit=limit,
        )

    async def list_earnings(
        self,
        *,
        current_user: UserDto,
        page: int,
        limit: int,
    ) -> PartnerEarningsPageSnapshot:
        effective_currency = (
            await self.partner_service.settings_service.resolve_partner_balance_currency(
                current_user
            )
        )
        partner = await self.partner_service.get_partner_by_user(current_user.telegram_id)
        if not partner:
            return PartnerEarningsPageSnapshot(earnings=[], total=0, page=page, limit=limit)
        if partner.id is None:
            raise PartnerPortalStateError("Partner record is missing id")

        transactions = await self.partner_service.get_partner_transactions(partner.id)
        total = len(transactions)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_transactions = transactions[start_idx:end_idx]

        earnings: list[PartnerEarningItemSnapshot] = []
        for txn in paginated_transactions:
            earnings.append(
                await self._build_earning_item(
                    txn,
                    effective_currency=effective_currency,
                )
            )

        return PartnerEarningsPageSnapshot(
            earnings=earnings,
            total=total,
            page=page,
            limit=limit,
        )

    async def request_withdrawal(
        self,
        *,
        current_user: UserDto,
        amount: Decimal,
        method: str,
        requisites: str,
    ) -> PartnerWithdrawalSnapshot:
        partner = await self.partner_service.get_partner_by_user(current_user.telegram_id)
        if not partner:
            raise PartnerPortalNotPartnerError("Not a partner")
        if partner.id is None:
            raise PartnerPortalStateError("Partner record is missing id")
        if not partner.is_active:
            raise PartnerPortalWithdrawalDisabledError()

        effective_currency = (
            await self.partner_service.settings_service.resolve_partner_balance_currency(
                current_user
            )
        )
        amount_input = self._normalize_display_amount(amount, effective_currency)
        if amount_input <= 0:
            raise PartnerPortalBadRequestError("Withdrawal amount must be positive")

        amount_rub, quote_rate, quote_source = await self._convert_display_amount_to_rub(
            amount=amount_input,
            source_currency=effective_currency,
        )
        amount_kopecks = self._rub_to_kopecks(amount_rub)
        withdrawal = await self.partner_service.create_withdrawal_request(
            partner_id=partner.id,
            amount=amount_rub,
            method=method.strip(),
            requisites=requisites.strip(),
            requested_amount=amount_input,
            requested_currency=effective_currency,
            quote_rate=quote_rate,
            quote_source=quote_source,
        )

        if not withdrawal:
            settings = await self.partner_service.settings_service.get()
            min_withdrawal_rub = Decimal(settings.partner.min_withdrawal_amount) / Decimal("100")

            if amount_kopecks < settings.partner.min_withdrawal_amount:
                raise PartnerPortalBadRequestError(
                    f"Minimum withdrawal amount is {min_withdrawal_rub}"
                )

            if amount_kopecks > partner.balance:
                available_rub = Decimal(partner.balance) / Decimal("100")
                raise PartnerPortalBadRequestError(
                    f"Insufficient balance. Available: {available_rub}"
                )

            raise PartnerPortalBadRequestError("Failed to create withdrawal request")

        await self._notify_withdrawal_requested(
            current_user=current_user,
            partner_balance_before=partner.balance,
            withdrawal=withdrawal,
        )

        return await self._serialize_withdrawal(
            withdrawal,
            effective_currency=effective_currency,
        )

    async def list_withdrawals(self, *, current_user: UserDto) -> PartnerWithdrawalsSnapshot:
        effective_currency = (
            await self.partner_service.settings_service.resolve_partner_balance_currency(
                current_user
            )
        )
        partner = await self.partner_service.get_partner_by_user(current_user.telegram_id)
        if not partner:
            return PartnerWithdrawalsSnapshot(withdrawals=[])
        if partner.id is None:
            raise PartnerPortalStateError("Partner record is missing id")

        withdrawals = await self.partner_service.get_partner_withdrawals(partner.id)
        return PartnerWithdrawalsSnapshot(
            withdrawals=[
                await self._serialize_withdrawal(
                    withdrawal,
                    effective_currency=effective_currency,
                )
                for withdrawal in withdrawals
            ]
        )

    async def _notify_withdrawal_requested(
        self,
        *,
        current_user: UserDto,
        partner_balance_before: int,
        withdrawal: PartnerWithdrawalDto,
    ) -> None:
        remaining_balance_kopecks = max(0, partner_balance_before - withdrawal.amount)
        amount_str = (
            f"{(Decimal(withdrawal.amount) / Decimal('100')).quantize(Decimal('0.01'))} RUB"
        )
        balance_str = (
            f"{(Decimal(remaining_balance_kopecks) / Decimal('100')).quantize(Decimal('0.01'))} RUB"
        )
        web_account = None
        if not current_user.username:
            web_account = await self.web_account_service.get_by_user_telegram_id(
                current_user.telegram_id
            )
        notification_username = resolve_public_username(current_user, web_account=web_account)

        await self.notification_service.notify_super_dev(
            MessagePayload(
                i18n_key="ntf-event-partner-withdrawal-request",
                i18n_kwargs={
                    "user_id": current_user.telegram_id,
                    "user_name": current_user.name or str(current_user.telegram_id),
                    "username": notification_username,
                    "amount": amount_str,
                    "partner_balance": balance_str,
                },
            )
        )

    def _build_level_setting(
        self,
        *,
        level: PartnerLevel,
        referrals_count: int,
        earned_amount: int,
        partner_settings: PartnerSettingsDto,
        use_global_settings: bool,
        individual_settings: PartnerIndividualSettingsDto,
        effective_reward_type: PartnerRewardType,
    ) -> PartnerLevelSettingSnapshot:
        global_percent = partner_settings.get_level_percent(level)
        individual_percent = (
            None if use_global_settings else individual_settings.get_level_percent(level)
        )
        raw_individual_fixed_amount = (
            None if use_global_settings else individual_settings.get_level_fixed_amount(level)
        )
        individual_fixed_amount = (
            raw_individual_fixed_amount
            if raw_individual_fixed_amount and raw_individual_fixed_amount > 0
            else None
        )

        effective_percent: Decimal | None = None
        effective_fixed_amount: int | None = None
        uses_global_value = use_global_settings

        if effective_reward_type == PartnerRewardType.FIXED_AMOUNT and individual_fixed_amount:
            effective_fixed_amount = individual_fixed_amount
            uses_global_value = False
        else:
            if use_global_settings:
                effective_percent = global_percent
            elif (
                effective_reward_type == PartnerRewardType.PERCENT
                and individual_percent is not None
            ):
                effective_percent = individual_percent
                uses_global_value = False
            else:
                effective_percent = global_percent
                uses_global_value = True

        return PartnerLevelSettingSnapshot(
            level=int(level.value),
            referrals_count=referrals_count,
            earned_amount=earned_amount,
            global_percent=float(global_percent),
            individual_percent=(
                float(individual_percent) if individual_percent is not None else None
            ),
            individual_fixed_amount=individual_fixed_amount,
            effective_percent=float(effective_percent) if effective_percent is not None else None,
            effective_fixed_amount=effective_fixed_amount,
            uses_global_value=uses_global_value,
        )

    async def _build_earning_item(
        self,
        txn: PartnerTransactionDto,
        *,
        effective_currency: Currency,
    ) -> PartnerEarningItemSnapshot:
        if txn.id is None:
            raise PartnerPortalStateError("Partner transaction is missing id")

        payment_amount_display, earned_amount_display = await self._convert_display_bundle(
            effective_currency=effective_currency,
            amounts_kopecks=(txn.payment_amount, txn.earned_amount),
        )
        return PartnerEarningItemSnapshot(
            id=txn.id,
            referral_telegram_id=txn.referral_telegram_id,
            referral_username=txn.referral.username if txn.referral else None,
            level=txn.level.value if hasattr(txn.level, "value") else int(txn.level),
            payment_amount=txn.payment_amount,
            payment_amount_display=float(payment_amount_display),
            percent=float(txn.percent),
            earned_amount=txn.earned_amount,
            earned_amount_display=float(earned_amount_display),
            display_currency=effective_currency.value,
            created_at=txn.created_at.isoformat() if txn.created_at else "",
        )

    async def _build_referral_item(
        self,
        *,
        referral: PartnerReferralDto,
        transaction_stats_map: dict[int, dict[str, Any]],
        invite_source_map: dict[int, str],
        effective_currency: Currency,
    ) -> PartnerReferralItemSnapshot:
        referred_user = referral.referral
        stats = transaction_stats_map.get(referral.referral_telegram_id, {})
        total_earned = int(stats.get("total_earned", 0) or 0)
        total_paid_amount = int(stats.get("total_paid_amount", 0) or 0)
        first_paid_at_obj = stats.get("first_paid_at")
        first_paid_at = first_paid_at_obj.isoformat() if first_paid_at_obj else None
        total_paid_display, total_earned_display = await self._convert_display_bundle(
            effective_currency=effective_currency,
            amounts_kopecks=(total_paid_amount, total_earned),
        )

        return PartnerReferralItemSnapshot(
            telegram_id=referral.referral_telegram_id,
            username=referred_user.username if referred_user else None,
            name=referred_user.name if referred_user else None,
            level=referral.level.value if hasattr(referral.level, "value") else int(referral.level),
            joined_at=referral.created_at.isoformat() if referral.created_at else "",
            invite_source=invite_source_map.get(referral.referral_telegram_id, "UNKNOWN"),
            is_active=(not referred_user.is_blocked) if referred_user else True,
            is_paid=total_paid_amount > 0,
            first_paid_at=first_paid_at,
            total_paid_amount=total_paid_amount,
            total_paid_amount_display=float(total_paid_display),
            total_earned=total_earned,
            total_earned_display=float(total_earned_display),
            display_currency=effective_currency.value,
        )

    async def _serialize_withdrawal(
        self,
        withdrawal: PartnerWithdrawalDto,
        *,
        effective_currency: Currency,
    ) -> PartnerWithdrawalSnapshot:
        if withdrawal.id is None:
            raise PartnerPortalStateError("Partner withdrawal is missing id")

        requested_amount = (
            float(withdrawal.requested_amount) if withdrawal.requested_amount is not None else None
        )
        requested_currency = (
            withdrawal.requested_currency.value
            if withdrawal.requested_currency is not None
            else None
        )
        display_amount_decimal = await self._convert_kopecks_to_display(
            withdrawal.amount,
            effective_currency,
        )
        status = (
            withdrawal.status.value
            if hasattr(withdrawal.status, "value")
            else str(withdrawal.status)
        )
        return PartnerWithdrawalSnapshot(
            id=withdrawal.id,
            amount=withdrawal.amount,
            display_amount=float(display_amount_decimal),
            display_currency=effective_currency.value,
            requested_amount=requested_amount,
            requested_currency=requested_currency,
            quote_rate=float(withdrawal.quote_rate) if withdrawal.quote_rate is not None else None,
            quote_source=withdrawal.quote_source,
            status=PartnerPortalService._normalize_withdrawal_status(status),
            method=withdrawal.method or "",
            requisites=withdrawal.requisites or "",
            admin_comment=withdrawal.admin_comment,
            created_at=withdrawal.created_at.isoformat() if withdrawal.created_at else "",
            updated_at=withdrawal.updated_at.isoformat() if withdrawal.updated_at else "",
        )

    @staticmethod
    def _normalize_withdrawal_status(status: str | None) -> str:
        if not status:
            return "PENDING"
        return _WITHDRAWAL_STATUS_ALIASES.get(status.upper(), status.upper())

    async def _convert_display_bundle(
        self,
        *,
        effective_currency: Currency,
        amounts_kopecks: tuple[int, ...],
    ) -> tuple[Decimal, ...]:
        return tuple(
            [
                await self._convert_kopecks_to_display(amount_kopecks, effective_currency)
                for amount_kopecks in amounts_kopecks
            ]
        )

    async def _convert_kopecks_to_display(
        self,
        amount_kopecks: int,
        effective_currency: Currency,
    ) -> Decimal:
        amount_rub = self._kopecks_to_rub_decimal(amount_kopecks)
        if effective_currency == Currency.RUB:
            return amount_rub
        conversion = await self.market_quote_service.convert_from_rub(
            amount_rub=amount_rub,
            target_currency=effective_currency,
        )
        return conversion.amount

    async def _convert_display_amount_to_rub(
        self,
        *,
        amount: Decimal,
        source_currency: Currency,
    ) -> tuple[Decimal, Decimal, str]:
        if source_currency == Currency.RUB:
            return (
                amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                Decimal("1"),
                "STATIC",
            )

        usd_rub_quote = await self.market_quote_service.get_usd_rub_quote()
        if source_currency == Currency.USD:
            return (
                (amount * usd_rub_quote.price).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                ),
                usd_rub_quote.price,
                usd_rub_quote.source,
            )

        asset_quote = await self.market_quote_service.get_asset_usd_quote(
            self._currency_to_asset(source_currency)
        )
        rub_per_asset = asset_quote.price * usd_rub_quote.price
        return (
            (amount * rub_per_asset).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            ),
            rub_per_asset,
            "+".join(part for part in (asset_quote.source, usd_rub_quote.source) if part),
        )

    @staticmethod
    def _currency_to_asset(currency: Currency) -> CryptoAsset:
        try:
            return CryptoAsset(currency.value)
        except ValueError as exception:
            raise PartnerPortalBadRequestError(
                f"Currency '{currency.value}' is not supported for partner balance quotes"
            ) from exception

    @staticmethod
    def _normalize_display_amount(amount: Decimal, currency: Currency) -> Decimal:
        if currency in {Currency.RUB, Currency.USD, Currency.USDT, Currency.USDC}:
            quantum = Decimal("0.01")
        elif currency == Currency.BTC:
            quantum = Decimal("0.00000001")
        else:
            quantum = Decimal("0.000001")
        return amount.quantize(quantum, rounding=ROUND_HALF_UP)

    @staticmethod
    def _kopecks_to_rub_decimal(amount_kopecks: int) -> Decimal:
        return (Decimal(amount_kopecks) / Decimal("100")).quantize(Decimal("0.01"))

    @staticmethod
    def _rub_to_kopecks(amount_rub: Decimal) -> int:
        return int((amount_rub * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
