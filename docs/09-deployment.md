# AltShop Deployment

Проверено по коду: `2026-03-21`

## Источники истины

- `docker-compose.yml`
- `docker-compose.prod.yml`
- `Dockerfile`
- `nginx/Dockerfile`
- `docker-entrypoint.sh`
- `nginx/nginx.conf`
- `.github/workflows/release.yml`

## Deployment contracts

### VPS / production contract

Канонический production deploy теперь идет через `docker-compose.prod.yml` и release images из GHCR.

| Service | Role | Image | Depends on |
| --- | --- | --- | --- |
| `altshop-nginx` | HTTPS termination, раздача `/webapp/`, proxy к backend | `ghcr.io/dizzzable/altshop-nginx` | none |
| `altshop-db` | PostgreSQL 17 | `postgres:17` | none |
| `altshop-redis` | Valkey 9 | `valkey/valkey:9-alpine` | none |
| `altshop` | основной FastAPI + aiogram runtime | `ghcr.io/dizzzable/altshop-backend` | `altshop-nginx` healthy, `altshop-db` healthy, `altshop-redis` healthy |
| `altshop-taskiq-worker` | фоновые Taskiq workers | `ghcr.io/dizzzable/altshop-backend` | `altshop` started |
| `altshop-taskiq-scheduler` | Taskiq scheduler | `ghcr.io/dizzzable/altshop-backend` | `altshop` started |

Что важно:

- `webapp-build` в production stack отсутствует, потому что frontend уже встроен в `altshop-nginx` image.
- `altshop-nginx` получает только TLS-сертификаты с хоста, а не из git.
- по умолчанию production compose использует `latest`, но поддерживает pin через `ALTSHOP_IMAGE_TAG` и `ALTSHOP_NGINX_IMAGE_TAG`.

### Local/manual build fallback

Существующий `docker-compose.yml` остается build-based fallback для локальной сборки и ручного деплоя из исходников.

Repository helpers map directly to those supported entrypoints:

- `make run-local` -> `docker-compose.yml`
- `make run-prod` -> `docker-compose.prod.yml`

| Service | Role | Image/build | Depends on |
| --- | --- | --- | --- |
| `webapp-build` | one-shot сборка React/Vite frontend в `web-app/dist` | `node:20.19-alpine` | none |
| `altshop-nginx` | HTTPS termination, раздача `/webapp/`, proxy к backend | `nginx:1.28` | `webapp-build` completed successfully |
| `altshop-db` | PostgreSQL 17 | `postgres:17` | none |
| `altshop-redis` | Valkey 9 | `valkey/valkey:9-alpine` | none |
| `altshop` | основной FastAPI + aiogram runtime | локальный `Dockerfile` | `altshop-nginx` healthy, `altshop-db` healthy, `altshop-redis` healthy |
| `altshop-taskiq-worker` | фоновые Taskiq workers | image `altshop` | `altshop` started |
| `altshop-taskiq-scheduler` | Taskiq scheduler | image `altshop` | `altshop` started |

## Что делает backend image

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

Canonical operator-facing route notes:

- exact `/webapp/` requests are proxied to `GET /api/v1/auth/webapp-shell` so branding and Telegram link previews can shape the shell response;
- canonical webhook URLs are `/api/v1/telegram`, `/api/v1/remnawave`, and `/api/v1/payments/{gateway_type}`;
- raw nginx locations `/telegram`, `/remnawave`, and `/payments` are legacy pass-throughs and should not be treated as the backend contract.

`nginx/nginx.conf` обслуживает:

| Path | Behaviour |
| --- | --- |
| `/` | `302` на `/webapp/` |
| `/webapp` | `301` на `/webapp/` |
| `/webapp/` | SPA root из `/opt/altshop/webapp` |
| `/webapp/index.html` | явная раздача index файла |
| `/webapp/*` | статический SPA + fallback на `/webapp/index.html` |
| `/assets/*` | static assets из frontend build |
| `/api/v1/health/livez` | публичный liveness probe |
| `/api/v1` | proxy в `altshop:5000` |
| `/telegram` | proxy в `altshop:5000` |
| `/remnawave` | proxy в `altshop:5000` |
| `/payments` | proxy в `altshop:5000` |
| все остальное `/` | proxy в `altshop:5000` |

Дополнительно:

- sourcemaps под `/webapp` и `/assets` блокируются regex-маршрутом;
- включены TLS, gzip и базовые security headers для SPA;
- upstream backend разрешается через Docker DNS `127.0.0.11`.
- `/api/v1/internal/readiness` и `/api/v1/internal/metrics` не публикуются через nginx и остаются backend-only проверками на `127.0.0.1:5000`.
- канонический payment webhook URL строится из `src/core/config/app.py` как `/api/v1/payments/{gateway_type}`; отдельный `location /payments` в nginx является raw pass-through, а не описанием backend route prefix.

## Подготовка к production запуску на VPS

### 1. Подготовить конфигурацию

```bash
cp .env.example .env
```

Обязательно проверьте вручную:

- `APP_DOMAIN`
- `APP_ALLOWED_HOSTS`
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

