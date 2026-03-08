# AltShop Deployment

Проверено по коду: `2026-03-08`

## Источники истины

- `docker-compose.yml`
- `Dockerfile`
- `docker-entrypoint.sh`
- `nginx/nginx.conf`

## Текущий deployment contract

В репозитории есть один актуальный compose stack на 7 сервисов:

| Service | Role | Image/build | Depends on |
| --- | --- | --- | --- |
| `webapp-build` | one-shot сборка React/Vite frontend в `web-app/dist` | `node:20-alpine` | none |
| `altshop-nginx` | HTTPS termination, раздача `/webapp/`, proxy к backend | `nginx:1.28` | `webapp-build` completed successfully |
| `altshop-db` | PostgreSQL 17 | `postgres:17` | none |
| `altshop-redis` | Valkey 9 | `valkey/valkey:9-alpine` | none |
| `altshop` | основной FastAPI + aiogram runtime | локальный `Dockerfile` | `altshop-nginx` healthy, `altshop-db` healthy, `altshop-redis` healthy |
| `altshop-taskiq-worker` | фоновые Taskiq workers | image `altshop` | `altshop` started |
| `altshop-taskiq-scheduler` | Taskiq scheduler | image `altshop` | `altshop` started |

Что важно:

- `admin-backend` или иные admin services в текущем `docker-compose.yml` отсутствуют.
- `webapp-build` является обязательной частью текущего старта, потому что `altshop-nginx` зависит от него через `service_completed_successfully`.
- `altshop` в текущем compose зависит от healthy Nginx, хотя технически backend сам по себе мог бы стартовать и без него. Документация фиксирует именно текущий contract, а не желаемую архитектуру.

## Порядок старта

Фактическая последовательность контейнеров по `depends_on`:

1. `altshop-db`, `altshop-redis` и `webapp-build` могут стартовать сразу.
2. `webapp-build` выполняет `npm ci --legacy-peer-deps && npm run build` внутри `./web-app`.
3. После успешной сборки фронтенда стартует `altshop-nginx`.
4. После прохождения healthchecks `altshop-db`, `altshop-redis` и `altshop-nginx` стартует `altshop`.
5. После запуска `altshop` стартуют `altshop-taskiq-worker` и `altshop-taskiq-scheduler`.

## Что делает backend container

`docker-entrypoint.sh` перед запуском uvicorn:

1. Инициализирует `assets/` из `assets.default`, если volume пустой.
2. При `RESET_ASSETS=true` архивирует текущие assets и полностью перезаписывает их дефолтным набором.
3. Создает `/opt/altshop/logs`.
4. Выполняет `alembic -c src/infrastructure/database/alembic.ini upgrade head`.
5. Запускает uvicorn с `--proxy-headers` и `--forwarded-allow-ips "${APP_TRUSTED_PROXY_IPS}"`.

Compose пробрасывает backend только на loopback:

- `127.0.0.1:5000:5000` для `altshop`
- внешний HTTPS трафик должен заходить через `altshop-nginx`

## Nginx routing contract

`nginx/nginx.conf` сейчас обслуживает:

| Path | Behaviour |
| --- | --- |
| `/` | `302` на `/webapp/` |
| `/webapp` | `301` на `/webapp/` |
| `/webapp/` | SPA root из `/opt/altshop/webapp` |
| `/webapp/index.html` | явная раздача index файла |
| `/webapp/*` | статический SPA + fallback на `/webapp/index.html` |
| `/assets/*` | static assets из frontend build |
| `/api/v1` | proxy в `altshop:5000` |
| `/telegram` | proxy в `altshop:5000` |
| `/remnawave` | proxy в `altshop:5000` |
| `/payments` | proxy в `altshop:5000` |
| все остальное `/` | proxy в `altshop:5000` |

Дополнительно:

