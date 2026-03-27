# AltShop Project Overview

Last audited against the live repository: `2026-03-26`

## What this repository is

AltShop is a production-oriented stack for selling and servicing VPN subscriptions through three user-facing surfaces:

- a Telegram bot built on `aiogram`
- a FastAPI backend that exposes web auth, user API, webhooks, and internal endpoints
- a separate React/Vite web application served under `/webapp/`

There is no standalone web admin panel in the default runtime. Operator workflows live in the Telegram dashboard.

## Current stack

- Backend runtime: Python 3.12, FastAPI, aiogram 3, aiogram-dialog
- Persistence: PostgreSQL 17, SQLAlchemy 2, Alembic, asyncpg
- Background work: Taskiq, Valkey, Redis-compatible queues and caches
- Security: secure cookie-based web auth, CSRF header checks for unsafe methods, JWT access and refresh cookies
- Frontend: React 19, TypeScript 5.7, Vite 7, Tailwind CSS 4, React Router 7, TanStack Query 5, Zustand 5
- Edge and deployment: Docker Compose, Nginx, GHCR release images for production

## Key counts from the current codebase

| Metric | Value | Source |
| --- | --- | --- |
| Services in `docker-compose.yml` | 7 | `docker-compose.yml` |
| Decorator-defined HTTP routes | 64 | `src/api/endpoints/` |
| Programmatic HTTP routes | 1 | `src/api/endpoints/telegram.py` |
| Service modules in `src/services/` | 46 | `src/services/*.py` |
| Concrete payment gateway adapters | 14 | `src/infrastructure/payment_gateways/` |
| SQL tables | 25 | `src/infrastructure/database/models/sql/` |
| Alembic revisions | 50 | `src/infrastructure/database/migrations/versions/` |
| Python test files under `tests/` | 34 | `tests/` |

## Repository layout

```text
altshop/
|-- src/
|   |-- api/                   FastAPI app, endpoints, contracts, presenters
|   |-- bot/                   aiogram dispatcher, routers, middlewares, states
|   |-- core/                  config, enums, constants, security, utilities
|   |-- infrastructure/        DI, database, Redis, Taskiq, payment gateways
|   |-- services/              application services grouped by domain
|   |-- __main__.py            local backend entrypoint factory
|   `-- lifespan.py            startup and shutdown orchestration
|-- assets/                    translations, banners, runtime assets
|-- docs/                      canonical docs plus historical audits and handoffs
|-- nginx/                     Nginx config and container assets
|-- scripts/                   audit, release, and deployment helpers
|-- tests/                     backend and service test suite for this workspace
|-- web-app/                   standalone React/Vite frontend
|-- docker-compose.yml         build-based local and manual deployment stack
|-- docker-compose.prod.yml    GHCR-based production stack
|-- docker-entrypoint.sh       migrations, asset init, uvicorn startup
|-- Makefile                   local workflow and database commands
`-- pyproject.toml             backend package and tooling config
```

## Runtime contract

### Default build-based stack

`docker-compose.yml` defines these seven services:

| Service | Role |
| --- | --- |
| `webapp-build` | one-shot frontend build into `web-app/dist` |
| `altshop-nginx` | TLS termination, SPA hosting, reverse proxy |
| `altshop-db` | PostgreSQL 17 |
| `altshop-redis` | Valkey 9 |
| `altshop` | FastAPI app plus aiogram dispatcher runtime |
| `altshop-taskiq-worker` | background task worker |
| `altshop-taskiq-scheduler` | scheduled jobs |

### Backend entrypoints

- FastAPI app factory: `src/api/app.py:create_app`
- Local backend entrypoint: `src.__main__:application`
- Container entrypoint: `docker-entrypoint.sh`
- Startup and shutdown orchestration: `src/lifespan.py`

### Public HTTP surface

- `/webapp/` serves the React SPA
- `/api/v1/*` serves the decorator-defined FastAPI routes
- `/telegram` is the programmatic Telegram webhook route
- `/remnawave` is the Remnawave webhook route
- `/api/v1/payments/*` is the registered payment webhook and redirect surface

### Route groups

The current FastAPI app includes these route families:

- `POST /api/v1/analytics/web-events`
- `POST /api/v1/internal/release-notify`
- `GET|POST /api/v1/auth/*`
- `GET|PATCH|POST /api/v1/user/*`
- `GET|POST|PATCH|DELETE /api/v1/subscription/*`
- `GET|POST|DELETE /api/v1/devices*`
- `GET|POST /api/v1/referral/*`
- `GET|POST /api/v1/partner/*`
- `GET|POST /api/v1/payments/*`
- `POST /api/v1/remnawave`
- `POST /telegram`

## Service topology

`src/services/` is currently split into these main domains:

- Access and web auth: `access.py`, `access_policy.py`, `auth_challenge.py`, `telegram_link.py`, `web_access_guard.py`, `web_account.py`
- User and activity: `user.py`, `user_profile.py`, `user_activity_portal.py`, `notification.py`, `user_notification_event.py`, `web_analytics_event.py`
- Plans, purchases, and subscriptions: `plan.py`, `plan_catalog.py`, `pricing.py`, `purchase_access.py`, `purchase_gateway_policy.py`, `subscription*.py`
- Payments and transactions: `payment_gateway.py`, `payment_webhook_event.py`, `transaction.py`, `market_quote.py`
- Referral and partner flows: `referral*.py`, `partner*.py`, `promocode*.py`
- Operations and integrations: `backup.py`, `broadcast.py`, `command.py`, `importer.py`, `release_notification.py`, `remnawave.py`, `settings.py`, `webhook.py`

For a detailed module map, use [03-services.md](03-services.md).

## Frontend split

`web-app/` is a separate Vite project that:

- builds for the fixed production base path `/webapp/`
- talks to the backend through `/api/v1` with `axios` and `withCredentials`
- uses secure cookie auth with CSRF protection on unsafe methods
- supports browser login, Telegram widget login, and Telegram Mini App auto-auth

Use [`web-app/README.md`](../web-app/README.md) for current frontend-specific notes.

## Tests and CI

- The repository currently includes the backend and service test suite under `tests/`.
- `make backend-test` runs `pytest -q` when `tests/` is present and falls back to an informational message in stripped mirrors where it is absent.
- GitHub Actions in this repository run the frontend lint, type-check, and build workflow plus `make backend-check` for backend lint, pytest, and mypy.
- In stripped mirrors where `tests/` is absent, the backend CI job still runs, but the `make backend-test` portion becomes informational until that suite is available.

## Continue with

- Architecture and request flows: [02-architecture.md](02-architecture.md)
- Database inventory: [04-database.md](04-database.md)
- API inventory: [05-api.md](05-api.md)
- Env and deployment: [08-configuration.md](08-configuration.md), [09-deployment.md](09-deployment.md)
- Local workflow: [10-development.md](10-development.md)
