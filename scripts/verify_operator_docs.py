from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DocCheck:
    path: str
    required: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()


CHECKS: tuple[DocCheck, ...] = (
    DocCheck(
        path="README.md",
        required=(
            "/api/v1/telegram",
            "/api/v1/remnawave",
            "uv run python scripts/verify_operator_docs.py",
        ),
        forbidden=(
            "- `/telegram` for Telegram webhook traffic",
            "- `/remnawave` for Remnawave webhook traffic",
        ),
    ),
    DocCheck(
        path="docs/05-api.md",
        required=(
            "`POST` | `/api/v1/telegram`",
            "`POST` | `/api/v1/remnawave`",
            "X-CSRF-Token",
        ),
        forbidden=("`POST` | `/telegram`",),
    ),
    DocCheck(
        path="docs/08-configuration.md",
        required=(
            "APP_ORIGINS",
            "BOT_FETCH_ME_ON_STARTUP",
            "WebhookService.setup()",
            "runtime correction",
            "`WEB_APP_JWT_EXPIRY`",
            "`WEB_APP_JWT_REFRESH_ENABLED`",
            "`WEB_APP_API_SECRET_TOKEN`",
        ),
    ),
    DocCheck(
        path="docs/09-deployment.md",
        required=(
            "/api/v1/auth/webapp-shell",
            "/api/v1/telegram",
            "/api/v1/remnawave",
            "/api/v1/payments/{gateway_type}",
            "make run-local",
            "make run-prod",
        ),
    ),
    DocCheck(
        path="docs/BACKEND_OPERATOR_GUIDE.md",
        required=(
            "uv sync --locked --group dev",
            "uv run python scripts/verify_operator_docs.py",
            "/api/v1/telegram",
            "/api/v1/remnawave",
        ),
        forbidden=(
            "`uv` is not required locally",
            "PRODUCTION_DEPLOYMENT_GUIDE.md",
        ),
    ),
    DocCheck(
        path="docs/README.md",
        required=(
            "Legacy one-off docs `PRODUCTION_DEPLOYMENT_GUIDE.md`, `WEB_APP_SETUP.md`, and `WEB_APP_NGINX_SETUP.md` were removed on `2026-03-27`",
        ),
        forbidden=(
            "[PRODUCTION_DEPLOYMENT_GUIDE.md]",
            "[WEB_APP_SETUP.md]",
            "[WEB_APP_NGINX_SETUP.md]",
        ),
    ),
)


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []

    for check in CHECKS:
        text = read_text(check.path)

        for snippet in check.required:
            if snippet not in text:
                failures.append(f"{check.path}: missing required snippet {snippet!r}")

        for snippet in check.forbidden:
            if snippet in text:
                failures.append(f"{check.path}: found forbidden stale snippet {snippet!r}")

    if failures:
        print("Operator doc verification failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Operator doc verification passed for {len(CHECKS)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
