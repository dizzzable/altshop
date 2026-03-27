from aiogram import Dispatcher
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.api.endpoints import (
    TelegramWebhookEndpoint,
    analytics_router,
    health_router,
    internal_router,
    payments_router,
    remnawave_router,
    user_router,
    web_auth_router,
)
from src.core.config import AppConfig
from src.lifespan import lifespan


def configure_http_middleware(app: FastAPI, config: AppConfig) -> None:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=config.resolved_allowed_hosts,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def create_app(config: AppConfig, dispatcher: Dispatcher) -> FastAPI:
    app: FastAPI = FastAPI(lifespan=lifespan)
    configure_http_middleware(app=app, config=config)
    app.include_router(analytics_router)
    app.include_router(health_router)
    app.include_router(internal_router)
    app.include_router(payments_router)
    app.include_router(remnawave_router)
    app.include_router(web_auth_router)  # Web app authentication
    app.include_router(user_router)  # User API (subscriptions, devices, referrals, partner)

    telegram_webhook_endpoint = TelegramWebhookEndpoint(
        dispatcher=dispatcher,
        secret_token=config.bot.secret_token.get_secret_value(),
    )
    telegram_webhook_endpoint.register(app=app, path=config.bot.webhook_path)
    app.state.telegram_webhook_endpoint = telegram_webhook_endpoint
    app.state.dispatcher = dispatcher
    app.state.config = config

    return app
