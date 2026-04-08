# Backend Tech Audit

Проверено по коду: 2026-04-08

## Цель и scope

Этот документ фиксирует аудиторскую оценку backend-слоя AltShop поверх канонических описаний в `docs/02-architecture.md`, `docs/03-services.md` и `docs/05-api.md`.

В scope входят:

- backend stack: FastAPI + aiogram + Taskiq + SQLAlchemy + Redis/Valkey + Dishka + Remnawave;
- HTTP API, web auth, Remnawave integration, фоновые задачи и тестовое покрытие;
- архитектурные риски, operational risks, refactor-кандидаты и quick wins.

Вне scope:

- повторное перечисление всех endpoint-ов и сервисов из канонических docs;
- frontend/UI, deployment runbooks и детальный API contract.

## Источники истины

| Категория | Основные источники |
| --- | --- |
| Каноническая архитектура | `docs/02-architecture.md`, `docs/03-services.md`, `docs/05-api.md` |
| HTTP/API слой | `src/api/app.py`, `src/api/endpoints/web_auth.py`, `src/api/endpoints/remnawave.py`, `src/api/endpoints/payments.py` |
| Application services | `src/services/remnawave.py`, `src/services/subscription_purchase.py`, `src/services/backup.py`, `src/services/settings.py`, `src/services/web_access_guard.py`, `src/services/web_account.py` |
| Background/tasks | `src/lifespan.py`, `src/infrastructure/taskiq/tasks/subscriptions.py` |
| Тесты | `tests/services/*`, `tests/core/*`, отсутствие `tests/api/*` |

## Краткая оценка архитектуры

| Область | Оценка | Комментарий |
| --- | --- | --- |
| Слой сервисов | Умеренно сильная | Есть явный application-layer в `src/services`, DI через Dishka и разделение HTTP/bot/task surfaces. |
| Интеграции | Сильная, но хрупкая | Remnawave интеграция имеет raw fallback и version gating на старте, но остаётся крупным и сложно изменяемым модулем. |
| API/auth | Средняя | Cookie-based web auth и CSRF выглядят осмысленно, но endpoint-layer слишком концентрирован в одном файле и содержит fail-open деградации. |
| Фоновые процессы | Средняя | Taskiq используется по назначению, но orchestration размазан между lifespan, services и tasks без достаточного integration coverage. |
| Тестируемость | Ниже нормы | Покрытие смещено в service-level, route-level/API integration tests практически отсутствуют. |

- Общая картина: backend функционально зрелый и уже содержит защитные механизмы уровня production, но риск сосредоточен в нескольких больших orchestration-файлах и в слабом покрытии границ API/integration.
- Главная проблема не в выборе стека, а в концентрации критичной логики в нескольких слишком крупных модулях без достаточного route-level regression net.

## Самые рискованные и большие backend-файлы

| Файл | Размер | Почему риск высокий |
| --- | ---: | --- |
| `src/services/backup.py` | ~2982 LOC | Очень большой ops-oriented сервис: backup lifecycle, файловые операции, планирование, восстановление путей и housekeeping в одном месте. Высокая цена регрессии и сложность точечного тестирования. |
| `src/services/remnawave.py` | ~1585 LOC | Ключевая внешняя интеграция, version parsing, fallback-логика, sync users/devices/nodes, webhook side effects. Ошибки здесь сразу затрагивают access и подписки. |
| `src/services/subscription_purchase.py` | ~1378 LOC | Главный purchase orchestrator: catalog validation, quote, renew, payment handoff, policy checks. Большой blast radius для бизнес-логики. |
| `src/api/endpoints/web_auth.py` | ~1353 LOC | Сконцентрированы login/register/refresh/logout/password/email/telegram-link/access-status/rate-limit flows. Endpoint-layer стал частью бизнес-логики. |
| `src/infrastructure/taskiq/tasks/subscriptions.py` | ~1067 LOC | Критический async orchestration для subscription processing; высокая связность с payment/remnawave/runtime flows и повышенный риск скрытых retry/idempotency ошибок. |

## Audit: Remnawave integration

### Strengths

| Сильная сторона | Что это даёт |
| --- | --- |
| Raw fallback при проблемах SDK | `src/services/remnawave.py` умеет переходить с SDK-вызовов `/system/stats` и `/system/metadata` на raw HTTP-проверки, что снижает риск ложного стартап-фейла из-за schema drift. |
| Version gating на старте | `src/lifespan.py` проверяет поддерживаемость версии панели и шлёт warning, если версия вне диапазона. Это полезный ранний сигнал до массовых ошибок в runtime. |
| Явная обработка webhook event types | Есть разделение user/device/node events и отдельные side effects для cache/runtime updates. |

