from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.contracts.web_auth import (
    ForgotPasswordRequest,
    RegisterRequest,
    TelegramLinkConfirmPayload,
    VerifyEmailConfirmRequest,
)


def test_verify_email_confirm_request_requires_code_or_token() -> None:
    with pytest.raises(ValidationError):
        VerifyEmailConfirmRequest()


def test_verify_email_confirm_request_accepts_token() -> None:
    payload = VerifyEmailConfirmRequest(token="confirm-token")

    assert payload.token == "confirm-token"
    assert payload.code is None


def test_forgot_password_request_requires_username_or_email() -> None:
    with pytest.raises(ValidationError):
        ForgotPasswordRequest()


def test_register_request_rejects_non_positive_telegram_id() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(username="new_user", password="secret123", telegram_id=0)


def test_telegram_link_confirm_payload_enforces_code_length() -> None:
    with pytest.raises(ValidationError):
        TelegramLinkConfirmPayload(telegram_id=1001, code="123")
