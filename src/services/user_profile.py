from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import cast

from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import UserDto, WebAccountDto
from src.services.partner import PartnerService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.web_account import WebAccountService

_WEB_ACCOUNT_UNSET = object()


@dataclass(slots=True, frozen=True)
class UserProfileSnapshot:
    telegram_id: int
    username: str | None
    web_login: str | None
    name: str | None
    safe_name: str | None
    role: str
    points: int
    language: str
    default_currency: str
    personal_discount: int
    purchase_discount: int
    partner_balance_currency_override: str | None
    effective_partner_balance_currency: str
    is_blocked: bool
    is_bot_blocked: bool
    created_at: str
    updated_at: str
    email: str | None
    email_verified: bool
    telegram_linked: bool
    linked_telegram_id: int | None
    show_link_prompt: bool
    requires_password_change: bool
    effective_max_subscriptions: int
    active_subscriptions_count: int
    is_partner: bool
    is_partner_active: bool
    has_web_account: bool
    needs_web_credentials_bootstrap: bool


class UserProfileService:
    def __init__(
        self,
        web_account_service: WebAccountService,
        subscription_service: SubscriptionService,
        settings_service: SettingsService,
        partner_service: PartnerService,
    ) -> None:
        self.web_account_service = web_account_service
        self.subscription_service = subscription_service
        self.settings_service = settings_service
        self.partner_service = partner_service

    async def build_snapshot(
        self,
        *,
        user: UserDto,
        web_account: WebAccountDto | None | object = _WEB_ACCOUNT_UNSET,
    ) -> UserProfileSnapshot:
        if web_account is _WEB_ACCOUNT_UNSET:
            (
                resolved_web_account,
                subscriptions,
                max_subscriptions,
                default_currency,
                partner,
                effective_partner_balance_currency,
            ) = await asyncio.gather(
                self.web_account_service.get_by_user_telegram_id(user.telegram_id),
                self.subscription_service.get_all_by_user(user.telegram_id),
                self.settings_service.get_max_subscriptions_for_user(user),
                self.settings_service.get_default_currency(),
                self.partner_service.get_partner_by_user(user.telegram_id),
                self.settings_service.resolve_partner_balance_currency(user),
            )
        else:
            (
                subscriptions,
                max_subscriptions,
                default_currency,
                partner,
                effective_partner_balance_currency,
            ) = (
                await asyncio.gather(
                    self.subscription_service.get_all_by_user(user.telegram_id),
                    self.settings_service.get_max_subscriptions_for_user(user),
                    self.settings_service.get_default_currency(),
                    self.partner_service.get_partner_by_user(user.telegram_id),
                    self.settings_service.resolve_partner_balance_currency(user),
                )
            )
            resolved_web_account = cast(WebAccountDto | None, web_account)

        username = self._resolve_public_username(user, web_account=resolved_web_account)
        linked_telegram_id, email, email_verified, show_link_prompt, requires_password_change = (
            self._resolve_link_state(user, web_account=resolved_web_account)
        )

        return UserProfileSnapshot(
            telegram_id=user.telegram_id,
            username=username,
            web_login=resolved_web_account.username if resolved_web_account else None,
            name=user.name,
            safe_name=user.name or username,
            role=self._enum_value(user.role),
            points=user.points,
            language=self._enum_value(user.language),
            default_currency=self._enum_value(default_currency),
            personal_discount=user.personal_discount,
            purchase_discount=user.purchase_discount,
            partner_balance_currency_override=self._enum_value(
                user.partner_balance_currency_override
            )
            if user.partner_balance_currency_override is not None
            else None,
            effective_partner_balance_currency=self._enum_value(
                effective_partner_balance_currency
            ),
            is_blocked=user.is_blocked,
            is_bot_blocked=user.is_bot_blocked,
            created_at=user.created_at.isoformat() if user.created_at else "",
            updated_at=user.updated_at.isoformat() if user.updated_at else "",
            email=email,
            email_verified=email_verified,
            telegram_linked=linked_telegram_id is not None,
            linked_telegram_id=linked_telegram_id,
            show_link_prompt=show_link_prompt,
            requires_password_change=requires_password_change,
            effective_max_subscriptions=max(1, max_subscriptions),
            active_subscriptions_count=sum(
                1
                for subscription in subscriptions
                if not self._is_deleted_subscription_status(subscription.status)
            ),
            is_partner=partner is not None,
            is_partner_active=bool(partner and partner.is_active),
            has_web_account=resolved_web_account is not None,
            needs_web_credentials_bootstrap=bool(
                resolved_web_account is not None
                and resolved_web_account.credentials_bootstrapped_at is None
            ),
        )

    @staticmethod
    def _resolve_public_username(
        user: UserDto,
        *,
        web_account: WebAccountDto | None,
    ) -> str:
        if user.username:
            return user.username
        if web_account and web_account.username:
            return web_account.username
        return str(user.telegram_id)

    @staticmethod
    def _resolve_link_state(
        user: UserDto,
        *,
        web_account: WebAccountDto | None,
    ) -> tuple[int | None, str | None, bool, bool, bool]:
        linked_telegram_id: int | None = None
        email: str | None = None
        email_verified = False
        show_link_prompt = False
        requires_password_change = False

        if web_account:
            email = web_account.email
            email_verified = bool(web_account.email_verified_at)
            requires_password_change = web_account.requires_password_change
            if web_account.user_telegram_id > 0:
                linked_telegram_id = web_account.user_telegram_id
            else:
                show_link_prompt = (
                    web_account.link_prompt_snooze_until is None
                    or web_account.link_prompt_snooze_until <= datetime_now()
                )
        elif user.telegram_id > 0:
            linked_telegram_id = user.telegram_id

        return (
            linked_telegram_id,
            email,
            email_verified,
            show_link_prompt,
            requires_password_change,
        )

    @staticmethod
    def _is_deleted_subscription_status(status: object) -> bool:
        if hasattr(status, "value"):
            return str(getattr(status, "value")) == "DELETED"
        return str(status) == "DELETED"

    @staticmethod
    def _enum_value(value: object) -> str:
        if hasattr(value, "value"):
            return str(getattr(value, "value"))
        return str(value)