- sourcemaps под `/webapp` и `/assets` блокируются regex-маршрутом;
- включены TLS, gzip и базовые security headers для SPA;
- upstream backend разрешается через Docker DNS `127.0.0.11`.

## Подготовка к production запуску

### 1. Подготовить конфигурацию

```bash
cp .env.example .env
```

Обязательно проверьте вручную:

- `APP_DOMAIN`
- `APP_CRYPT_KEY`
- `APP_ORIGINS`
- `APP_TRUSTED_PROXY_IPS`
- `WEB_APP_JWT_SECRET`
- `DATABASE_PASSWORD`
- `REDIS_PASSWORD`
- `BOT_TOKEN`
- `BOT_SECRET_TOKEN`
- `REMNAWAVE_TOKEN`
- `REMNAWAVE_WEBHOOK_SECRET`

Подробная env-матрица: [08-configuration.md](08-configuration.md)

### 2. Подготовить TLS файлы для Nginx

Compose ожидает, что эти файлы уже существуют:

- `nginx/fullchain.pem`
- `nginx/privkey.key`

Эти пути захардкожены в `docker-compose.yml` и `nginx/nginx.conf`.

### 3. Собрать frontend

```bash
docker compose up --build webapp-build
```

Этот шаг должен завершиться успешно, чтобы `web-app/dist` был доступен Nginx.

### 4. Поднять runtime stack

```bash
docker compose up -d --build
```

Если нужен более явный порядок:

```bash
docker compose up -d --build altshop-db altshop-redis
docker compose up -d --build altshop-nginx
docker compose up -d --build altshop altshop-taskiq-worker altshop-taskiq-scheduler
```

## Что монтируется в контейнеры

| Host path / volume | Container path | Used by |
| --- | --- | --- |
| `./nginx/nginx.conf` | `/etc/nginx/conf.d/default.conf` | `altshop-nginx` |
| `./nginx/fullchain.pem` | `/etc/nginx/ssl/fullchain.pem` | `altshop-nginx` |
| `./nginx/privkey.key` | `/etc/nginx/ssl/privkey.key` | `altshop-nginx` |
| `./web-app/dist` | `/opt/altshop/webapp` / `/app/dist` | `altshop-nginx`, `webapp-build`, `altshop` |
| `./logs` | `/opt/altshop/logs` | `altshop`, worker, scheduler |
| `./assets` | `/opt/altshop/assets` | `altshop`, worker, scheduler |
| `altshop-db-data` | `/var/lib/postgresql/data` | `altshop-db` |
| `altshop-redis-data` | `/data` | `altshop-redis` |
| `webapp-node-modules` | `/app/node_modules` | `webapp-build` |

## Проверка после старта

Минимальный набор проверок:

```bash
docker compose ps
docker compose logs --tail=200 altshop
docker compose logs --tail=200 altshop-nginx
docker compose logs --tail=200 altshop-taskiq-worker
docker compose logs --tail=200 altshop-taskiq-scheduler
```

Проверки по контракту:

- `docker compose ps` показывает `webapp-build` в статусе `Exited (0)`
- `altshop-nginx` находится в `healthy`
- `altshop-db` и `altshop-redis` находятся в `healthy`
- в логах `altshop` нет ошибок `alembic upgrade head`
- `https://<APP_DOMAIN>/webapp/` открывает SPA
- `https://<APP_DOMAIN>/api/v1/auth/branding` отвечает через Nginx proxy

## Текущие ограничения

- В репозитории нет актуальных `docker-compose.local.yml` и `docker-compose.prod.external.yml`, поэтому они не являются частью текущего deployment contract.
- Отдельный admin service в default stack отсутствует.
- Отдельный health endpoint для backend в документации не фиксируется, потому что в текущем deployment flow compose использует healthchecks только для Nginx, PostgreSQL и Valkey.
- При изменении frontend-кода нужно заново прогонять `webapp-build`, иначе Nginx продолжит раздавать старый `web-app/dist`.
