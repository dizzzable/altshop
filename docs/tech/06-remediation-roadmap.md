# Remediation Roadmap

Проверено по коду: 2026-04-08

## Роль документа

Этот roadmap фиксирует последовательность remediation-работ по audit-layer `docs/tech/`. Он не заменяет канонические документы `docs/02-architecture.md`, `docs/05-api.md`, `docs/09-deployment.md`, `docs/10-development.md`, а переводит audit findings в исполнимые волны изменений.

## Целевой принцип

Roadmap строится вокруг четырёх главных bottleneck'ов текущего состояния:

- oversized modules в backend и frontend;
- слабый API/frontend regression net;
- infra health и config drift;
- docs/contract drift.

При этом важно учитывать, что backend по сравнению с мартом стал заметно здоровее, поэтому первая волна направлена не на emergency rewrite, а на сокращение residual high-risk gaps и повышение предсказуемости изменений.

## P0 — Quick wins за 1-2 дня

| Пункт | Ожидаемый эффект | Ключевые файлы и зоны |
| --- | --- | --- |
| Исправить webhook failure semantics для Remnawave: не возвращать `200 OK`, если внутренняя обработка не завершилась успешно | Восстанавливается retry-friendly contract и снижается риск silent inconsistency | `src/api/endpoints/remnawave.py`, `src/services/remnawave.py` |
| Пересмотреть fail-open поведение rate limit в web auth при проблемах Redis | Снижается brute-force risk в деградационном режиме | `src/api/endpoints/web_auth.py`, Redis/rate-limit path |
| Добавить минимальный набор route-level тестов для auth и Remnawave webhook | Появляется базовый regression net на самом рискованном boundary-layer | `tests/api/*`, `src/api/endpoints/web_auth.py`, `src/api/endpoints/remnawave.py` |
| Добавить базовые `/health` и `/ready` endpoints и повесить healthcheck на backend | Улучшается orchestration, detection деградации и operational visibility | `src/api/app.py`, новый health router, `docker-compose.yml`, `docker-compose.prod.yml` |
| Исправить явный config drift в env template | Снижается риск misconfiguration при deployment и release operations | `.env.example`, `src/core/config/app.py`, `src/core/config/web_app.py` |

## P1 — Short-term за 1-2 недели

| Пункт | Ожидаемый эффект | Ключевые файлы и зоны |
| --- | --- | --- |
| Поднять frontend test baseline: unit/integration для auth/API layer и smoke coverage для ключевых dashboard flows | Появляется первый safety net для `web-app`, снижается страх перед refactor'ом | `web-app/package.json`, `web-app/src/lib/api.ts`, `web-app/src/App.tsx`, `web-app/src/pages/dashboard/*` |
| Расширить backend API/integration tests на cookie contract, CSRF, logout/refresh, error codes | Укрепляется проверяемость реального HTTP-контракта | `tests/api/*`, `src/api/endpoints/web_auth.py`, `src/api/endpoints/payments.py` |
| Обновить docs, которые уже drift'уют от runtime | Ускоряется onboarding и уменьшается риск неправильных инженерных предположений | `web-app/README.md`, `web-app/AUTH_SYSTEM.md`, `docs/OPENAPI_GENERATION_SETUP.md`, связанные docs |
| Явно закрепить persistent backup path и привести runtime layout к документированному виду | Снижается риск потери backup-артефактов и operational ambiguity | `docker-compose.prod.yml`, `docker-compose.yml`, `.env.example`, `src/core/config/backup.py` |
| Разделить log surfaces по backend/worker/scheduler | Упрощается incident analysis и forensic-debugging | `docker-compose.prod.yml`, `docker-compose.yml`, `src/core/logger.py` |

## P2 — Medium-term за 1-2 спринта

| Пункт | Ожидаемый эффект | Ключевые файлы и зоны |
| --- | --- | --- |
| Начать декомпозицию крупнейших backend-модулей по bounded responsibilities | Снижается blast radius изменений и растёт reviewability | `src/services/remnawave.py`, `src/services/subscription_purchase.py`, `src/services/backup.py`, `src/infrastructure/taskiq/tasks/subscriptions.py`, `src/api/endpoints/web_auth.py` |
| Начать декомпозицию крупнейших frontend pages в feature-level hooks/components/query modules | Уменьшается page-bloat и улучшается testability UI | `web-app/src/pages/dashboard/PurchasePage.tsx`, `web-app/src/pages/dashboard/SubscriptionPage.tsx`, `web-app/src/pages/dashboard/SettingsPage.tsx`, `web-app/src/pages/dashboard/PartnerPage.tsx` |
| Стандартизовать query keys, cache invalidation и typed contract layer | Снижается риск frontend/backend contract drift и скрытых cache-regressions | `web-app/src/lib/api.ts`, `web-app/src/hooks/*`, `web-app/src/types/*`, возможный `web-app/src/generated/*` |
| Добавить config conformance checks и production env validation | Drift между `.env.example`, runtime config и deploy paths становится контролируемым | `.github/workflows/*`, `.env.example`, `src/core/config/*` |
| Зафиксировать publish/deploy semantics на immutable tags и усилить связь publish с green CI | Улучшается reproducibility релизов и rollback discipline | `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/beta-images.yml`, `docker-compose.prod.yml` |

## Structural changes — после стабилизации базовых волн

| Пункт | Ожидаемый эффект | Ключевые файлы и зоны |
| --- | --- | --- |
| Развести shared infra control planes: Redis workloads, readiness contracts, worker/scheduler operational model | Снижается cross-domain blast radius при деградации инфраструктуры | `src/core/config/redis.py`, `src/infrastructure/taskiq/*`, `src/bot/dispatcher.py`, compose/runtime config |
| Перейти от log-only observability к нормальной telemetry surface | Появляется основа для SLO/SLA, alerting и faster incident response | `src/core/logger.py`, `src/core/observability.py`, API/runtime layer, deploy stack |
| Оформить docs/contract governance как постоянную практику, а не разовый cleanup | Drift перестаёт накапливаться между backend, frontend, docs и ops | `docs/`, `web-app/`, CI checks, development workflow |
| Перевести крупные remediation topics в устойчивые engineering conventions | Команда получает предсказуемый способ развивать систему без возврата к текущим bottleneck'ам | `docs/10-development.md`, тестовые и review practices, архитектурные ADR/notes |

## Suggested sequencing

1. Сначала закрыть P0: это самые дешёвые изменения с максимальным снижением системного риска.
2. Затем в P1 быстро поднять regression baseline и убрать самый заметный config/docs drift.
3. После этого идти в P2 refactor-first волной: уменьшать oversized modules и стандартизовать contracts.
4. Structural changes выносить в отдельную программу платформенного укрепления, не смешивая её с быстрыми bugfix/remediation задачами.

## Итог

Наиболее рациональная стратегия сейчас — не масштабный rewrite, а серия последовательных волн: сначала восстановить предсказуемость boundary-layer и infra health, затем уменьшить oversized change surfaces, после этого закрыть contract/docs drift и перевести оставшийся debt в платформенные практики. Это соответствует текущему состоянию проекта: backend уже заметно сильнее мартовского baseline, но безопасную скорость развития всё ещё ограничивают regression gaps, крупные модули и operational/documentation drift.