### Risks

| Риск | Детали |
| --- | --- |
| Webhook ack не отражает фактический результат обработки | `src/api/endpoints/remnawave.py` логирует и нотифицирует исключение, но после этого всё равно возвращает `200 OK`. Внешняя сторона перестаёт ретраить, а внутреннее состояние может остаться частично обновлённым. |
| Слишком крупный integration service | `src/services/remnawave.py` объединяет connection checks, version parsing, sync logic, webhook handling и notification side effects. Это затрудняет локальные изменения и изоляцию отказов. |
| Незавершённые operational ветки | `src/services/remnawave.py:1560` содержит TODO по реакции на traffic threshold у node events; поведение частично определено, но не доведено до policy-level решения. |

### Current mitigations

| Митигация | Статус |
| --- | --- |
| Fallback с SDK на raw HTTP | Есть |
| Проверка версии панели на старте | Есть |
| Логирование и error notifications | Есть |
| Частичное unit/service-level покрытие | Есть: `tests/services/test_remnawave_service.py`, `tests/services/test_lifespan_startup_tasks.py` |

### Residual risks

- При schema drift или частичной деградации панели старт backend скорее всего выживет, но runtime-пути webhook/sync всё ещё могут уходить в silent inconsistency.
- Нет видимого end-to-end подтверждения, что critical Remnawave webhooks переводят систему в согласованное состояние при сбоях cache update, DB update и task enqueue.
- Концентрация logic + side effects в `src/services/remnawave.py` повышает риск того, что исправление одной ветки сломает другую без быстрого сигнала от тестов.

## Audit: web auth и API

### Strengths

| Сильная сторона | Что это даёт |
| --- | --- |
| Cookie-first auth model | Текущий web auth не опирается только на bearer-токены и лучше соответствует browser flow. |
| CSRF-проверка для cookie auth | Unsafe methods требуют `X-CSRF-Token`, что снижает базовый CSRF-риск. |
| Token versioning | Logout и invalidation опираются на `token_version`, что упрощает отзыв сессий. |

### Security/stability risks

| Риск | Уровень | Детали |
| --- | --- | --- |
| Rate limit работает fail-open при падении Redis | Высокий | `_enforce_rate_limit()` в `src/api/endpoints/web_auth.py` ловит исключение Redis и просто возвращает управление. В момент деградации инфраструктуры brute-force защита ослабляется именно тогда, когда она нужнее всего. |
| Слишком большой auth endpoint module | Высокий | `src/api/endpoints/web_auth.py` совмещает transport, validation, rate-limit, analytics hooks и recovery flows. Это ухудшает обозримость security-sensitive кода. |
| Недостаток route-level проверок error semantics | Высокий | Для auth/web API почти не видно тестов уровня FastAPI routes, поэтому статус-коды, cookie headers, CSRF enforcement и dependency wiring плохо защищены от регрессий. |

### Coverage gaps

| Gap | Что отсутствует |
| --- | --- |
| `tests/api` | Папка не просматривается; route-level/API integration tests практически нет. |
| Auth transport regression tests | Нет явного набора тестов на cookies, refresh path, logout invalidation, CSRF-required unsafe methods и error codes. |
| Redis degradation tests | Нет явного integration coverage для fail-open/fail-closed поведения rate limit. |
| Remnawave webhook API tests | Нет route-level тестов на signature validation, internal failure semantics и retry-friendly status codes. |

## Состояние backend-тестов

| Метрика | Состояние |
| --- | --- |
| Количество test files | Около 38 |
| Количество test functions | Около 180 |
| Основной фокус | Service-level и core-level unit tests |
| API/integration coverage | Практически отсутствует |

### Что покрыто

- `tests/services/test_remnawave_service.py` закрывает часть fallback/version parsing логики Remnawave.
- `tests/services/test_lifespan_startup_tasks.py` проверяет отдельные startup-effects, включая warning на unsupported Remnawave version.
- `tests/services/test_subscription_purchase_service.py` и соседние service-level тесты покрывают часть бизнес-правил purchase flow.
- `tests/services/test_web_login_identity.py` покрывает отдельные куски web-account/telegram-link/profile logic, но не весь HTTP contract.

### Чего не хватает

