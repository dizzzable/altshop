# AltShop Configuration

Проверено по коду: `2026-03-08`

## Источники истины

- `src/core/config/app.py`
- `src/core/config/bot.py`
- `src/core/config/web_app.py`
- `src/core/config/email.py`
- `src/core/config/remnawave.py`
- `src/core/config/database.py`
- `src/core/config/redis.py`
- `src/core/config/backup.py`
- `.env.example`
- runtime usage в `src/api/app.py`, `src/api/endpoints/web_auth.py`, `src/core/security/jwt_handler.py`, `src/services/email_sender.py`

## Ключевые расхождения template vs runtime

| Переменная | Что есть в коде сейчас |
| --- | --- |
| `APP_ORIGINS` | Реально используется FastAPI CORS (`allow_origins=config.origins`), но отсутствует в `.env.example`. Добавлять вручную. |
| `WEB_APP_CORS_ORIGINS` | Есть в `.env.example` и `WebAppConfig`, но текущий FastAPI CORS ее не читает. Для API сейчас важен `APP_ORIGINS`. |
| `BOT_SETUP_WEBHOOK` | Есть только в `.env.example`. В текущем `BotConfig` и runtime-потоке такого флага нет. |
| `BOT_MINI_APP` | Комментарий в `.env.example` допускает `true`, но валидатор принимает только пустое значение, `false` или точный URL. |
| `WEB_APP_JWT_EXPIRY` | Есть в `WebAppConfig`, но текущий `jwt_handler.py` использует хардкод `7 days`. |
| `WEB_APP_JWT_REFRESH_ENABLED` | Есть в `WebAppConfig`, но текущие auth routes не отключают `/api/v1/auth/refresh` по этому флагу. |
| `WEB_APP_API_SECRET_TOKEN` | Валидируется конфигом, но активного runtime consumer в текущем коде нет. |

2026-03-27 runtime correction:

- `BOT_SETUP_WEBHOOK` is now a live `BotConfig` field and controls `WebhookService.setup()` on startup plus webhook cleanup eligibility on shutdown.
- `BOT_FETCH_ME_ON_STARTUP` is also live and gates the startup `bot.get_me()` call in `src/lifespan.py`.

## AppConfig (`APP_*`)

| Variable | Required | Code default | Example/template | Runtime notes |
| --- | --- | --- | --- | --- |
| `APP_DOMAIN` | yes | none | `change_me` | Публичный домен без схемы; используется для webhook URLs и fallback web URLs. |
| `APP_ALLOWED_HOSTS` | no | `APP_DOMAIN,localhost,127.0.0.1,::1` | `vpn.example.com,api.vpn.example.com` | Явный allowlist для `Host` header через `TrustedHostMiddleware`. Если нужен доступ по нескольким DNS-именам, перечислите их здесь. |
| `APP_HOST` | no | `0.0.0.0` | `0.0.0.0` | Bind host для uvicorn. |
| `APP_PORT` | no | `5000` | `5000` | Bind port для uvicorn/compose runtime. |
| `APP_LOCALES` | no | `en` | `ru,en` | Список поддерживаемых локалей. Значение template расходится с code default. |
| `APP_DEFAULT_LOCALE` | no | `en` | `ru` | Базовая локаль UI/branding. Значение template расходится с code default. |
| `APP_CRYPT_KEY` | yes | none | `change_me` | Используется для шифрования чувствительных данных и подписи redirect token для YooMoney. |
| `APP_ORIGINS` | no | empty list | absent | Реальный список CORS origins для FastAPI API. |
| `APP_TRUSTED_PROXY_IPS` | no | `127.0.0.1,::1` | `127.0.0.1,::1` | Ограничивает доверие к `X-Forwarded-For`/`X-Real-IP` и пробрасывается в `uvicorn --forwarded-allow-ips`. |

## BotConfig (`BOT_*`)

Authoritative startup-toggle correction for this section:

- `BOT_SETUP_WEBHOOK` is a live `BotConfig` field with code default `true`; it drives `WebhookService.setup()` on startup and allows webhook deletion on shutdown together with `BOT_RESET_WEBHOOK`.
- `BOT_FETCH_ME_ON_STARTUP` is a live `BotConfig` field with code default `true`; it gates the startup `bot.get_me()` probe in `src/lifespan.py`.

