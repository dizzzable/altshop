from aiogram import Router
from aiogram.filters import ExceptionTypeFilter
from aiogram_dialog.api.exceptions import (
    InvalidStackIdError,
    OutdatedIntent,
    UnknownIntent,
    UnknownState,
)

from src.bot.routers.extra.error import on_lost_context

from . import dashboard, extra, menu, subscription
from .dashboard import (
    access,
    broadcast,
    importer,
    promocodes,
    remnashop,
    remnawave,
    statistics,
    users,
)

__all__ = [
    "setup_routers",
]


def setup_routers(router: Router) -> None:
    # WARNING: The order of router registration matters!
    routers = [
        extra.payment.router,
        extra.notification.router,
        extra.test.router,
        extra.commands.router,
        extra.member.router,
        extra.goto.router,
        #
        menu.handlers.router,
        menu.dialog.router,
        #
        subscription.dialog.router,
        #
        dashboard.dialog.router,
        statistics.dialog.router,
        access.dialog.router,
        broadcast.dialog.router,
        promocodes.dialog.router,
        #
        remnashop.dialog.router,
        remnashop.banners.dialog.router,
        remnashop.gateways.dialog.router,
        remnashop.referral.dialog.router,
        remnashop.notifications.dialog.router,
        remnashop.plans.dialog.router,
        #
        remnawave.dialog.router,
        #
        importer.dialog.router,
        #
        users.dialog.router,
        users.user.dialog.router,
    ]

    router.include_routers(*routers)


def setup_error_handlers(router: Router) -> None:
    router.errors.register(on_lost_context, ExceptionTypeFilter(UnknownIntent))
    router.errors.register(on_lost_context, ExceptionTypeFilter(UnknownState))
    router.errors.register(on_lost_context, ExceptionTypeFilter(OutdatedIntent))
    router.errors.register(on_lost_context, ExceptionTypeFilter(InvalidStackIdError))
