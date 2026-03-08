<div align="center">
  <h1>AltShop</h1>
  <p><strong>Telegram-бот, FastAPI API и React web app для продажи VPN-подписок с интеграцией Remnawave.</strong></p>
  <p><a href="./README.md">ENGLISH</a> | РУССКИЙ</p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12" />
    <img src="https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white" alt="FastAPI Backend" />
    <img src="https://img.shields.io/badge/React-19-149ECA?logo=react&logoColor=white" alt="React 19" />
    <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose" />
    <img src="https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL 17" />
    <img src="https://img.shields.io/github/license/dizzzable/altshop" alt="MIT License" />
  </p>
</div>

## Что это

AltShop это production-ориентированный стек для продажи и обслуживания VPN-подписок. Репозиторий объединяет:

- Telegram-бота на `aiogram`
- FastAPI backend с cookie-based web auth
- отдельный React/Vite frontend
- PostgreSQL migrations, фоновые задачи и payment gateway integrations
- Docker Compose и Nginx deployment contract для production

Актуальная точка входа в документацию находится в [`docs/README.md`](./docs/README.md).

## Основные возможности

| Зона | Что есть в проекте |
| --- | --- |
| Bot runtime | Telegram bot flows, operator dialogs, access controls, notifications |
| Web app | React 19 портал пользователя: auth, subscriptions, devices, referral и partner страницы |
| Payments | Несколько payment gateways, webhook handling, quotes и purchase flows |
| Infrastructure | Docker Compose stack, Nginx reverse proxy, PostgreSQL 17, Valkey 9, Taskiq workers |
| Configuration | Большая `.env` matrix с готовой базой в [`.env.example`](./.env.example) |
| Documentation | Канонические документы по architecture, API, config, deployment и development в [`docs/`](./docs) |

## Стек

### Backend

- Python 3.12
- FastAPI
- aiogram 3 + aiogram-dialog
- SQLAlchemy 2 + Alembic
- asyncpg
- Taskiq

### Frontend

- React 19
- TypeScript 5
- Vite 7
- Tailwind CSS 4
- TanStack Query
- Zustand

### Infrastructure

- Docker Compose
- Nginx
- PostgreSQL 17
- Valkey 9
- GitHub Actions

## Структура репозитория

```text
altshop/
|-- src/                 backend application code
|-- web-app/             React/Vite frontend
|-- assets/              translations и default runtime assets
|-- nginx/               Nginx config и SSL mount paths
|-- docs/                canonical и historical documentation
|-- tests/               backend pytest suite
|-- docker-compose.yml   основной deployment contract
`-- Dockerfile           backend container image
```

## Быстрый старт

### 1. Подготовить окружение

```bash
cp .env.example .env
```

Минимально заполнить:

- `APP_DOMAIN`
- `APP_CRYPT_KEY`
- `BOT_TOKEN`
- `BOT_SECRET_TOKEN`
- `WEB_APP_JWT_SECRET`
- `REMNAWAVE_TOKEN`
- `REMNAWAVE_WEBHOOK_SECRET`
- `DATABASE_PASSWORD`
- `REDIS_PASSWORD`

### 2. Положить TLS-файлы

```text
nginx/fullchain.pem
nginx/privkey.key
```

### 3. Поднять стек

```bash
docker compose up --build
```

### 4. Проверить точки входа

- `https://<APP_DOMAIN>/webapp/`
- `https://<APP_DOMAIN>/api/v1/auth/branding`

## Локальная разработка

### Backend

```bash
uv sync --locked --group dev
uv run python -m pytest -q
```

### Frontend

```bash
cd web-app
npm ci
npm run lint
npm run type-check
npm run build
```

## Документация

Стартовая точка:

- [`docs/README.md`](./docs/README.md)

Канонические документы:

- [`docs/01-project-overview.md`](./docs/01-project-overview.md)
- [`docs/05-api.md`](./docs/05-api.md)
- [`docs/08-configuration.md`](./docs/08-configuration.md)
- [`docs/09-deployment.md`](./docs/09-deployment.md)
- [`docs/10-development.md`](./docs/10-development.md)

## CI

Сейчас GitHub Actions гоняет:

- backend `pytest`
- frontend `eslint`
- frontend `tsc --noEmit`
- frontend production build

## Лицензия

MIT. См. [`LICENSE`](./LICENSE).
