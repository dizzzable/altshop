from __future__ import annotations

import os


os.environ.setdefault("APP_DOMAIN", "example.com")
os.environ.setdefault("APP_CRYPT_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
os.environ.setdefault("APP_LOCALES", "en")
os.environ.setdefault("APP_ORIGINS", "")

os.environ.setdefault("BOT_TOKEN", "123456:TEST_TOKEN")
os.environ.setdefault("BOT_SECRET_TOKEN", "test-secret-token")
os.environ.setdefault("BOT_DEV_ID", "1")
os.environ.setdefault("BOT_SUPPORT_USERNAME", "support")

os.environ.setdefault("REMNAWAVE_TOKEN", "test-token")
os.environ.setdefault("REMNAWAVE_WEBHOOK_SECRET", "test-webhook-secret")

os.environ.setdefault("DATABASE_PASSWORD", "test-password")
os.environ.setdefault("REDIS_PASSWORD", "test-password")

os.environ.setdefault("WEB_APP_JWT_SECRET", "0123456789abcdef0123456789abcdef")
os.environ.setdefault("WEB_APP_API_SECRET_TOKEN", "0123456789abcdef")
os.environ.setdefault("WEB_APP_CORS_ORIGINS", "")
