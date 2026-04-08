# Infra/Ops Tech Audit

Проверено по коду: 2026-04-08

## Цель и scope

Документ фиксирует эксплуатационные риски и приоритеты remediation для текущего Docker/compose, runtime, CI/CD и фоновых процессов. Это не deployment guide: здесь нет пошагового развёртывания, только audit текущей operational-модели по коду и конфигурации.

В scope входят:

- container/runtime topology для `docker-compose.yml` и `docker-compose.prod.yml`;
- image build/publish flows в GitHub Actions, включая `beta`;
- backend, `Taskiq` worker/scheduler, Redis и backup operating model;
- observability, logging, health/readiness, config drift и secret-handling;
- findings `P1/P2/P3` и план remediation.

## Источники истины

- Compose/runtime: `docker-compose.yml`, `docker-compose.prod.yml`, `Dockerfile`, `docker-entrypoint.sh`.
- CI/CD: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/beta-images.yml`.
- App config: `src/core/config/app.py`, `src/core/config/web_app.py`, `src/core/config/redis.py`, `src/core/config/backup.py`, `.env.example`.
- FastAPI/runtime wiring: `src/__main__.py`, `src/api/app.py`, `src/api/endpoints/internal.py`, `src/lifespan.py`.
- Background processing: `src/bot/dispatcher.py`, `src/infrastructure/taskiq/broker.py`, `src/infrastructure/taskiq/worker.py`, `src/infrastructure/taskiq/scheduler.py`, `src/infrastructure/taskiq/tasks/updates.py`.
- Logging/observability: `src/core/logger.py`, `src/core/observability.py`.

## Docker / compose / runtime architecture

- Базовая stack-модель уже собрана: `nginx`, `postgres`, `valkey/redis`, backend app, `Taskiq` worker, `Taskiq` scheduler; в dev есть отдельный `webapp-build`, в prod backend/nginx приходят из GHCR (`docker-compose.yml`, `docker-compose.prod.yml`).
- Backend Docker image собран на pinned base images по digest, что снижает supply-chain drift на уровне базового runtime (`Dockerfile:3`, `Dockerfile:15`).
- В prod compose backend/worker/scheduler используют один и тот же backend image tag `ghcr.io/dizzzable/altshop-backend:${ALTSHOP_IMAGE_TAG:-latest}`, а nginx использует отдельный `ALTSHOP_NGINX_IMAGE_TAG` (`docker-compose.prod.yml:3`, `docker-compose.prod.yml:61`, `docker-compose.prod.yml:86`, `docker-compose.prod.yml:105`).
- Runtime state для БД и Redis вынесен в named volumes, но backup path по умолчанию не смонтирован в контейнеры вообще, поэтому сохранность backup-архивов зависит от внутреннего FS контейнера, если оператор не переопределил путь вручную (`docker-compose.prod.yml:79-119`, `.env.example:297-299`, `src/core/config/backup.py:23-44`).
- У `nginx`, `db`, `redis` healthcheck есть, у backend/worker/scheduler — нет; `depends_on` для worker/scheduler смотрит только на `service_started`, а не на реальную готовность приложения (`docker-compose.prod.yml:16-20`, `docker-compose.prod.yml:38-58`, `docker-compose.prod.yml:72-78`, `docker-compose.prod.yml:95-116`).
- Логи и assets смонтированы общими host-path для app/worker/scheduler. Для assets это ожидаемо, для логов это создаёт смешение потоков и усложняет forensic/debugging (`docker-compose.prod.yml:79-119`, `src/core/logger.py:66-85`).

## CI/CD и image publishing audit

- Release и beta image workflows уже настроены: stable publish идёт по тегам `v*.*.*`, beta publish — по пушу в ветку `beta` (`.github/workflows/release.yml:3-6`, `.github/workflows/beta-images.yml:3-7`).
- Release workflow валидирует версии в `pyproject.toml` и `web-app/package.json`, публикует backend/nginx images и GitHub Release (`.github/workflows/release.yml:34-112`).
- Beta workflow публикует `beta` и `beta-${github.sha}` теги для backend/nginx, что полезно для канала предварительной проверки (`.github/workflows/beta-images.yml:30-48`).
- Основной риск: ни `release.yml`, ни `beta-images.yml` не имеют жёсткой привязки к fully green `CI`; в них нет `needs`, `workflow_run` или встроенного повторного прогона тестов до publish. Формально image publishing может пройти отдельно от полного green state (`.github/workflows/ci.yml:9-60`, `.github/workflows/release.yml:12-94`, `.github/workflows/beta-images.yml:12-48`).
- Дополнительно prod compose по умолчанию ориентирован на mutable `latest`, поэтому rollback и pinning версии остаются ручной дисциплиной оператора, а не enforced практикой (`docker-compose.prod.yml:3`, `docker-compose.prod.yml:61`, `.env.example:258-263`).
- Release notification в production уже предусмотрен и защищён bearer secret, но сам required runtime secret не отражён в `.env.example`, что повышает шанс silent misconfiguration (`src/api/endpoints/internal.py:39-67`, `src/core/config/app.py:22-34`, `.github/workflows/release.yml:113-181`).

## Redis / Taskiq / worker-scheduler operating model

- Один Redis DSN используется одновременно для aiogram FSM storage, application cache, web auth/rate limiting, release dedupe/update audit и Taskiq broker/result backend (`src/bot/dispatcher.py:13-25`, `src/api/endpoints/web_auth.py:360-373`, `src/services/release_notification.py:231-307`, `src/infrastructure/taskiq/broker.py:10-17`, `src/core/config/redis.py:7-21`).
- Такая схема упрощает single-node эксплуатацию, но делает Redis общим control plane без namespace isolation по workload criticality. Сбой, eviction, saturation или операторская ошибка в одном слое затрагивает сразу bot FSM, API throttling, async jobs и release-dedupe.
- Worker и scheduler поднимаются из того же image, что и backend, и используют один broker; scheduler читает cron labels из task registry (`docker-compose.prod.yml:85-119`, `src/infrastructure/taskiq/scheduler.py:10-17`).
- Startup lifecycle backend запускает auto-backup и фоновые update/payment recovery tasks внутри lifespan, но worker/scheduler не имеют собственного readiness контракта для orchestration (`src/lifespan.py:53-151`, `src/infrastructure/taskiq/worker.py:14-27`, `src/infrastructure/taskiq/scheduler.py:10-17`).

## Observability / logging / healthcheck

- Observability сейчас в основном log-centric: Loguru пишет в stderr и в файл `logs/bot.log` с daily rotation/zip retention (`src/core/logger.py:66-99`).
- `emit_counter()` не экспортирует метрики наружу, а лишь пишет события вида `counter ...` в лог; полноценного metrics endpoint/exporter в коде не видно (`src/core/observability.py:6-12`).
- У FastAPI app нет явного `/health`, `/ready` или аналогичного app-level endpoint; `src/api/app.py` подключает только business/internal routers (`src/api/app.py:18-43`).
- В compose нет healthcheck у backend/worker/scheduler, поэтому orchestration не различает процесс "запущен" и сервис "готов принимать трафик/таски" (`docker-compose.prod.yml:60-121`, `docker-compose.yml:63-128`).
- Общий log volume `./logs:/opt/altshop/logs` для трёх процессов создаёт риск interleaving, потери причинно-следственной связи и спорных ownership/rotation сценариев (`docker-compose.prod.yml:79-119`, `src/core/constants.py:7-10`, `src/core/logger.py:77-85`).

## Configuration / security drift и secret-handling risks

- Критичный drift в CORS: `.env.example` документирует `WEB_APP_CORS_ORIGINS`, но FastAPI middleware реально читает `config.origins`, то есть `APP_ORIGINS`; поле `web_app.cors_origins` в runtime wiring не используется (`.env.example:101-104`, `src/core/config/web_app.py:24-25`, `src/core/config/app.py:22-34`, `src/api/app.py:20-26`).
- `APP_RELEASE_NOTIFY_SECRET` требуется коду для защищённого `/api/v1/internal/release-notify`, но отсутствует в `.env.example`, что создаёт config drift между release workflow и production runtime (`src/core/config/app.py:26`, `src/api/endpoints/internal.py:39-67`, `.github/workflows/release.yml:113-181`, `.env.example`).
- Secrets в целом приходят через env/secrets GitHub Actions и не захардкожены в compose, что хорошо, но operational risk остаётся из-за неполного шаблона `.env.example` и отсутствия machine-checkable config audit.
- Backup default path `/app/data/backups` не совпадает с основным runtime layout `/opt/altshop/...` и не закреплён volume mount'ом, что повышает вероятность ошибочного предположения о persistent storage (`src/core/config/backup.py:23-44`, `.env.example:297-299`, `docker-compose.prod.yml:79-119`).

## Findings

### P1

- `P1` CORS env drift: `.env.example` предлагает `WEB_APP_CORS_ORIGINS`, но middleware использует `APP_ORIGINS`; оператор может быть уверен, что CORS настроен, хотя production app прочитает другое поле. Файлы: `.env.example:101-104`, `src/core/config/app.py:33`, `src/core/config/web_app.py:24-25`, `src/api/app.py:20-26`.
- `P1` Нет app-level health/readiness endpoint и нет healthcheck у backend/worker/scheduler; Compose не способен корректно определять readiness и деградацию application tier. Файлы: `src/api/app.py:18-43`, `docker-compose.yml:63-128`, `docker-compose.prod.yml:60-121`.
- `P1` Общие лог-файлы/shared log volume у app/worker/scheduler; это повышает риск повреждения операционной картины при инцидентах и затрудняет разбор фоновых ошибок. Файлы: `docker-compose.yml:85-126`, `docker-compose.prod.yml:79-119`, `src/core/logger.py:77-85`.
- `P1` Backup path по умолчанию не примонтирован явно и может быть эфемерным; потеря контейнера может означать потерю локальных backup-архивов. Файлы: `.env.example:297-299`, `src/core/config/backup.py:23-44`, `docker-compose.yml:85-126`, `docker-compose.prod.yml:79-119`.

### P2

- `P2` Beta/release images публикуются без жёсткой привязки к full green CI; publish flows отделены от CI и не блокируются им на уровне workflow graph. Файлы: `.github/workflows/ci.yml:9-60`, `.github/workflows/release.yml:12-94`, `.github/workflows/beta-images.yml:12-48`.
- `P2` Redis является shared control plane для FSM/cache/rate limit/release dedupe/Taskiq; один отказ Redis затрагивает сразу несколько operational domains. Файлы: `src/bot/dispatcher.py:13-25`, `src/api/endpoints/web_auth.py:360-373`, `src/services/release_notification.py:231-307`, `src/infrastructure/taskiq/broker.py:10-17`, `src/core/config/redis.py:7-21`.
- `P2` Production compose по умолчанию использует mutable `latest`; rollback manual, а reproducibility окружения зависит от ручного pinning тега оператором. Файлы: `docker-compose.prod.yml:3`, `docker-compose.prod.yml:61`, `.env.example:258-263`.
- `P2` `APP_RELEASE_NOTIFY_SECRET` нужен runtime-коду, но не отражён в `.env.example`; результат — нестабильный release notify path и риск 503/401 после релиза. Файлы: `src/core/config/app.py:26`, `src/api/endpoints/internal.py:44-67`, `.github/workflows/release.yml:113-181`, `.env.example`.

### P3

- `P3` Observability ограничена файловыми логами и log-derived counters без стандартного metrics/export endpoint; для SLO/SLA и alerting этого недостаточно. Файлы: `src/core/logger.py:66-99`, `src/core/observability.py:6-12`.
- `P3` Worker/scheduler зависят от backend старта по `service_started`, а не от явного сервиса очередей/ready contract; поведение при частичной деградации остаётся неформализованным. Файлы: `docker-compose.prod.yml:95-116`, `docker-compose.yml:102-123`.

## Quick wins

- Исправить `.env.example`: добавить `APP_ORIGINS`, добавить `APP_RELEASE_NOTIFY_SECRET`, пометить `WEB_APP_CORS_ORIGINS` как deprecated/unused либо убрать.
- Добавить минимальные `/health` и `/ready` endpoints в FastAPI и повесить на них `healthcheck` для backend; для worker/scheduler добавить отдельные probe-команды или watchdog-script.
- Разделить log sinks/host paths как минимум по процессам: `backend.log`, `worker.log`, `scheduler.log` или отдельные директории.
- Явно смонтировать persistent backup volume/path в compose и синхронизировать default path с фактическим runtime layout.
- Зафиксировать prod image tags на immutable release tags или digest вместо `latest`.

## Более крупные remediation items

- Перестроить CI/CD graph: image publish только после full CI gate, отдельно оформить promotion из `beta` в stable, добавить provenance/SBOM и policy на immutable deploy tags.
- Разделить Redis workloads по logical DB/instance/cluster policy: минимум — отдельный Redis для Taskiq или для bot/API control-plane, плюс namespace/TTL review.
- Ввести app-level operational contract: readiness checks на DB/Redis/Remnawave dependencies, graceful degradation rules, restart semantics для worker/scheduler.
- Перейти от log-only observability к нормальной telemetry surface: metrics exporter, structured logs, correlation/request IDs, централизованный сбор логов и алерты на backup/queue/release-notify failures.
- Добавить config conformance tests, которые валидируют `.env.example` против реальных `AppConfig`/`WebAppConfig` и проверяют наличие обязательных env keys для production paths.

## Итог

Базовая infra-модель уже рабочая: compose stack собран, Docker images публикуются, backend base images pinned by digest, release и beta flows существуют. Основной operational debt сосредоточен не в отсутствии контейнеризации, а в readiness/health, config drift, shared operational surfaces и слабой привязке publish pipeline к green CI. Приоритет first wave remediation: закрыть четыре `P1`, затем зафиксировать immutable deploy semantics и развести shared Redis/logging surfaces.