- FastAPI route tests для `web_auth.py`, `remnawave.py`, `payments.py`, user-facing subscription endpoints.
- Integration tests на цепочки `HTTP -> service -> DB/cache/task`.
- Набора негативных тестов на infrastructure degradation: Redis down, Remnawave webhook processing error, partial task enqueue failure.
- Явных тестов на security headers, cookie attributes, CSRF-required paths и retry semantics webhook-ов.

## Code markers и сигналы техдолга

| Маркер | Что сигнализирует |
| --- | --- |
| `src/services/remnawave.py:1560` | Не завершена policy-реакция на traffic threshold/node event. |
| `src/services/settings.py:99` | Прямой `FIXME` в runtime settings update path; это плохой сигнал для стабильности одного из базовых конфигурационных сервисов. |
| Прочие TODO/FIXME в `src/services`, `src/core`, `src/bot` | Техдолг не единичный, а распределённый; нужен triage по критичности, а не только backlog accumulation. |

## Findings

### P0

| ID | Finding | Почему приоритет максимальный |
| --- | --- | --- |
| P0-1 | `src/api/endpoints/remnawave.py` возвращает `200 OK` даже при внутренних ошибках обработки webhook | Это ломает retry contract с внешней системой и может оставлять backend в несогласованном состоянии без автоматического восстановления. |

### P1

| ID | Finding | Почему это важно |
| --- | --- | --- |
| P1-1 | Rate limit в `src/api/endpoints/web_auth.py` работает fail-open при падении Redis | Ослабляет brute-force protection в аварийном режиме. |
| P1-2 | `src/services/remnawave.py`, `src/api/endpoints/web_auth.py`, `src/services/subscription_purchase.py` и `src/infrastructure/taskiq/tasks/subscriptions.py` слишком крупные | Риск регрессий и стоимость изменения выше нормы для security/business-critical путей. |
| P1-3 | Route-level/API integration tests практически отсутствуют | Нет надёжного safety net на status codes, cookie contract, DI wiring и error semantics. |

### P2

| ID | Finding | Почему это важно |
| --- | --- | --- |
| P2-1 | `src/services/backup.py` остаётся чрезмерно большим ops-сервисом | Высокая сложность сопровождения и слабая локализуемость изменений. |
| P2-2 | В `src/services/settings.py:99` остаётся `FIXME` в рабочем update path | Низкое доверие к cleanliness критичного settings-сервиса. |
| P2-3 | Remnawave node-event policy не завершена (`src/services/remnawave.py:1560`) | Operational behavior на threshold events пока недоопределён. |

## Refactor-кандидаты

| Кандидат | Что выделить |
| --- | --- |
| `src/api/endpoints/web_auth.py` | Разделить на transport helpers, rate-limit/auth guards, password recovery routes, telegram-link routes, session routes. |
| `src/services/remnawave.py` | Выделить `panel_health/version client`, `webhook event handlers`, `user sync orchestration`, `node/device side effects`. |
| `src/services/subscription_purchase.py` | Отделить catalog/policy validation, quote calculation, payment initiation и renew/additional-specific orchestration. |
| `src/infrastructure/taskiq/tasks/subscriptions.py` | Разделить enqueue/retry/idempotency helpers и конкретные task сценарии. |
| `src/services/backup.py` | Вынести scheduler/retention, file-path resolution, storage/backends и restore helpers в отдельные модули. |

## Quick wins

| Приоритет | Действие | Эффект |
| --- | --- | --- |
| 1 | Исправить `src/api/endpoints/remnawave.py`: возвращать `5xx`, если обработка webhook не завершилась успешно | Восстанавливает корректный retry contract и снижает риск silent data loss. |
| 2 | Пересмотреть fail-open в `_enforce_rate_limit()` (`src/api/endpoints/web_auth.py`) | Улучшает защиту auth surface в аварийных режимах Redis. |
| 3 | Добавить минимальный `tests/api` набор для `web_auth` и `remnawave` | Быстро закрывает главный coverage gap на boundary-layer. |
| 4 | Завести ADR/decision note по Remnawave degradation policy | Снижает неоднозначность вокруг fallback, unknown version и node traffic events. |
| 5 | Разобрать `FIXME` в `src/services/settings.py:99` и triage TODO/FIXME по критичности | Убирает явные маркеры нестабильности из runtime-critical paths. |

## Итог

- Backend в целом опирается на зрелый стек и уже содержит полезные защитные механизмы, особенно в Remnawave startup path.
- Главный риск находится на стыке integration semantics и отсутствующего API-level regression coverage.
- Приоритет исправлений: сначала webhook error semantics и auth rate-limit degradation, затем декомпозиция крупных файлов и наращивание route-level tests.
