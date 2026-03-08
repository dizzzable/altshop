# AltShop Project Overview

Проверено по коду: `2026-03-08`

## Что это

AltShop это backend и web interface для продажи и обслуживания VPN-подписок через Telegram bot, FastAPI API и отдельный React/Vite frontend. Внутренней VPN-панелью выступает Remnawave.

## Текущий стек

- Backend: Python 3.12, FastAPI, aiogram 3, aiogram-dialog, SQLAlchemy 2, Alembic
- Async/background: Redis/Valkey, Taskiq, asyncpg, httpx
- Auth/security: `python-jose`, bcrypt, cookie-based web auth, CSRF token
- Frontend: React 19, TypeScript 5.7, Vite 7, Tailwind CSS 4, TanStack Query, Zustand
- Infra: Docker Compose, Nginx, PostgreSQL 17, Valkey 9

## Ключевые числа

| Метрика | Значение |
| --- | --- |
| Compose services в `docker-compose.yml` | 7 |
| HTTP route decorators в `src/api/endpoints` | 60 |
| Programmatic route | 1 (`TelegramWebhookEndpoint`) |
| Service modules в `src/services` | 42 |
| Concrete payment gateways | 14 |
| SQL-таблицы (`__tablename__`) | 23 |
| Alembic migrations | 45 |
| Backend test files (`tests/test_*.py`) | 63 |

## Структура репозитория

```text
altshop/
├── src/
│   ├── api/                   FastAPI app, endpoints, contracts, presenters
│   ├── bot/                   aiogram dispatcher, routers, middlewares, states
│   ├── core/                  config, enums, security, storage keys, utils
│   ├── infrastructure/        DI, database, Redis, Taskiq, payment gateways
│   ├── services/              42 application services
│   ├── __main__.py            локальный FastAPI/aiogram entrypoint
│   └── lifespan.py            startup/shutdown orchestration
├── assets/                    banners, translations, static assets
├── docs/                      каноническая и историческая документация
├── nginx/                     production Nginx config и SSL mount points
├── tests/                     backend pytest suite
├── web-app/                   React/Vite frontend
├── docker-compose.yml         основной deployment contract
├── docker-entrypoint.sh       миграции, инициализация assets, запуск uvicorn
├── Makefile                   проектные команды для dev и DB lifecycle
└── pyproject.toml             backend dependencies и tooling config
```

## Runtime Contract

### Default Docker stack

Текущий `docker-compose.yml` описывает ровно 7 сервисов:

| Service | Роль |
| --- | --- |
| `webapp-build` | one-shot build `web-app/dist` перед запуском Nginx |
| `altshop-nginx` | SSL termination, раздача `/webapp/`, proxy к backend |
| `altshop-db` | PostgreSQL 17 |
| `altshop-redis` | Valkey 9 / Redis-compatible storage |
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

- SPA раздаётся Nginx по `/webapp/`
- Статика ассетов раздаётся по `/assets/`
- API публикуется под `/api/v1`
- Production build web-app собирается в `web-app/dist`

## Основные HTTP surfaces

### Programmatic route

- `POST /api/v1/telegram`
  - регистрируется через `TelegramWebhookEndpoint.register(...)`
  - проверяет `X-Telegram-Bot-Api-Secret-Token`

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

В `src/services` находится 42 service modules. Главные доменные зоны:

- Auth/access: `web_account.py`, `web_access_guard.py`, `auth_challenge.py`, `telegram_link.py`, `access.py`
- User/profile/activity: `user.py`, `user_profile.py`, `user_activity_portal.py`, `notification.py`, `user_notification_event.py`, `web_analytics_event.py`
- Subscription lifecycle: `subscription*.py`, `purchase_access.py`, `purchase_gateway_policy.py`
- Payments: `payment_gateway.py`, `payment_webhook_event.py`, `transaction.py`
- Referral/partner: `referral*.py`, `partner*.py`
- Ops/integration: `backup.py`, `broadcast.py`, `command.py`, `importer.py`, `remnawave.py`, `settings.py`, `webhook.py`

Подробная карта находится в [03-services.md](03-services.md).

## Frontend Split

`web-app/` это отдельный Vite project, который:

- использует cookie-based auth against `/api/v1/auth/*`
- работает с backend через `axios` + `withCredentials`
- собирается отдельно сервисом `webapp-build`
- монтируется в Nginx как статический SPA bundle

Исторические frontend planning-docs сохранены в [`docs/web-app/`](web-app/), но не являются текущей спецификацией.

## Проверять дальше

- Архитектура и потоки: [02-architecture.md](02-architecture.md)
- API inventory: [05-api.md](05-api.md)
- Public contract: [API_CONTRACT.md](API_CONTRACT.md)
- Env/config: [08-configuration.md](08-configuration.md)
