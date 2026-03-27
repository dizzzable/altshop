# AltShop Backend Operator Guide

## Purpose

This document is the current operator-facing entrypoint for backend work. Use it before older
session reports, parity notes, or generated handoff documents.

## Runtime Shape

### Canonical API surfaces

- Web auth: `/api/v1/auth/*`
- User dashboard API: `/api/v1/*`
- Telegram webhook: `/api/v1/telegram`
- Remnawave webhook: `/api/v1/remnawave`
- Legacy `/auth/*` backend router is removed
- Docker runtime is built from `Dockerfile`

### Auth model

- Cookie-first web auth
- Session cookies are managed by `src/api/utils/web_auth_transport.py`
- Shared auth guards live in `src/api/dependencies/web_auth.py`
- Active account credentials live in `web_accounts`, not legacy `users.auth_username/password_hash`

### User endpoint split

- `src/api/endpoints/user_account.py`
- `src/api/endpoints/user_subscription.py`
- `src/api/endpoints/user_portal.py`

### Hot runtime services

- Subscription runtime cache: `src/services/subscription_runtime.py`
- Device cache/orchestration: `src/services/subscription_device.py`
- Purchase flow: `src/services/subscription_purchase.py`
- Referral and partner portals:
  - `src/services/referral_portal.py`
  - `src/services/partner_portal.py`

## Local Quality Gates

Use these commands on this workstation:

```powershell
uv sync --locked --group dev
uv run python -m ruff check src tests scripts
uv run python -m pytest -q
uv run python -m mypy src
uv run python scripts/verify_operator_docs.py
uv run python scripts/backend_audit_report.py
```

Notes:

- `uv` is the canonical Python toolchain locally and in CI
- `make backend-check` and `make docs-verify` wrap the same `uv`-based checks for CI or Git Bash automation
- `uv run python scripts/verify_operator_docs.py` is the direct PowerShell-friendly docs contract check

## Canonical Deploy Sequence

```powershell
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec altshop-nginx test -f /opt/altshop/webapp/index.html
```

Notes:

- `docker-compose.prod.yml` is the canonical VPS deploy contract and pulls release images from GHCR.
- `make run-local` is the source-build helper and maps to `docker-compose.yml`.
- `make run-prod` is the GHCR-backed helper and maps to `docker-compose.prod.yml`.
- `APP_DOMAIN` from `.env` is rendered into `server_name` inside `altshop-nginx` at container startup.
- `scripts/bootstrap-prod-vps.sh` is the one-time migration path for older manually deployed VPS hosts that do not have `docker-compose.prod.yml` yet.
- Certificates are expected on the host at `/opt/altshop/nginx/remnabot_fullchain.pem` and `/opt/altshop/nginx/remnabot_privkey.key` unless overridden via `NGINX_SSL_FULLCHAIN_PATH` and `NGINX_SSL_PRIVKEY_PATH`.
- After the first release publish, ensure `ghcr.io/dizzzable/altshop-backend` and `ghcr.io/dizzzable/altshop-nginx` are `Public` in GitHub Packages if you want anonymous pulls on the VPS.

Smoke checks:

```powershell
curl -I https://<host>/
curl -I https://<host>/webapp/
curl -I https://<host>/api/v1/auth/access-status
```

Notes:

- `401` from `/api/v1/auth/access-status` is acceptable for unauthenticated smoke

## Current Operational Checks

### Auth smoke

- register/login/bootstrap/refresh should only use `/api/v1/auth/*`
- JSON auth responses should not expose `access_token` or `refresh_token`
- session establishment should be verified through `Set-Cookie`

### Access-mode parity

When access mode changes in bot admin, verify:

- `REG_BLOCKED`: new registration returns `403`
- `INVITED`: new registration without valid invite returns `403`
- `PURCHASE_BLOCKED`: purchase routes return `403`, read-only routes still work
- `RESTRICTED`: non-privileged users lose protected API access

### Runtime/cache sanity

- `/subscription/list` should reuse runtime snapshot preparation
- device webhooks should update cached `devices_count`
- device-count updates should not refresh traffic/url freshness

## Highest-Value Next Steps

1. Keep cleaning stale backend docs and move non-canonical reports to archive.
2. Audit whether runtime and device caches should keep separate Redis boundaries.
3. Continue profiling `/subscription/list`, `/api/v1/auth/login`, and `/api/v1/user/me`.

## Canonical Supporting Docs

- [refactor-followup-2026-03-07.md](refactor-followup-2026-03-07.md)
- [optimization-plan-2026-03-06.md](optimization-plan-2026-03-06.md)
- [API_CONTRACT.md](API_CONTRACT.md)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- [09-deployment.md](09-deployment.md)
