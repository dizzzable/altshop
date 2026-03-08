# AltShop Documentation Index

Проверено по коду: `2026-03-08`

Это актуальная точка входа в документацию проекта.

- Источники истины для этой итерации: `src/`, `.env.example`, `docker-compose.yml`, `Makefile`, `web-app/package.json`, `nginx/nginx.conf`
- Каноническими считаются только документы из раздела `Canonical`
- Публичный GitHub-репозиторий не содержит внутреннюю QA-папку `tests/`; она остается в локальном приватном workspace

## Canonical

Эти файлы перепроверены по текущему коду и должны обновляться вместе с runtime-логикой.

| Документ | Что покрывает |
| --- | --- |
| [01-project-overview.md](01-project-overview.md) | Состав репозитория, стек, runtime-контракт, ключевые числа |
| [02-architecture.md](02-architecture.md) | Слои системы, DI, middleware chain, webhook и auth потоки |
| [03-services.md](03-services.md) | Сервисные модули, сгруппированные по доменам |
| [04-database.md](04-database.md) | SQL-таблицы, связи и Alembic migrations |
| [05-api.md](05-api.md) | Инвентарь HTTP endpoints, auth transport и route groups |
| [06-bot-dialogs.md](06-bot-dialogs.md) | Актуальные `StatesGroup` и пользовательские или admin сценарии |
| [07-payment-gateways.md](07-payment-gateways.md) | Concrete gateway implementations и webhook surface |
| [08-configuration.md](08-configuration.md) | Env matrix по config-моделям и `.env.example` |
| [09-deployment.md](09-deployment.md) | Текущий Docker и Nginx deployment contract |
| [10-development.md](10-development.md) | Реальный dev workflow: `uv`, `make`, public checks, private QA suite, npm scripts |
| [API_CONTRACT.md](API_CONTRACT.md) | Публичный контракт API с реальными request/response shapes |

## Auxiliary

Эти файлы могут быть полезны, но не считаются главным публичным контрактом проекта.

| Документ | Назначение |
| --- | --- |
| [BACKEND_OPERATOR_GUIDE.md](BACKEND_OPERATOR_GUIDE.md) | Операторские заметки по backend |
| [OPENAPI_GENERATION_SETUP.md](OPENAPI_GENERATION_SETUP.md) | Генерация OpenAPI и TypeScript SDK |
| [PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md) | Дополнительный deployment guide |
| [QUICK_START_API.md](QUICK_START_API.md) | Сокращенный старт по API |
| [SERVICE_INTEGRATION_GUIDE.md](SERVICE_INTEGRATION_GUIDE.md) | Интеграционные заметки по сервисам |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Сборник проблем и обходных путей |
| [WEB_APP_NGINX_SETUP.md](WEB_APP_NGINX_SETUP.md) | Дополнительные заметки по Nginx для web-app |
| [WEB_APP_SETUP.md](WEB_APP_SETUP.md) | Дополнительные заметки по web-app setup |
| [../QUICK_DEPLOY.md](../QUICK_DEPLOY.md) | Репозиторный quick deploy cheat sheet |

## Historical

Исторические файлы не нужно использовать как текущую спецификацию. Они сохранены ради истории решений, аудитов и этапов внедрения.

## Working Rules

При изменении runtime-кода:

1. Сначала обновляйте канонический документ из раздела `Canonical`.
2. Если комментарий в `.env.example` расходится с кодом, источником истины считается config-модель и фактическое использование в `src/`.
3. Исторические файлы не нужно синхронизировать с кодом.

## Quick Navigation

- Backend overview: [01-project-overview.md](01-project-overview.md)
- Architecture and flows: [02-architecture.md](02-architecture.md)
- Full endpoint inventory: [05-api.md](05-api.md)
- Public request/response contract: [API_CONTRACT.md](API_CONTRACT.md)
- Env and deployment: [08-configuration.md](08-configuration.md), [09-deployment.md](09-deployment.md)
- Developer workflow: [10-development.md](10-development.md)
