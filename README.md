# AltShop

AltShop is a production-oriented VPN sales stack built around a Telegram bot, a FastAPI backend, and a separate React/Vite web app. The system integrates with Remnawave, serves a browser-based user portal, and ships with a Docker Compose deployment contract for PostgreSQL, Valkey, Nginx, background workers, and the frontend build pipeline.

## What is included

- Telegram bot runtime on `aiogram` 3
- FastAPI API with cookie-based web authentication and CSRF protection
- React 19 + TypeScript 5 + Vite 7 web application under [`web-app/`](./web-app)
- PostgreSQL migrations via Alembic
- Taskiq workers and scheduler for background jobs
- Production Nginx config for `/webapp/`, `/assets/`, API proxying, and HTTPS termination

## Stack

- Backend: Python 3.12, FastAPI, aiogram, SQLAlchemy, Alembic
- Frontend: React 19, TypeScript, Vite, Tailwind CSS 4, TanStack Query, Zustand
- Infra: Docker Compose, Nginx, PostgreSQL 17, Valkey 9
- Tooling: `uv`, Ruff, MyPy, Pytest, npm, GitHub Actions

## Repository layout

- [`src/`](./src) backend application code
- [`web-app/`](./web-app) standalone frontend project
- [`assets/`](./assets) runtime defaults: translations and default banners
- [`nginx/`](./nginx) Nginx config and local TLS mount points
- [`docs/`](./docs) canonical and historical project documentation

## Quick start

1. Copy environment variables:

   ```bash
   cp .env.example .env
   ```

2. Fill in the required secrets and deployment values in `.env`.

3. Place your TLS certificate files in:

   ```text
   nginx/fullchain.pem
   nginx/privkey.key
   ```

4. Build and start the stack:

   ```bash
   docker compose up --build
   ```

5. Open:

   - `https://<APP_DOMAIN>/webapp/` for the web app
   - `https://<APP_DOMAIN>/api/v1/auth/branding` to verify the API proxy path

## Local development

Backend:

```bash
uv sync --locked --group dev
uv run python -m ruff check src tests
uv run python -m pytest -q
uv run python -m mypy src
```

Frontend:

```bash
cd web-app
npm ci
npm run lint
npm run type-check
npm run build
```

## Documentation

Start from [`docs/README.md`](./docs/README.md). The most relevant canonical documents are:

- [`docs/01-project-overview.md`](./docs/01-project-overview.md)
- [`docs/05-api.md`](./docs/05-api.md)
- [`docs/08-configuration.md`](./docs/08-configuration.md)
- [`docs/09-deployment.md`](./docs/09-deployment.md)
- [`docs/10-development.md`](./docs/10-development.md)

## CI

GitHub Actions runs:

- backend Ruff checks
- backend Pytest suite
- backend MyPy
- frontend lint
- frontend type-check
- frontend build

## License

MIT, see [`LICENSE`](./LICENSE).
