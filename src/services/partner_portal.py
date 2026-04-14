from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from src.core.config import AppConfig
from src.core.enums import CryptoAsset, Currency, PartnerLevel, PartnerRewardType
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
from .partner_portal_info import _build_level_setting as _build_level_setting_impl
from .partner_portal_info import get_info as _get_info_impl
from .partner_portal_listing import _build_earning_item as _build_earning_item_impl
from .partner_portal_listing import _build_referral_item as _build_referral_item_impl
from .partner_portal_listing import _serialize_withdrawal as _serialize_withdrawal_impl
from .partner_portal_listing import list_earnings as _list_earnings_impl
from .partner_portal_listing import list_referrals as _list_referrals_impl
from .partner_portal_listing import list_withdrawals as _list_withdrawals_impl
from .partner_portal_models import (
    PartnerEarningItemSnapshot,
    PartnerEarningsPageSnapshot,
    PartnerInfoSnapshot,
    PartnerLevelSettingSnapshot,
    PartnerPortalBadRequestError,
    PartnerPortalError,
    PartnerPortalNotPartnerError,
    PartnerPortalStateError,
    PartnerPortalWithdrawalDisabledError,
    PartnerReferralItemSnapshot,
    PartnerReferralsPageSnapshot,
    PartnerWithdrawalSnapshot,
    PartnerWithdrawalsSnapshot,
)
from .partner_portal_withdrawals import (
    _notify_withdrawal_requested as _notify_withdrawal_requested_impl,
)
from .partner_portal_withdrawals import request_withdrawal as _request_withdrawal_impl
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

__all__ = [
    "PartnerEarningItemSnapshot",
    "PartnerEarningsPageSnapshot",
    "PartnerInfoSnapshot",
    "PartnerLevelSettingSnapshot",
    "PartnerPortalBadRequestError",
    "PartnerPortalError",
    "PartnerPortalNotPartnerError",
    "PartnerPortalService",
    "PartnerPortalStateError",
    "PartnerPortalWithdrawalDisabledError",
    "PartnerReferralItemSnapshot",
    "PartnerReferralsPageSnapshot",
    "PartnerWithdrawalSnapshot",
    "PartnerWithdrawalsSnapshot",
]


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
        return await _get_info_impl(self, current_user)

    async def list_referrals(
        self,
        *,
        current_user: UserDto,
        page: int,
        limit: int,
    ) -> PartnerReferralsPageSnapshot:
        return await _list_referrals_impl(
            self,
            current_user=current_user,
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
        return await _list_earnings_impl(
            self,
            current_user=current_user,
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
        return await _request_withdrawal_impl(
            self,
            current_user=current_user,
            amount=amount,
            method=method,
            requisites=requisites,
        )

    async def list_withdrawals(self, *, current_user: UserDto) -> PartnerWithdrawalsSnapshot:
        return await _list_withdrawals_impl(self, current_user=current_user)

    async def _notify_withdrawal_requested(
        self,
        *,
        current_user: UserDto,
        partner_balance_before: int,
        withdrawal: PartnerWithdrawalDto,
    ) -> None:
        return await _notify_withdrawal_requested_impl(
            self,
            current_user=current_user,
            partner_balance_before=partner_balance_before,
            withdrawal=withdrawal,
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
        return _build_level_setting_impl(
            self,
            level=level,
            referrals_count=referrals_count,
            earned_amount=earned_amount,
            partner_settings=partner_settings,
            use_global_settings=use_global_settings,
            individual_settings=individual_settings,
            effective_reward_type=effective_reward_type,
        )

    async def _build_earning_item(
        self,
        txn: PartnerTransactionDto,
        *,
        effective_currency: Currency,
    ) -> PartnerEarningItemSnapshot:
        return await _build_earning_item_impl(self, txn, effective_currency=effective_currency)

    async def _build_referral_item(
        self,
        *,
        referral: PartnerReferralDto,
        transaction_stats_map: dict[int, dict[str, object]],
        invite_source_map: dict[int, str],
        effective_currency: Currency,
    ) -> PartnerReferralItemSnapshot:
        return await _build_referral_item_impl(
            self,
            referral=referral,
            transaction_stats_map=transaction_stats_map,
            invite_source_map=invite_source_map,
            effective_currency=effective_currency,
        )

    async def _serialize_withdrawal(
        self,
        withdrawal: PartnerWithdrawalDto,
        *,
        effective_currency: Currency,
    ) -> PartnerWithdrawalSnapshot:
        return await _serialize_withdrawal_impl(
            self,
            withdrawal,
            effective_currency=effective_currency,
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
