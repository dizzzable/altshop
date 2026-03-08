"""JWT token handling utilities."""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, cast

from jose import jwt
from jose.exceptions import JWTError

from src.core.config import AppConfig

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 10080  # 7 days
REFRESH_TOKEN_EXPIRE_DAYS = 30


def _get_webapp_jwt_secret() -> str:
    """
    Return WEB_APP_JWT_SECRET as plain string for python-jose.

    Raises:
        ValueError: If WEB_APP_JWT_SECRET is missing or has invalid type.
    """
    try:
        config = AppConfig.get()
        secret_value = config.web_app.jwt_secret.get_secret_value()
    except Exception as exc:
        raise ValueError(
            "WEB_APP_JWT_SECRET is not configured correctly. "
            "Ensure it is set and accessed via get_secret_value()."
        ) from exc

    if not isinstance(secret_value, str):
        raise ValueError(
            "WEB_APP_JWT_SECRET must be a string. Ensure it is accessed via get_secret_value()."
        )

    if not secret_value.strip():
        raise ValueError(
            "WEB_APP_JWT_SECRET is empty. "
            "Set WEB_APP_JWT_SECRET in environment to a non-empty string."
        )

    return secret_value


def _encode_token(payload: dict[str, Any], secret: str) -> str:
    encoded = cast(Any, jwt).encode(payload, secret, algorithm=ALGORITHM)
    return cast(str, encoded)


def _decode_token_payload(token: str, secret: str) -> dict[str, Any]:
    payload = cast(Any, jwt).decode(token, secret, algorithms=[ALGORITHM])
    return cast(dict[str, Any], payload)


def create_access_token(
    user_id: int,
    username: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
    token_version: int = 0,
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User's Telegram ID
        username: User's username
        expires_delta: Optional custom expiration time
        token_version: Current token_version of the user's web account

    Returns:
        Encoded JWT token string
    """
    secret = _get_webapp_jwt_secret()

    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode: dict[str, Any] = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
        "ver": token_version,
    }

    if username:
        to_encode["username"] = username

    return _encode_token(to_encode, secret)


def create_refresh_token(
    user_id: int,
    username: Optional[str] = None,
    token_version: int = 0,
) -> str:
    """
    Create a JWT refresh token.

    Args:
        user_id: User's Telegram ID
        username: User's username
        token_version: Current token_version of the user's web account

    Returns:
        Encoded JWT token string
    """
    secret = _get_webapp_jwt_secret()

    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode: dict[str, Any] = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "ver": token_version,
    }

    if username:
        to_encode["username"] = username

    return _encode_token(to_encode, secret)


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload or None if invalid
    """
    secret = _get_webapp_jwt_secret()

    try:
        payload = _decode_token_payload(token, secret)
        return payload
    except JWTError:
        return None


def verify_access_token(token: str) -> Optional[dict[str, Any]]:
    """
    Verify an access token.

    Args:
        token: JWT access token string

    Returns:
        Decoded payload if valid access token, None otherwise
    """
    payload = decode_token(token)

    if not payload:
        return None

    if payload.get("type") != "access":
        return None

    return payload


def verify_refresh_token(token: str) -> Optional[dict[str, Any]]:
    """
    Verify a refresh token.

    Args:
        token: JWT refresh token string

    Returns:
        Decoded payload if valid refresh token, None otherwise
    """
    payload = decode_token(token)

    if not payload:
        return None

    if payload.get("type") != "refresh":
        return None

    return payload
