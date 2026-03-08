from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.contracts.user_account import SetSecurityEmailRequest


def test_set_security_email_request_accepts_valid_email() -> None:
    payload = SetSecurityEmailRequest(email="user@example.com")

    assert payload.email == "user@example.com"


def test_set_security_email_request_rejects_short_email() -> None:
    with pytest.raises(ValidationError):
        SetSecurityEmailRequest(email="a@b")