`APP_DOMAIN` из `.env` также используется production nginx image для рендера `server_name` при старте контейнера.

### 2. Выпустить TLS-файлы на хост

```bash
acme.sh --issue --standalone -d '<domain>' \
  --key-file /opt/altshop/nginx/remnabot_privkey.key \
  --fullchain-file /opt/altshop/nginx/remnabot_fullchain.pem
```

По умолчанию `docker-compose.prod.yml` ожидает именно эти пути:

- `/opt/altshop/nginx/remnabot_fullchain.pem`
- `/opt/altshop/nginx/remnabot_privkey.key`

Если на VPS используется другой layout, переопределите:

- `NGINX_SSL_FULLCHAIN_PATH`
- `NGINX_SSL_PRIVKEY_PATH`

### 3. Один раз проверить visibility GHCR packages

Release workflow публикует:

- `ghcr.io/dizzzable/altshop-backend`
- `ghcr.io/dizzzable/altshop-nginx`

Если GitHub создал их приватными, переведите оба пакета в `Public`. После этого `docker compose -f docker-compose.prod.yml pull` будет работать без `docker login`.

### 4. Обновить и поднять stack

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

Если нужен pin конкретного релиза вместо `latest`, задайте перед запуском:

```bash
export ALTSHOP_IMAGE_TAG=X.Y.Z
export ALTSHOP_NGINX_IMAGE_TAG=X.Y.Z
```

Если сервер когда-то поднимался вручную и в нем еще нет `docker-compose.prod.yml`, используйте одноразовый migrate-bootstrap:

```bash
curl -fsSL https://raw.githubusercontent.com/dizzzable/altshop/main/scripts/bootstrap-prod-vps.sh | sh
```

Скрипт подтягивает `docker-compose.prod.yml`, сохраняет текущий `.env`, пытается подхватить существующие volume или bind mounts для PostgreSQL и Redis и затем переводит хост на GHCR-based stack.

## Что монтируется в production контейнеры

| Host path / volume | Container path | Used by |
| --- | --- | --- |
| `${NGINX_SSL_FULLCHAIN_PATH:-/opt/altshop/nginx/remnabot_fullchain.pem}` | `/etc/nginx/ssl/fullchain.pem` | `altshop-nginx` |
| `${NGINX_SSL_PRIVKEY_PATH:-/opt/altshop/nginx/remnabot_privkey.key}` | `/etc/nginx/ssl/privkey.key` | `altshop-nginx` |
| `./logs` | `/opt/altshop/logs` | `altshop`, worker, scheduler |
| `./assets` | `/opt/altshop/assets` | `altshop`, worker, scheduler |
| `${ALTSHOP_DB_VOLUME_NAME:-altshop-db-data}` | `/var/lib/postgresql/data` | `altshop-db` |
| `${ALTSHOP_REDIS_VOLUME_NAME:-altshop-redis-data}` | `/data` | `altshop-redis` |

## Проверка после старта

Минимальный набор проверок:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=200 altshop
docker compose -f docker-compose.prod.yml logs --tail=200 altshop-nginx
docker compose -f docker-compose.prod.yml logs --tail=200 altshop-taskiq-worker
docker compose -f docker-compose.prod.yml logs --tail=200 altshop-taskiq-scheduler
docker compose -f docker-compose.prod.yml exec altshop-nginx nginx -t
docker compose -f docker-compose.prod.yml exec altshop-nginx test -f /opt/altshop/webapp/index.html
```

Smoke checks:

- `curl -I https://<APP_DOMAIN>/` возвращает `302` на `/webapp/`
- `curl -I https://<APP_DOMAIN>/webapp/` возвращает `200`
- `curl -I https://<APP_DOMAIN>/api/v1/auth/access-status` возвращает `401` для неавторизованного запроса, что считается нормой
- `curl -fsS https://<APP_DOMAIN>/api/v1/health/livez` возвращает `{"status":"ok"}`
- `docker compose -f docker-compose.prod.yml exec altshop python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:5000/api/v1/internal/readiness', timeout=5).status)"` печатает `200`, пока PostgreSQL и Redis доступны; `remnawave` может быть `degraded` внутри JSON без провала readiness
- `docker compose -f docker-compose.prod.yml exec altshop python -c "import urllib.request; print('payment_webhook_enqueue_failures_total' in urllib.request.urlopen('http://127.0.0.1:5000/api/v1/internal/metrics', timeout=5).read().decode())"` печатает `True`
- `docker compose -f docker-compose.prod.yml ps` показывает `altshop` в `healthy`, а worker/scheduler стартуют после backend readiness probe
- `altshop-nginx` находится в `healthy`
- `altshop-db` и `altshop-redis` находятся в `healthy`
- в логах `altshop` нет ошибок `alembic upgrade head`

## Ограничения и замечания

- `docker-compose.yml` остается build-based и требует локальной сборки frontend и backend.
- `docker-compose.prod.yml` рассчитан на image-based VPS deploy через GHCR.
- сертификаты не должны попадать в git; они живут только на VPS и монтируются в `altshop-nginx`.
- versioned image tags сохраняются для rollback, даже если production по умолчанию использует `latest`.