| Variable | Required | Code default | Example/template | Runtime notes |
| --- | --- | --- | --- | --- |
| `BOT_TOKEN` | yes | none | `change_me` | Telegram Bot API token. |
| `BOT_SECRET_TOKEN` | yes | none | `change_me` | Секрет для Telegram webhook и `TelegramWebhookEndpoint`. |
| `BOT_DEV_ID` | yes | none | `change_me` | Один ID или CSV; используется для привилегий/системных flows. |
| `BOT_SUPPORT_USERNAME` | yes | none | `change_me` | Строит support URL для web branding. |
| `BOT_MINI_APP` | no | `false` | `false` | Допустимы только пустое значение, `false` или точный URL. Литеральное `true` сейчас невалидно. |
| `BOT_RESET_WEBHOOK` | no | `false` | `false` | При shutdown удаляет Telegram webhook. |
| `BOT_DROP_PENDING_UPDATES` | no | `false` | `false` | Пробрасывается в setup webhook flow. |
| `BOT_SETUP_COMMANDS` | no | `true` | `true` | Включает startup setup bot commands. |
| `BOT_USE_BANNERS` | no | `true` | `true` | Управляет использованием banner assets в bot UI. |
| `BOT_SETUP_WEBHOOK` | example-only | n/a | `false` | Есть только в `.env.example`; в текущем коде не читается. |

## WebAppConfig (`WEB_APP_*`)

Update on 2026-03-27 for bot startup toggles:

- `BOT_SETUP_WEBHOOK` is now wired into the runtime and controls webhook setup/delete during startup and shutdown.
- `BOT_FETCH_ME_ON_STARTUP` is now available for smoke checks that must skip the Telegram `get_me()` call while still booting the containerized app.

| Variable | Required | Code default | Example/template | Runtime notes |
| --- | --- | --- | --- | --- |
| `WEB_APP_ENABLED` | no | `true` | `true` | Поле есть в конфиге, но текущая регистрация роутов/Nginx не отключается этим флагом. |
| `WEB_APP_URL` | conditional | `None` | `https://app.yourdomain.com` | Используется для verify/reset links, referral web links и broadcast links. Если пусто, код фолбечит к `https://APP_DOMAIN/webapp`. |
| `WEB_APP_JWT_SECRET` | yes in practice | empty string | `change_me_to_a_secure_random_string_at_least_32_chars` | JWT access/refresh токены не работают без непустого секрета длиной не менее 32 символов. |
| `WEB_APP_JWT_EXPIRY` | config-only | `604800` | `604800` | Есть в конфиге, но текущий `jwt_handler.py` использует хардкод `7 days`. |
| `WEB_APP_CORS_ORIGINS` | config-only | empty list | `https://app.yourdomain.com` | Значение попадает в `WebAppConfig`, но FastAPI CORS сейчас использует `APP_ORIGINS`. |
| `WEB_APP_JWT_REFRESH_ENABLED` | config-only | `true` | `true` | Toggle есть, но `/api/v1/auth/refresh` не зависит от него. |
| `WEB_APP_API_SECRET_TOKEN` | config-only | empty string | `change_me_to_another_secure_random_string` | Валидируется как минимум 16 символов, но активного runtime consumer в коде не найдено. |
| `WEB_APP_RATE_LIMIT_ENABLED` | no | `true` | `true` | Включает Redis-backed rate limit в web auth flows. |
| `WEB_APP_RATE_LIMIT_MAX_REQUESTS` | no | `60` | `60` | Лимит запросов за окно rate limit. |
| `WEB_APP_RATE_LIMIT_WINDOW` | no | `60` | `60` | Окно rate limit в секундах. |
| `WEB_APP_TELEGRAM_LINK_CODE_TTL_SECONDS` | no | `600` | `600` | TTL challenge-кодов для Telegram link confirm/request. |
| `WEB_APP_EMAIL_VERIFY_TTL_SECONDS` | no | `1800` | `1800` | TTL email verification challenges. |
| `WEB_APP_PASSWORD_RESET_TTL_SECONDS` | no | `1800` | `1800` | TTL password reset challenges. |
| `WEB_APP_AUTH_CHALLENGE_ATTEMPTS` | no | `5` | `5` | Количество попыток на challenge. |
| `WEB_APP_LINK_PROMPT_SNOOZE_DAYS` | no | `3` | `3` | Сколько дней не показывать prompt после `telegram-link/remind-later`. |
| `WEB_APP_REGISTER_RATE_LIMIT_IP_MAX_REQUESTS` | no | `10` | `10` | Порог для `POST /api/v1/auth/register` на один client IP в пределах `WEB_APP_RATE_LIMIT_WINDOW`; снижайте при явном бот-спаме, повышайте если много пользователей за общим NAT. |
| `WEB_APP_REGISTER_RATE_LIMIT_IDENTITY_MAX_REQUESTS` | no | `5` | `5` | Порог для `POST /api/v1/auth/register` на один username или переданный `telegram_id`; ограничивает перебор логинов и повторные Telegram link-code триггеры. |
| `WEB_APP_TELEGRAM_AUTH_RATE_LIMIT_IP_MAX_REQUESTS` | no | `30` | `30` | Порог для `POST /api/v1/auth/telegram` на один client IP; держится выше, чем register, чтобы не резать легитимные shared-network логины. |
| `WEB_APP_TELEGRAM_AUTH_RATE_LIMIT_IDENTITY_MAX_REQUESTS` | no | `10` | `10` | Порог для `POST /api/v1/auth/telegram` на один Telegram identity; помогает сдерживать replay и повторные невалидные auth attempts по одному `id`. |

