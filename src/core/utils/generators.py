import hashlib

from src.core.security.crypto import base62_encode


def generate_referral_code(telegram_id: int, secret: str, length: int = 6) -> str:
    data = f"{telegram_id}:{secret}".encode("utf-8")
    digest = hashlib.sha256(data).digest()
    code_int = int.from_bytes(digest[:6], "big")
    code = base62_encode(code_int)
    return code[:length].rjust(length, "0")
