# AltShop Backend Operator Guide

## Purpose

This document is the current operator-facing entrypoint for backend work. Use it before older
session reports, parity notes, or generated handoff documents.

## Runtime Shape

### Canonical API surfaces

- Web auth: `/api/v1/auth/*`
- User dashboard API: `/api/v1/*`
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
.\.venv\Scripts\ruff.exe check src tests scripts
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe scripts\backend_audit_report.py
```

Notes:

- `uv` is not required locally
- `pytest.exe` and `mypy.exe` can fail in this PowerShell with `Failed to canonicalize script path`
- prefer `.\.venv\Scripts\python.exe -m ...` for stable execution

## Canonical Deploy Sequence

```powershell
docker compose pull
docker compose up -d --build webapp-build
docker compose up -d --build altshop altshop-taskiq-worker altshop-taskiq-scheduler altshop-nginx
docker compose exec altshop-nginx test -f /opt/altshop/webapp/index.html
```

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
- [PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md)
