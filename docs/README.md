# AltShop Documentation Index

Last audited against the live repository: `2026-03-27`

This index is the entry point for the current AltShop documentation set. It tracks which files are canonical, which ones are historical, and which code paths must be checked before changing a document.

## Sources of truth

- Runtime code: `src/`
- Database schema and history: `src/infrastructure/database/models/sql/`, `src/infrastructure/database/migrations/versions/`
- Configuration: `src/core/config/`, `.env.example`
- Deployment contract: `docker-compose.yml`, `docker-compose.prod.yml`, `nginx/nginx.conf`, `Dockerfile`, `docker-entrypoint.sh`, `.github/workflows/release.yml`
- Frontend runtime: `web-app/src/`, `web-app/package.json`, `web-app/vite.config.ts`

## Canonical docs

These files should be updated together with the runtime behavior they describe.

| Document | Purpose | Primary source of truth |
| --- | --- | --- |
| [01-project-overview.md](01-project-overview.md) | Repository shape, stack, runtime contract, key counts | `pyproject.toml`, `web-app/package.json`, `docker-compose*.yml`, `src/api/app.py` |
| [02-architecture.md](02-architecture.md) | System layers, DI, middleware, auth and webhook flows | `src/api/`, `src/infrastructure/di/`, `src/lifespan.py` |
| [03-services.md](03-services.md) | Service map grouped by domain | `src/services/` |
| [04-database.md](04-database.md) | SQL models, table inventory, migration history | `src/infrastructure/database/models/sql/`, `src/infrastructure/database/migrations/versions/` |
| [05-api.md](05-api.md) | Route inventory, auth transport, webhook and internal endpoints | `src/api/endpoints/`, `src/api/contracts/`, `src/api/dependencies/` |
| [06-bot-dialogs.md](06-bot-dialogs.md) | Bot states and user or operator flows | `src/bot/routers/`, `src/bot/states.py` |
| [07-payment-gateways.md](07-payment-gateways.md) | Gateway implementations and webhook processing | `src/infrastructure/payment_gateways/`, `src/api/endpoints/payments.py` |
| [08-configuration.md](08-configuration.md) | Environment variables and config model mapping | `src/core/config/`, `.env.example` |
| [09-deployment.md](09-deployment.md) | Docker, GHCR, Nginx, VPS deployment contract | `docker-compose*.yml`, `nginx/nginx.conf`, `scripts/bootstrap-prod-vps.sh`, `.github/workflows/release.yml` |
| [10-development.md](10-development.md) | Local setup, checks, CI scope, frontend workflow | `Makefile`, `pyproject.toml`, `web-app/package.json`, `.github/workflows/ci.yml` |
| [API_CONTRACT.md](API_CONTRACT.md) | Request and response shapes for public API consumers | `src/api/contracts/`, `src/api/presenters/`, `src/api/endpoints/` |

## Documentation ownership map

Use this map when deciding which document to update after a code change.

| Path | Update when this changes | Audit against |
| --- | --- | --- |
| [`README.md`](../README.md) | External project summary, repo layout, deployment entrypoint | Root runtime and deployment files |
| [`01-project-overview.md`](01-project-overview.md) | Stack, counts, high-level runtime boundaries | `src/`, compose files, frontend package |
| [`04-database.md`](04-database.md) | Models, tables, migrations, persistence additions | SQL models and Alembic revisions |
| [`05-api.md`](05-api.md) | Endpoint inventory, auth transport, hidden routes, internal endpoints | `src/api/endpoints/`, contracts, dependencies |
| [`07-payment-gateways.md`](07-payment-gateways.md) | Gateway roster, webhook behavior, redirect flow | `src/infrastructure/payment_gateways/`, `src/api/endpoints/payments.py` |
| [`08-configuration.md`](08-configuration.md) | Environment variables and config flags | `src/core/config/`, `.env.example` |
| [`09-deployment.md`](09-deployment.md) | Containers, Nginx routes, GHCR deployment, VPS bootstrap | Compose, Nginx, release workflow, bootstrap script |
| [`10-development.md`](10-development.md) | Local commands, lint, type-check, pytest, frontend workflow | `Makefile`, `pyproject.toml`, `web-app/package.json`, CI workflow |
| [`web-app/README.md`](../web-app/README.md) | Current frontend runtime, route map, auth behavior, dev workflow | `web-app/src/`, `web-app/package.json`, `web-app/vite.config.ts` |

## Frontend markdowns

- [`web-app/README.md`](../web-app/README.md) is the current frontend entry point.
- [`web-app/AUTH_SYSTEM.md`](../web-app/AUTH_SYSTEM.md), [`web-app/FIX_SUMMARY.md`](../web-app/FIX_SUMMARY.md), and [`web-app/LANDING_PAGE.md`](../web-app/LANDING_PAGE.md) are historical implementation notes. Re-audit them before treating them as current runtime documentation.
- `docs/web-app/` contains planning and implementation notes for the web client. Treat it as project history unless a file is explicitly re-audited.

## Auxiliary docs

These files are useful, but they are not the primary public contract.

| Document | Use |
| --- | --- |
| [BACKEND_OPERATOR_GUIDE.md](BACKEND_OPERATOR_GUIDE.md) | Operator-oriented backend notes |
| [OPENAPI_GENERATION_SETUP.md](OPENAPI_GENERATION_SETUP.md) | OpenAPI and TypeScript client generation |
| [QUICK_START_API.md](QUICK_START_API.md) | Short API onboarding path |
| [SERVICE_INTEGRATION_GUIDE.md](SERVICE_INTEGRATION_GUIDE.md) | Integration notes for external services |
| [SERVICE_INTEGRATION_STATUS.md](SERVICE_INTEGRATION_STATUS.md) | Snapshot of integration coverage |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Failure modes and recovery notes |

## Historical docs

Files under `docs/archive/` and dated audit or handoff notes in `docs/` are preserved for implementation history. Do not treat them as the current runtime contract unless they are explicitly refreshed against code.

Legacy one-off docs `PRODUCTION_DEPLOYMENT_GUIDE.md`, `WEB_APP_SETUP.md`, and `WEB_APP_NGINX_SETUP.md` were removed on `2026-03-27` after their surviving runtime guidance was folded into `README.md`, `05-api.md`, `08-configuration.md`, `09-deployment.md`, and `BACKEND_OPERATOR_GUIDE.md`.

## Working rules

1. Update the canonical document that owns the changed runtime behavior.
2. When `.env.example` comments disagree with config code, prefer `src/core/config/` and real runtime usage.
3. `tests/` exists in this workspace and is part of the current repository audit. `make backend-test` also handles stripped mirrors where the directory is absent.
4. Keep historical notes, but mark them clearly if they no longer describe the live codebase.