## EmailConfig (`EMAIL_*`)

| Variable | Required | Code default | Example/template | Runtime notes |
| --- | --- | --- | --- | --- |
| `EMAIL_ENABLED` | no | `false` | `false` | Если выключено, verify/reset email flows не шлют письма. |
| `EMAIL_HOST` | conditional | empty string | empty | SMTP host. |
| `EMAIL_PORT` | no | `587` | `587` | Должен быть положительным числом. |
| `EMAIL_USERNAME` | no | `None` | empty | SMTP username. |
| `EMAIL_PASSWORD` | no | `None` | empty | SMTP password. |
| `EMAIL_FROM_ADDRESS` | conditional | empty string | `no-reply@2get.pro` | Обязателен для реальной отправки. |
| `EMAIL_FROM_NAME` | no | `AltShop` | `AltShop` | Display name отправителя. |
| `EMAIL_USE_TLS` | no | `true` | `true` | STARTTLS режим для обычного SMTP. |
| `EMAIL_USE_SSL` | no | `false` | `false` | SSL SMTP режим; если включен, используется `SMTP_SSL`. |

## RemnawaveConfig (`REMNAWAVE_*`)

| Variable | Required | Code default | Example/template | Runtime notes |
| --- | --- | --- | --- | --- |
| `REMNAWAVE_HOST` | yes | `remnawave` | `remnawave` | `remnawave` трактуется как docker-service с `http://`; любой другой валидный домен трактуется как внешний `https://`. |
| `REMNAWAVE_PORT` | no | `3000` | `3000` | Используется только для docker/local сценария с host=`remnawave`. |
| `REMNAWAVE_TOKEN` | yes | none | `change_me` | API token клиента Remnawave. |
| `REMNAWAVE_WEBHOOK_SECRET` | yes | none | `change_me` | Секрет проверки `/api/v1/remnawave`. |
| `REMNAWAVE_CADDY_TOKEN` | no | empty string | empty | Дополнительный `X-Api-Key` для Caddy-protected Remnawave. |
| `REMNAWAVE_COOKIE` | no | empty string | empty | Дополнительный cookie `key=value` для доступа к Remnawave API. |

## DatabaseConfig (`DATABASE_*`)

