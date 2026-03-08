# AltShop Architecture

Проверено по коду: `2026-03-08`

## Слои системы

| Слой | Основные модули | Назначение |
| --- | --- | --- |
| Presentation | `src/api`, `src/bot`, `web-app` | HTTP endpoints, Telegram update handling, React UI |
| Application | `src/services` | orchestration бизнес-логики и межсервисных сценариев |
| Infrastructure | `src/infrastructure` | DB, Redis, Taskiq, DI, gateway adapters |
| Shared Core | `src/core` | enums, config, security, utility code |
| Data/Runtime | PostgreSQL, Valkey, Remnawave, assets, Nginx | persistence, queues, external panel, static delivery |

## DI и composition root

### FastAPI + aiogram composition

- `src.__main__.application()` создаёт `AppConfig`, `Dispatcher`, `FastAPI app` и Dishka container.
- `src/infrastructure/di/ioc.py` собирает `AsyncContainer`.
- Container получает `AppConfig` и `BgManagerFactory` через context.
- `setup_dishka` подключается и к aiogram, и к FastAPI.

### Provider set

`get_providers()` включает:

- `AiogramProvider`
- `BotProvider`
- `ConfigProvider`
- `DatabaseProvider`
- `FastapiProvider`
- `I18nProvider`
- `RedisProvider`
- `RemnawaveProvider`
- `ServicesProvider`
- `PaymentGatewaysProvider`

Это означает, что bot handlers, FastAPI endpoints и background/service objects получают один и тот же согласованный dependency graph.

## Lifespan orchestration

`src/lifespan.py` выполняет на старте:

1. Создание и нормализацию payment gateways в БД.
2. Загрузку `access_mode` через `SettingsService`.
3. Запуск auto-backup через `BackupService`.
4. Настройку Telegram webhook через `WebhookService.setup(...)`.
5. Настройку bot commands через `CommandService.setup()`.
6. Startup aiogram webhook endpoint.
7. Системные notification tasks и проверку соединения с Remnawave.

На shutdown:

1. Останавливаются auto-backups.
2. Отправляется shutdown notification.
3. Закрывается `TelegramWebhookEndpoint`.
4. Удаляются bot commands.
5. Условно удаляется webhook, если `BOT_RESET_WEBHOOK=true`.
6. Закрывается Dishka container.

## Bot flow

### Dispatcher storage

`create_dispatcher()` использует `RedisStorage.from_url(...)` с `DefaultKeyBuilder(with_bot_id=True, with_destiny=True)`.

### Middleware chain

`setup_middlewares()` регистрирует outer middlewares в таком порядке:

1. `ErrorMiddleware`
2. `AccessMiddleware`
3. `RulesMiddleware`
4. `UserMiddleware`
5. `ChannelMiddleware`
6. `ThrottlingMiddleware`

Inner middleware:

1. `GarbageMiddleware`

### Telegram webhook path

- фактический путь формируется как `API_V1 + BOT_WEBHOOK_PATH`
- при текущих константах это `/api/v1/telegram`
- endpoint регистрируется программно классом `TelegramWebhookEndpoint`

`TelegramWebhookEndpoint._handle_request()`:

1. сверяет `X-Telegram-Bot-Api-Secret-Token`
2. принимает `Update`
3. передаёт update в `dispatcher.feed_update(...)` через background task

## Web API flow

### App assembly

`src/api/app.py`:

- создаёт `FastAPI(lifespan=lifespan)`
- включает `CORSMiddleware`
- подключает routers: analytics, payments, remnawave, web auth, grouped user API
- регистрирует `TelegramWebhookEndpoint`

### CORS и proxy awareness

- `CORSMiddleware` использует `config.origins`, то есть `APP_ORIGINS`
- `APP_TRUSTED_PROXY_IPS` передаётся в uvicorn как `--forwarded-allow-ips`
- `resolve_client_ip()` доверяет `X-Forwarded-For` и `X-Real-IP` только если непосредственный клиент входит в trusted proxy list

## Web auth transport

### Основная модель

Primary transport для web auth это cookies:

- `altshop_access_token`
- `altshop_refresh_token`
- `altshop_csrf_token`

Cookies устанавливаются `set_auth_cookies()` со следующими параметрами:

- `HttpOnly=true` для access/refresh cookies
- `Secure=true`
- `SameSite=lax`
- refresh cookie ограничен path `/api/v1/auth`

### CSRF

`ensure_csrf_if_cookie_auth()` требует `X-CSRF-Token` на unsafe methods, если запрос использует auth cookie.

### Token verification

`get_current_user()`:

1. читает access token из cookie
2. при отсутствии cookie допускает `Authorization: Bearer ...`
3. валидирует JWT через `verify_access_token(...)`
4. проверяет `token_version` у `WebAccount`
5. возвращает `UserDto`

Для browser/UI документации bearer-token режим следует считать fallback/compatibility transport, а не primary flow.

## Purchase и payment flow

### Payment creation

`SubscriptionPurchaseService` рассчитывает quote/execute, а `PaymentGatewayService`:

1. выбирает concrete gateway instance
2. создаёт `TransactionDto`
3. получает `PaymentResult`
4. сохраняет транзакцию

### Payment webhook processing

`POST /api/v1/payments/{gateway_type}`:

1. читает raw body и `payload_hash`
2. выбирает gateway по `PaymentGatewayType`
3. вызывает `gateway.handle_webhook(request)`
4. записывает inbox-event через `PaymentWebhookEventService.record_received(...)`
5. при первом получении ставит в очередь `handle_payment_transaction_task`
6. помечает событие как `enqueued`

Дедупликация webhook delivery выполняется через таблицу `payment_webhook_events`.

### Background completion

Worker затем вызывает `PaymentGatewayService.handle_payment_succeeded()` или `handle_payment_canceled()`, а успешный платёж продолжает цепочку:

1. обновление transaction status
2. запуск `purchase_subscription_task`
3. referral reward assignment
4. partner earning processing

## Nginx contract

`nginx/nginx.conf` делает три вещи:

1. редиректит `/` на `/webapp/`
2. раздаёт SPA bundle из `/opt/altshop/webapp`
3. проксирует backend surfaces на `altshop:5000`

Ключевые детали:

- `location /api/v1` проксирует весь API
- sourcemaps под `/webapp` и `/assets` блокируются `404`
- передаются `X-Real-IP` и `X-Forwarded-*`
- upstream разрешается через Docker DNS `127.0.0.11`

## Почему это важно для документации

При описании AltShop нельзя смешивать старую модель проекта с текущей:

- web auth сейчас cookie-based, не bearer-only
- default deployment не содержит отдельного admin stack
- proxy/trusted IP handling является частью runtime contract
- Telegram webhook регистрируется программно, а не как обычный decorator route
