# AltShop Project Overview

Проверено по коду: `2026-03-08`

## Что Это

AltShop это backend и web interface для продажи и обслуживания VPN-подписок через Telegram bot, FastAPI API и отдельный React/Vite frontend. Внутренней VPN-панелью выступает Remnawave.

Важно: в текущем runtime нет отдельной web admin panel. Основная операторская админка встроена в Telegram dashboard.

## Текущий Стек

- Backend: Python 3.12, FastAPI, aiogram 3, aiogram-dialog, SQLAlchemy 2, Alembic
- Async и background: Valkey, Taskiq, asyncpg, httpx
- Auth и security: `python-jose`, bcrypt, cookie-based web auth, CSRF token
- Frontend: React 19, TypeScript 5.7, Vite 7, Tailwind CSS 4, TanStack Query, Zustand
- Infra: Docker Compose, Nginx, PostgreSQL 17, Valkey 9

## Ключевые Числа

| Метрика | Значение |
| --- | --- |
| Compose services в `docker-compose.yml` | 7 |
| HTTP route decorators в `src/api/endpoints` | 60 |
| Programmatic route | 1 (`TelegramWebhookEndpoint`) |
| Service modules в `src/services` | 42 |
| Concrete payment gateways | 14 |
| SQL-таблицы (`__tablename__`) | 23 |
| Alembic migrations | 45 |

## Структура Публичного Репозитория

```text
altshop/
|-- src/
|   |-- api/                   FastAPI app, endpoints, contracts, presenters
|   |-- bot/                   aiogram dispatcher, routers, middlewares, states
|   |-- core/                  config, enums, security, storage keys, utils
|   |-- infrastructure/        DI, database, Redis, Taskiq, payment gateways
|   |-- services/              application services
|   |-- __main__.py            локальный FastAPI и aiogram entrypoint
|   `-- lifespan.py            startup и shutdown orchestration
|-- assets/                    banners, translations, static assets
|-- docs/                      каноническая и историческая документация
|-- nginx/                     production Nginx config и SSL mount points
|-- scripts/                   maintenance и audit helpers
|-- web-app/                   React/Vite frontend
|-- docker-compose.yml         основной deployment contract
|-- docker-entrypoint.sh       миграции, инициализация assets, запуск uvicorn
|-- Makefile                   проектные команды для dev и DB lifecycle
`-- pyproject.toml             backend dependencies и tooling config
```

Внутренняя QA-папка `tests/` не входит в публичный GitHub mirror и остается локально.

## Runtime Contract

### Default Docker stack

Текущий `docker-compose.yml` описывает ровно 7 сервисов:

| Service | Роль |
| --- | --- |
| `webapp-build` | one-shot build `web-app/dist` перед запуском Nginx |
| `altshop-nginx` | SSL termination, раздача `/webapp/`, proxy к backend |
| `altshop-db` | PostgreSQL 17 |
| `altshop-redis` | Valkey 9 |
| `altshop` | основной backend process: FastAPI + aiogram + lifespan |
| `altshop-taskiq-worker` | background worker |
| `altshop-taskiq-scheduler` | scheduled jobs |

`admin-backend` и другие отдельные admin services в default compose отсутствуют.

### Backend entrypoints

- Локальный Python entrypoint: `src.__main__.application`
- Container entrypoint: `docker-entrypoint.sh`
- FastAPI app factory: `src/api/app.py:create_app`
- Lifespan orchestration: `src/lifespan.py`

### Web surface

- SPA раздается Nginx по `/webapp/`
- Статика раздается по `/assets/`
- API публикуется под `/api/v1`
- Telegram webhook идет через `/telegram`
- Remnawave webhook идет через `/remnawave`
- Payment webhooks идут через `/payments/*`

## Основные HTTP Surfaces

### Programmatic route

- `POST /api/v1/telegram`
  регистрируется через `TelegramWebhookEndpoint.register(...)` и проверяет `X-Telegram-Bot-Api-Secret-Token`

### Decorator-defined route groups

- `POST /api/v1/analytics/web-events`
- `GET /api/v1/auth/*`, `POST /api/v1/auth/*`
- `GET|PATCH|POST /api/v1/user/*`
- `GET|POST|PATCH|DELETE /api/v1/subscription/*`
- `GET|POST|DELETE /api/v1/devices*`
- `GET|POST /api/v1/referral/*`
- `GET|POST /api/v1/partner/*`
- `GET /api/v1/payments/yoomoney/redirect`
- `POST /api/v1/payments/{gateway_type}`
- `POST /api/v1/remnawave`

## Service Topology

В `src/services` находятся 42 service modules. Основные доменные зоны:

- Auth и access: `web_account.py`, `web_access_guard.py`, `auth_challenge.py`, `telegram_link.py`, `access.py`
- User и profile: `user.py`, `user_profile.py`, `user_activity_portal.py`, `notification.py`
- Subscription lifecycle: `subscription*.py`, `purchase_access.py`, `purchase_gateway_policy.py`
- Payments: `payment_gateway.py`, `payment_webhook_event.py`, `transaction.py`
- Referral и partner: `referral*.py`, `partner*.py`
- Ops и integrations: `backup.py`, `broadcast.py`, `command.py`, `importer.py`, `remnawave.py`, `settings.py`, `webhook.py`

Подробная карта находится в [03-services.md](03-services.md).

## Frontend Split

`web-app/` это отдельный Vite project, который:

- использует cookie-based auth против `/api/v1/auth/*`
- работает с backend через `axios` и `withCredentials`
- собирается отдельным сервисом `webapp-build`
- монтируется в Nginx как статический SPA bundle

## Проверять Дальше

- Архитектура и потоки: [02-architecture.md](02-architecture.md)
- API inventory: [05-api.md](05-api.md)
- Public contract: [API_CONTRACT.md](API_CONTRACT.md)
- Env и config: [08-configuration.md](08-configuration.md)
- Dev workflow: [10-development.md](10-development.md)