| Variable | Required | Code default | Example/template | Runtime notes |
| --- | --- | --- | --- | --- |
| `DATABASE_HOST` | no | `altshop-db` | `altshop-db` | PostgreSQL host. |
| `DATABASE_PORT` | no | `5432` | `5432` | PostgreSQL port. |
| `DATABASE_NAME` | no | `altshop` | `altshop` | DB name. |
| `DATABASE_USER` | no | `altshop` | `altshop` | DB user. |
| `DATABASE_PASSWORD` | yes | none | `change_me` | Используется для async DSN и compose env. |
| `DATABASE_ECHO` | no | `false` | `false` | Лог SQL statements. |
| `DATABASE_ECHO_POOL` | no | `false` | `false` | Лог pool behaviour. |
| `DATABASE_POOL_SIZE` | no | `25` | `25` | SQLAlchemy pool size. |
| `DATABASE_MAX_OVERFLOW` | no | `25` | `25` | Pool overflow limit. |
| `DATABASE_POOL_TIMEOUT` | no | `10` | `10` | Время ожидания соединения. |
| `DATABASE_POOL_RECYCLE` | no | `3600` | `3600` | Lifetime соединения перед recycle. |

## RedisConfig (`REDIS_*`)

| Variable | Required | Code default | Example/template | Runtime notes |
| --- | --- | --- | --- | --- |
| `REDIS_HOST` | no | `altshop-redis` | `altshop-redis` | Redis/Valkey host. |
| `REDIS_PORT` | no | `6379` | `6379` | Redis/Valkey port. |
| `REDIS_NAME` | no | `0` | `0` | Database index для DSN. |
| `REDIS_PASSWORD` | yes | none | `change_me` | Используется runtime и compose healthcheck. |

## BackupConfig (`BACKUP_*`)

| Variable | Required | Code default | Example/template | Runtime notes |
| --- | --- | --- | --- | --- |
| `BACKUP_AUTO_ENABLED` | no | `false` | `false` | Включает автоматический backup loop на startup. |
| `BACKUP_INTERVAL_HOURS` | no | `24` | `24` | Интервал между backup jobs. |
| `BACKUP_TIME` | no | `03:00` | `03:00` | Время запуска daily backup. |
| `BACKUP_MAX_KEEP` | no | `7` | `7` | Максимум хранимых архивов. |
| `BACKUP_COMPRESSION` | no | `true` | `true` | Gzip compression для архивов. |
| `BACKUP_INCLUDE_LOGS` | no | `false` | `false` | Включать ли `logs/` в backup. |
| `BACKUP_LOCATION` | no | `/app/data/backups` | `/app/data/backups` | Директория хранения backup-архивов. |
| `BACKUP_SEND_ENABLED` | no | `false` | `false` | Разрешает отправку backup в Telegram. |
| `BACKUP_SEND_CHAT_ID` | conditional | `None` | empty | Нужен вместе с `BACKUP_SEND_ENABLED=true`. |
| `BACKUP_SEND_TOPIC_ID` | no | `None` | empty | Опциональный forum topic id для Telegram. |

## Frontend build env

| Variable | Required | Code default | Example/template | Runtime notes |
| --- | --- | --- | --- | --- |
| `VITE_SOURCEMAP` | no | `false` | `false` | Читается только `web-app/vite.config.ts`; включает sourcemaps при `npm run build`. |

## Практические замечания

- Для browser/web-app auth сейчас критичны `WEB_APP_JWT_SECRET`, `APP_CRYPT_KEY`, `APP_DOMAIN`, `APP_ALLOWED_HOSTS`, `APP_TRUSTED_PROXY_IPS`, `APP_ORIGINS`.
- Если backend должен отвечать на несколько DNS-имен, перечисляйте их в `APP_ALLOWED_HOSTS`; одного `APP_DOMAIN` недостаточно для дополнительных host aliases.
- Если API стоит за Nginx или иным reverse proxy, список `APP_TRUSTED_PROXY_IPS` должен включать адреса этого proxy, иначе `resolve_client_ip()` будет игнорировать forwarded headers.
- Если используется frontend на отдельном origin, добавляйте его в `APP_ORIGINS`, а не только в `WEB_APP_CORS_ORIGINS`.
- Если нужен email verify/reset flow, одного `EMAIL_ENABLED=true` недостаточно: должны быть заполнены `EMAIL_HOST` и `EMAIL_FROM_ADDRESS`, а при необходимости и SMTP credentials.
- `make setup-env` не заполняет `WEB_APP_JWT_SECRET` и не чинит отсутствующий `APP_ORIGINS`; эти значения нужно добавить вручную.
