"""Request contracts for web authentication endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.utils.validators import validate_web_login_or_raise


def _validate_and_normalize_web_login(value: str) -> str:
    return validate_web_login_or_raise(value)


class TelegramAuthRequest(BaseModel):
    id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int | None = None
    hash: str | None = None
    initData: str | None = None  # noqa: N815
    queryId: str | None = None  # noqa: N815
    isTest: bool | None = None  # noqa: N815
    referralCode: str | None = None  # noqa: N815


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    telegram_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, max_length=64)
    referral_code: str | None = None
    accept_rules: bool = False
    accept_channel_subscription: bool = False

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return _validate_and_normalize_web_login(value)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str


class WebAccountBootstrapRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return _validate_and_normalize_web_login(value)


class TelegramLinkRequestPayload(BaseModel):
    telegram_id: int = Field(ge=1)


class TelegramLinkConfirmPayload(BaseModel):
    telegram_id: int = Field(ge=1)
    code: str = Field(min_length=4, max_length=12)


class VerifyEmailConfirmRequest(BaseModel):
    code: str | None = None
    token: str | None = None

    @model_validator(mode="after")
    def _validate_payload(self) -> "VerifyEmailConfirmRequest":
        if not self.code and not self.token:
            raise ValueError("Provide code or token")
        return self


class ForgotPasswordRequest(BaseModel):
    username: str | None = None
    email: str | None = None

    @model_validator(mode="after")
    def _validate_payload(self) -> "ForgotPasswordRequest":
        if not self.username and not self.email:
            raise ValueError("Provide username or email")
        return self


class ResetPasswordByLinkRequest(BaseModel):
    token: str = Field(min_length=8)
    new_password: str = Field(min_length=6, max_length=128)


class ResetPasswordByCodeRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=6, max_length=128)


class ForgotPasswordTelegramRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)


class ResetPasswordByTelegramCodeRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=6, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


__all__ = [
    "ChangePasswordRequest",
    "ForgotPasswordRequest",
    "ForgotPasswordTelegramRequest",
    "LoginRequest",
    "RegisterRequest",
    "ResetPasswordByCodeRequest",
    "ResetPasswordByLinkRequest",
    "ResetPasswordByTelegramCodeRequest",
    "TelegramAuthRequest",
    "TelegramLinkConfirmPayload",
    "TelegramLinkRequestPayload",
    "VerifyEmailConfirmRequest",
    "WebAccountBootstrapRequest",
]
