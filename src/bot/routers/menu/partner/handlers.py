from decimal import ROUND_HALF_UP, Decimal

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.bot.states import UserPartner
from src.core.constants import USER_KEY
from src.core.enums import Currency, UserNotificationType
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService
from src.services.partner import PartnerService
from src.services.partner_portal import PartnerPortalService
from src.services.settings import SettingsService
from src.services.user import UserService


def _currency_quantum(currency: Currency) -> Decimal:
    if currency == Currency.BTC:
        return Decimal("0.00000001")
    if currency in {
        Currency.TON,
        Currency.ETH,
        Currency.LTC,
        Currency.BNB,
        Currency.DASH,
        Currency.SOL,
        Currency.XMR,
        Currency.TRX,
    }:
        return Decimal("0.000001")
    return Decimal("0.01")


def _parse_amount(raw_value: str | None, currency: Currency) -> Decimal | None:
    if raw_value is None:
        return None

    normalized = raw_value.strip().replace(",", ".")
    if not normalized:
        return None

    try:
        amount = Decimal(normalized).quantize(
            _currency_quantum(currency),
            rounding=ROUND_HALF_UP,
        )
    except Exception:
        return None

    return amount if amount > 0 else None


def _format_amount(value: Decimal | float, currency: Currency) -> str:
    amount = Decimal(str(value)).quantize(_currency_quantum(currency), rounding=ROUND_HALF_UP)
    text = format(amount, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text} {currency.value}"


@inject
async def on_partner(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    partner_settings = await settings_service.get_partner_settings()
    if not partner_settings.is_enabled:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-disabled"),
        )
        return

    partner = await partner_service.get_partner_by_user(user.telegram_id)
    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    await dialog_manager.switch_to(state=UserPartner.MAIN)


@inject
async def on_withdraw(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    partner_portal_service: FromDishka[PartnerPortalService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    snapshot = await partner_portal_service.get_info(user)

    if not snapshot.is_partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    effective_currency = Currency(snapshot.effective_currency)
    if not snapshot.can_withdraw:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-partner-withdraw-min-not-reached",
                i18n_kwargs={
                    "min_withdrawal": _format_amount(
                        Decimal(str(snapshot.min_withdrawal_display)),
                        effective_currency,
                    )
                },
            ),
        )
        return

    dialog_manager.dialog_data["withdraw_amount"] = float(snapshot.balance_display)
    await dialog_manager.switch_to(state=UserPartner.WITHDRAW)


@inject
async def on_withdraw_amount_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    partner_portal_service: FromDishka[PartnerPortalService],
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    snapshot = await partner_portal_service.get_info(user)

    if not snapshot.is_partner:
        return

    effective_currency = Currency(snapshot.effective_currency)
    amount = _parse_amount(message.text, effective_currency)
    if amount is None:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-invalid-amount"),
        )
        return

    balance_display = Decimal(str(snapshot.balance_display))
    min_withdrawal_display = Decimal(str(snapshot.min_withdrawal_display))
    if amount > balance_display:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-withdraw-insufficient-balance"),
        )
        return

    if amount < min_withdrawal_display:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-partner-withdraw-min-not-reached",
                i18n_kwargs={
                    "min_withdrawal": _format_amount(
                        min_withdrawal_display,
                        effective_currency,
                    )
                },
            ),
        )
        return

    dialog_manager.dialog_data["withdraw_amount"] = float(amount)
    await dialog_manager.switch_to(state=UserPartner.WITHDRAW_CONFIRM)


@inject
async def on_withdraw_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    partner_portal_service: FromDishka[PartnerPortalService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    snapshot = await partner_portal_service.get_info(user)

    if not snapshot.is_partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    effective_currency = Currency(snapshot.effective_currency)
    amount = Decimal(str(dialog_manager.dialog_data.get("withdraw_amount", 0))).quantize(
        _currency_quantum(effective_currency),
        rounding=ROUND_HALF_UP,
    )
    if amount <= 0:
        return

    try:
        withdrawal = await partner_portal_service.request_withdrawal(
            current_user=user,
            amount=amount,
            method="",
            requisites="",
        )
    except Exception as exception:
        logger.exception("Error creating withdrawal request: {}", exception)
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error"),
        )
        return

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload.not_deleted(
            i18n_key="ntf-partner-withdraw-request-created",
        ),
        ntf_type=UserNotificationType.PARTNER_WITHDRAWAL_REQUEST_CREATED,
    )
    logger.info(
        "{} Created withdrawal request for {}, withdrawal_id={}",
        log(user),
        _format_amount(amount, effective_currency),
        withdrawal.id,
    )
    await dialog_manager.switch_to(state=UserPartner.MAIN)


@inject
async def on_withdraw_all(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    partner_portal_service: FromDishka[PartnerPortalService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    snapshot = await partner_portal_service.get_info(user)

    if not snapshot.is_partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    effective_currency = Currency(snapshot.effective_currency)
    if not snapshot.can_withdraw:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-partner-withdraw-min-not-reached",
                i18n_kwargs={
                    "min_withdrawal": _format_amount(
                        Decimal(str(snapshot.min_withdrawal_display)),
                        effective_currency,
                    )
                },
            ),
        )
        return

    dialog_manager.dialog_data["withdraw_amount"] = float(snapshot.balance_display)
    await dialog_manager.switch_to(state=UserPartner.WITHDRAW_CONFIRM)


@inject
async def on_partner_balance_currency_select(
    callback: CallbackQuery,
    widget: Select[str],
    dialog_manager: DialogManager,
    selected_currency: str,
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    override = None if selected_currency == "AUTO" else Currency(selected_currency)
    await user_service.set_partner_balance_currency_override(user, override)
    user.partner_balance_currency_override = override

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key="ntf-partner-balance-currency-updated",
            i18n_kwargs={"currency": override.value if override else "AUTO"},
        ),
    )
    await dialog_manager.switch_to(state=UserPartner.MAIN)
