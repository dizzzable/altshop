# AltShop Development

Last audited against the live repository: `2026-03-26`

## Sources of truth

- `pyproject.toml`
- `Makefile`
- `src/__main__.py`
- `src/infrastructure/database/alembic.ini`
- `web-app/package.json`
- `web-app/vite.config.ts`
- `.github/workflows/ci.yml`

## Current repository reality

- `tests/` is present in this workspace and is part of the current repository audit
- `make backend-test` runs `pytest -q` when `tests/` exists
- the same Make target falls back to an informational message in stripped mirrors where `tests/` is absent
- GitHub Actions in this repository validate the frontend workflow plus `make backend-check`

## Toolchain

- Python: `>=3.12`
- Backend package manager and runner: `uv`
- Frontend runtime and package manager: `Node.js` and `npm`
- Frontend dev server: `Vite 7`
- Backend static checks: `ruff`, `mypy`
- Backend test runner: `pytest`

## Recommended local setup

### 1. Install backend dependencies

```bash
uv sync --locked --group dev
```

Optional shell activation on Windows:

```bash
.venv\Scripts\activate
```

On Unix-like shells:

```bash
source .venv/bin/activate
```

### 2. Copy the environment file

```bash
cp .env.example .env
```

Minimum values you usually need to fill manually:

- `APP_DOMAIN`
- `APP_CRYPT_KEY`
- `APP_ORIGINS`
- `WEB_APP_JWT_SECRET`
- `DATABASE_PASSWORD`
- `REDIS_PASSWORD`
- `BOT_TOKEN`
- `BOT_SECRET_TOKEN`
- `REMNAWAVE_TOKEN`
- `REMNAWAVE_WEBHOOK_SECRET`

### 3. Start PostgreSQL and Valkey

```bash
docker compose up -d altshop-db altshop-redis
```

If you use external PostgreSQL or Redis, configure the `DATABASE_*` and `REDIS_*` variables in `.env` instead.

### 4. Apply database migrations

```bash
uv run alembic -c src/infrastructure/database/alembic.ini upgrade head
```

Or via `make`:

```bash
make migrate
```

### 5. Run the backend

Preferred dev command for frontend proxy compatibility:

```bash
uv run uvicorn src.__main__:application --factory --reload --host 0.0.0.0 --port 5000
```

`python -m src` is also valid, but the explicit `uvicorn` command is the clearest path for local web-app work.

### 6. Run the frontend

```bash
cd web-app
npm ci
npm run dev
```

Important frontend runtime facts:

- Vite dev server listens on `3000`
- the dev proxy forwards `/api` to `http://localhost:5000`
- the production `base` remains `/webapp/`

## Backend commands

### Static checks

```bash
uv run python -m ruff check src tests
uv run python -m mypy src
```

`make` wrappers:

```bash
make backend-lint
make backend-typecheck
make backend-check
```

`make backend-lint` dynamically includes `tests/` only when the directory exists.

### Tests

```bash
make backend-test
uv run python -m pytest -q
```

The Makefile behavior is conditional:

- if `tests/` exists, it runs `pytest -q`
- if `tests/` is missing, it prints a mirror note instead of failing immediately

## Frontend commands

Current scripts from `web-app/package.json`:

| Script | Purpose |
| --- | --- |
| `npm run dev` | Vite dev server |
| `npm run build` | production build |
| `npm run postbuild` | post-process built asset paths |
| `npm run preview` | preview the built frontend |
| `npm run lint` | ESLint |
| `npm run type-check` | TypeScript type-check |
| `npm run check:encoding` | encoding guard |
| `npm run check:i18n` | i18n parity guard |
| `npm run generate:api` | generate TS client from `http://localhost:5000/openapi.json` |
| `npm run generate:api:download` | download `openapi.json`, then generate the client |

Recommended local frontend loop:

1. Run the backend on `localhost:5000`
2. In `web-app/`, run `npm run dev`
3. Use `npm run lint` and `npm run type-check` while iterating
4. Run `npm run build` before merging frontend changes

## Full-stack smoke workflow

Minimal local workflow without production Nginx:

```bash
docker compose up -d altshop-db altshop-redis
uv run alembic -c src/infrastructure/database/alembic.ini upgrade head
uv run uvicorn src.__main__:application --factory --reload --host 0.0.0.0 --port 5000
cd web-app && npm ci && npm run dev
curl -fsS http://127.0.0.1:5000/api/v1/health/livez
curl -fsS http://127.0.0.1:5000/api/v1/internal/readiness
curl -fsS http://127.0.0.1:5000/api/v1/internal/metrics | grep subscription_runtime_refresh_failures_total
```

Production-like compose smoke:

```bash
docker compose up --build webapp-build
docker compose up -d --build
docker compose ps
```

## CI scope

`.github/workflows/ci.yml` currently runs the frontend job plus a backend quality gate:

- `npm ci`
- `npm run lint`
- `npm run type-check`
- `npm run build`
- `uv sync --locked --group dev`
- `make backend-check`

In stripped mirrors where `tests/` is absent, `make backend-test` prints an informational note instead of running `pytest`, so the backend CI job still executes but its test leg is informational until that suite is present.

## Notes

- `APP_ORIGINS` is required for real browser auth flows even if some older notes treat it as optional
- `WEB_APP_JWT_SECRET` is required for local web auth work, not just production
- `make setup-env` uses BSD-style `sed -i ''` and is not portable without adjustment on all shells
- `web-app/README.md` is the current frontend-specific guide; root-level web-app markdowns other than that file are historical notes
