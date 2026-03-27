from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path


def build_smoke_values(*, fullchain_path: Path, privkey_path: Path) -> dict[str, str]:
    crypt_key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")

    return {
        "APP_DOMAIN": "altshop.local",
        "APP_ALLOWED_HOSTS": "altshop.local,localhost,127.0.0.1,::1",
        "APP_CRYPT_KEY": crypt_key,
        "APP_TRUSTED_PROXY_IPS": "127.0.0.1,::1",
        "BOT_TOKEN": "123456:smoke-token",
        "BOT_SECRET_TOKEN": "smoke-secret-token",
        "BOT_DEV_ID": "1",
        "BOT_SUPPORT_USERNAME": "altsupport",
        "BOT_SETUP_COMMANDS": "false",
        "BOT_SETUP_WEBHOOK": "false",
        "BOT_FETCH_ME_ON_STARTUP": "false",
        "BOT_RESET_WEBHOOK": "false",
        "WEB_APP_URL": "https://altshop.local/webapp",
        "WEB_APP_JWT_SECRET": "smoke-web-app-jwt-secret-0123456789",
        "WEB_APP_API_SECRET_TOKEN": "smoke-api-secret-token",
        "REMNAWAVE_TOKEN": "smoke-remnawave-token",
        "REMNAWAVE_WEBHOOK_SECRET": "smoke-remnawave-webhook-secret",
        "DATABASE_PASSWORD": "smoke-db-password",
        "REDIS_PASSWORD": "smoke-redis-password",
        "ALTSHOP_IMAGE_TAG": "ci-smoke",
        "ALTSHOP_NGINX_IMAGE_TAG": "ci-smoke",
        "NGINX_SSL_FULLCHAIN_PATH": str(fullchain_path.resolve()),
        "NGINX_SSL_PRIVKEY_PATH": str(privkey_path.resolve()),
    }


def render_env(template: str, replacements: dict[str, str]) -> str:
    rendered_lines: list[str] = []
    seen_keys: set[str] = set()

    for line in template.splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            rendered_lines.append(line)
            continue

        key, _, _value = line.partition("=")
        if key in replacements:
            rendered_lines.append(f"{key}={replacements[key]}")
            seen_keys.add(key)
        else:
            rendered_lines.append(line)

    for key in sorted(replacements.keys() - seen_keys):
        rendered_lines.append(f"{key}={replacements[key]}")

    return "\n".join(rendered_lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write a deterministic .env file for Docker contract smoke tests."
    )
    parser.add_argument("--template", type=Path, default=Path(".env.example"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fullchain-path", type=Path, required=True)
    parser.add_argument("--privkey-path", type=Path, required=True)
    args = parser.parse_args()

    template = args.template.read_text(encoding="utf-8")
    rendered = render_env(
        template,
        build_smoke_values(
            fullchain_path=args.fullchain_path,
            privkey_path=args.privkey_path,
        ),
    )
    args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
