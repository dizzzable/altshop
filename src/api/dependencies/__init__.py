"""Shared API dependency helpers."""

from src.api.dependencies.web_auth import (
    get_current_user,
    get_current_web_account,
    require_web_product_access,
)

__all__ = [
    "get_current_user",
    "get_current_web_account",
    "require_web_product_access",
]
