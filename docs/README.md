# AltShop Documentation Index

Актуальная точка входа в документацию проекта.

- Проверено по коду: `2026-03-08`
- Источники истины для этой итерации: `src/`, `.env.example`, `docker-compose.yml`, `Makefile`, `web-app/package.json`, `nginx/nginx.conf`
- Каноническими считаются только документы из раздела `Canonical`

## Canonical

Эти файлы были переаудированы по текущему коду и должны обновляться вместе с runtime-логикой.

| Документ | Что покрывает |
| --- | --- |
| [01-project-overview.md](01-project-overview.md) | Состав репозитория, стек, runtime-контракт, ключевые числа |
| [02-architecture.md](02-architecture.md) | Слои системы, DI, middleware chain, webhook и auth потоки |
| [03-services.md](03-services.md) | 42 service modules, сгруппированные по доменам |
| [04-database.md](04-database.md) | 23 SQL-таблицы, связи, 45 Alembic migrations |
| [05-api.md](05-api.md) | Полный inventory HTTP endpoints, auth transport и route groups |
| [06-bot-dialogs.md](06-bot-dialogs.md) | Актуальные `StatesGroup` и пользовательские/admin сценарии |
| [07-payment-gateways.md](07-payment-gateways.md) | 14 concrete gateway implementations и webhook surface |
| [08-configuration.md](08-configuration.md) | Env matrix по config-моделям и `.env.example` |
| [09-deployment.md](09-deployment.md) | Текущий Docker/Nginx deployment contract |
| [10-development.md](10-development.md) | Реальный dev workflow: `uv`, `make`, `pytest`, `ruff`, `mypy`, npm scripts |
| [API_CONTRACT.md](API_CONTRACT.md) | Публичный контракт API с реальными request/response shapes |

## Auxiliary (Not Reviewed In This Pass)

Эти файлы могут быть полезны, но в этой итерации не проверялись на полное соответствие текущему коду.

| Документ | Назначение |
| --- | --- |
| [BACKEND_OPERATOR_GUIDE.md](BACKEND_OPERATOR_GUIDE.md) | Операторские заметки по backend |
| [BOT_WEB_PARITY_IMPLEMENTATION.md](BOT_WEB_PARITY_IMPLEMENTATION.md) | История выравнивания bot/web features |
| [OPENAPI_GENERATION_SETUP.md](OPENAPI_GENERATION_SETUP.md) | Генерация OpenAPI и TypeScript SDK |
| [PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md) | Дополнительный deployment guide |
| [QUICK_START_API.md](QUICK_START_API.md) | Сокращённый старт по API |
| [SERVICE_INTEGRATION_GUIDE.md](SERVICE_INTEGRATION_GUIDE.md) | Интеграционные заметки по сервисам |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Сборник проблем и обходных путей |
| [WEB_APP_NGINX_SETUP.md](WEB_APP_NGINX_SETUP.md) | Дополнительные заметки по Nginx для web-app |
| [WEB_APP_SETUP.md](WEB_APP_SETUP.md) | Дополнительные заметки по web-app setup |
| [../QUICK_DEPLOY.md](../QUICK_DEPLOY.md) | Репозиторный quick deploy cheat sheet |

## Historical

Эти файлы не следует использовать как текущую спецификацию. Они сохранены ради истории решений, аудитов и этапов внедрения.

| Путь | Статус |
| --- | --- |
| [web-app/](web-app/) | Исторический пакет документов про первоначальное внедрение frontend |
| [DOCUMENTATION_UPDATE_ACT.md](DOCUMENTATION_UPDATE_ACT.md) | Исторический отчёт о предыдущем проходе по документации |
| [DOCUMENTATION_UPDATE_REPORT.md](DOCUMENTATION_UPDATE_REPORT.md) | Исторический отчёт о предыдущем проходе по документации |
| [project-audit-2026-03-06.md](project-audit-2026-03-06.md) | Снимок аудита на 2026-03-06 |
| [backend-followup-2026-03-06.md](backend-followup-2026-03-06.md) | Исторический follow-up |
| [refactor-followup-2026-03-07.md](refactor-followup-2026-03-07.md) | Исторический follow-up |
| [optimization-plan-2026-03-06.md](optimization-plan-2026-03-06.md) | Исторический optimisation plan |
| [PROMOCODE_E2E_AUDIT.md](PROMOCODE_E2E_AUDIT.md) | Исторический audit |
| [SERVICE_INTEGRATION_STATUS.md](SERVICE_INTEGRATION_STATUS.md) | Исторический status snapshot |
| [wave3-lint-burndown-2026-03-06.md](wave3-lint-burndown-2026-03-06.md) | Исторический lint snapshot |
| [../web-app/README.md](../web-app/README.md) | Исторический README frontend-подпроекта |

## Working Rules

При изменении runtime-кода:

1. Сначала обновляйте канонический документ из раздела `Canonical`.
2. Если комментарий в `.env.example` расходится с кодом, источником истины считается config-модель и фактическое использование в `src/`.
3. Исторические файлы не нужно синхронизировать с кодом; достаточно баннера и корректной классификации в этом индексе.

## Quick Navigation

- Backend overview: [01-project-overview.md](01-project-overview.md)
- Architecture and flows: [02-architecture.md](02-architecture.md)
- Full endpoint inventory: [05-api.md](05-api.md)
- Public request/response contract: [API_CONTRACT.md](API_CONTRACT.md)
- Env and deployment: [08-configuration.md](08-configuration.md), [09-deployment.md](09-deployment.md)
- Developer workflow: [10-development.md](10-development.md)
