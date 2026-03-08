import types
from enum import Enum
from typing import Any, Union, get_args, get_origin

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, SubManager
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger
from pydantic import SecretStr, TypeAdapter, ValidationError

from src.bot.states import RemnashopGateways
from src.core.constants import USER_KEY
from src.core.enums import Currency
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.database.models.dto.payment_gateway import normalize_platega_payment_method
from src.services.notification import NotificationService
from src.services.payment_gateway import PaymentGatewayService
from src.services.settings import SettingsService


def _annotation_contains(annotation: Any, expected: type[Any]) -> bool:
    if annotation is expected:
        return True

    origin = get_origin(annotation)
    if origin in (types.UnionType, Union):
        return any(_annotation_contains(arg, expected) for arg in get_args(annotation))
    if origin is None:
        return False
    return any(_annotation_contains(arg, expected) for arg in get_args(annotation))


def _extract_enum_type(annotation: Any) -> type[Enum] | None:
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation

    origin = get_origin(annotation)
    if origin:
        for nested in get_args(annotation):
            enum_type = _extract_enum_type(nested)
            if enum_type is not None:
                return enum_type

    return None


def _is_optional_annotation(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is None:
        return False
    return type(None) in get_args(annotation)


def _convert_gateway_field_input(gateway_settings: Any, field_name: str, raw_value: str) -> Any:
    model_field = gateway_settings.__class__.model_fields.get(field_name)
    if model_field is None:
        raise ValueError(f"Unknown field '{field_name}'")

    value = raw_value.strip()
    if value == "" and _is_optional_annotation(model_field.annotation):
        return None

    if field_name == "payment_method":
        return normalize_platega_payment_method(value)

    if _annotation_contains(model_field.annotation, SecretStr):
        return SecretStr(value)

    try:
        return TypeAdapter(model_field.annotation).validate_python(value)
    except ValidationError as validation_error:
        enum_type = _extract_enum_type(model_field.annotation)
        if enum_type is None:
            raise validation_error

        try:
            return enum_type[value.upper()]
        except (KeyError, AttributeError):
            raise validation_error


@inject
async def on_gateway_select(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = sub_manager.middleware_data[USER_KEY]
    gateway_id = int(sub_manager.item_id)
    gateway = await payment_gateway_service.get(gateway_id)

    if not gateway:
        raise ValueError(f"Attempted to select non-existent gateway '{gateway_id}'")

    logger.info(f"{log(user)} Gateway '{gateway_id}' selected")

    if not gateway.settings:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-gateway-not-configurable"),
        )
        return

    sub_manager.manager.dialog_data["gateway_id"] = gateway_id
    await sub_manager.switch_to(state=RemnashopGateways.SETTINGS)


@inject
async def on_gateway_test(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = sub_manager.middleware_data[USER_KEY]
    gateway_id = int(sub_manager.item_id)
    gateway = await payment_gateway_service.get(gateway_id)

    if not gateway:
        raise ValueError(f"Attempted to test non-existent gateway '{gateway_id}'")

    if gateway.settings and not gateway.settings.is_configure:
        logger.warning(f"{log(user)} Gateway '{gateway_id}' is not configured")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-gateway-not-configured"),
        )
        return

    logger.info(f"{log(user)} Testing gateway '{gateway_id}'")

    try:
        payment = await payment_gateway_service.create_test_payment(user, gateway.type)
        logger.info(f"{log(user)} Test payment successful for gateway '{gateway_id}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-gateway-test-payment-created",
                i18n_kwargs={"url": payment.url},
            ),
        )

    except Exception as exception:
        logger.error(f"{log(user)} Test payment failed for gateway '{gateway_id}': {exception}")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-gateway-test-payment-error"),
        )
        return


@inject
async def on_active_toggle(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
) -> None:
    await sub_manager.load_data()
    user: UserDto = sub_manager.middleware_data[USER_KEY]
    gateway_id = int(sub_manager.item_id)
    gateway = await payment_gateway_service.get(gateway_id)

    if not gateway:
        raise ValueError(f"Attempted to toggle non-existent gateway '{gateway_id}'")

    if gateway.settings and not gateway.settings.is_configure:
        logger.warning(f"{log(user)} Gateway '{gateway_id}' is not configured")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-gateway-not-configured"),
        )
        return

    gateway.is_active = not gateway.is_active
    logger.info(f"{log(user)} Toggled active state for gateway '{gateway_id}'")
    await payment_gateway_service.update(gateway)


async def on_field_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_field: str,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    dialog_manager.dialog_data["selected_field"] = selected_field
    logger.info(f"{log(user)} Selected field '{selected_field}' for editing")
    await dialog_manager.switch_to(state=RemnashopGateways.FIELD)


@inject
async def on_field_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    gateway_id = dialog_manager.dialog_data["gateway_id"]
    selected_field = dialog_manager.dialog_data["selected_field"]

    if message.text is None:
        logger.warning(f"{log(user)} Empty input for field '{selected_field}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-gateway-field-wrong-value"),
        )
        return

    gateway = await payment_gateway_service.get(gateway_id)

    if not gateway or not gateway.settings:
        await dialog_manager.switch_to(state=RemnashopGateways.MAIN)
        raise ValueError(f"Attempted update of non-existent gateway '{gateway_id}'")

    try:
        input_value = _convert_gateway_field_input(gateway.settings, selected_field, message.text)
    except (ValueError, ValidationError) as exception:
        logger.warning(
            f"{log(user)} Invalid value '{message.text}' for '{selected_field}' on "
            f"gateway '{gateway_id}': {exception}"
        )
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-gateway-field-wrong-value"),
        )
        return

    setattr(gateway.settings, selected_field, input_value)
    logger.info(f"{log(user)} Updated '{selected_field}' for gateway '{gateway_id}'")
    await payment_gateway_service.update(gateway)
    await dialog_manager.switch_to(state=RemnashopGateways.SETTINGS)


@inject
async def on_default_currency_select(
    callback: CallbackQuery,
    widget: Select[Currency],
    dialog_manager: DialogManager,
    selected_currency: Currency,
    settings_service: FromDishka[SettingsService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Set default currency '{selected_currency}'")
    await settings_service.set_default_currency(selected_currency)


@inject
async def on_gateway_move(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
) -> None:
    await sub_manager.load_data()
    user: UserDto = sub_manager.middleware_data[USER_KEY]
    gateway_id = int(sub_manager.item_id)

    moved = await payment_gateway_service.move_gateway_up(gateway_id)
    if moved:
        logger.info(f"{log(user)} Moved plan '{gateway_id}' up successfully")
    else:
        logger.warning(f"{log(user)} Failed to move plan '{gateway_id}' up")
