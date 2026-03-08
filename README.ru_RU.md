<div align="center">
  <h1>AltShop</h1>
  <p><strong>Telegram-бот, FastAPI API и React web app для продажи VPN-подписок с интеграцией Remnawave.</strong></p>
  <p><a href="./README.md">ENGLISH</a> | РУССКИЙ</p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12" />
    <img src="https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white" alt="FastAPI Backend" />
    <img src="https://img.shields.io/badge/React-19-149ECA?logo=react&logoColor=white" alt="React 19" />
    <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose" />
    <img src="https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL 17" />
    <img src="https://img.shields.io/github/license/dizzzable/altshop" alt="MIT License" />
  </p>
</div>

> [!IMPORTANT]
> В текущей основной ветке нет отдельной web admin panel в составе стандартного runtime stack.
> Управление проектом сейчас встроено в Telegram dashboard и operator flows внутри бота.

## Что Это

AltShop это production-ориентированный стек для продажи и обслуживания VPN-подписок. Репозиторий объединяет:

- Telegram-бота на `aiogram`
- FastAPI backend с cookie-based web auth
- отдельный React/Vite frontend
- PostgreSQL, Valkey, Taskiq workers и Nginx
- интеграцию с Remnawave для жизненного цикла подписок и синхронизации

Актуальная точка входа в документацию находится в [`docs/README.md`](./docs/README.md).

## Что Получает Проект

| Роль | Что получает |
| --- | --- |
| Владелец сервиса | Каталог тарифов, платежи, branding, access rules, referral и partner механики, backup, analytics и Remnawave integration |
| Администратор/оператор | Telegram dashboard для users, plans, gateways, notifications, broadcasts, branding, partner withdrawals, imports и backups |
| Покупатель подписки | Telegram и web purchase flows, device management, trial access, promocodes, notifications, referral rewards, partner cabinet и account recovery |

## Что Получает Покупатель Подписок

После запуска сервиса пользователь может:

- авторизоваться по username/password или через Telegram auth
- заранее видеть требования к регистрации и доступу
- принимать правила и проходить channel gating, если он включен
- открывать web cabinet и видеть подписки, транзакции и уведомления
- покупать новую подписку, продлевать существующую или докупать дополнительную
- получать trial subscription, если она разрешена настройками
- выбирать тариф, длительность, тип устройства, способ оплаты и платежный asset
- управлять устройствами, генерировать connection link и удалять старые устройства
- активировать промокоды и смотреть историю активаций
- привязывать Telegram к web account
- подтверждать email, восстанавливать пароль по коду или ссылке и менять пароль из профиля
- пользоваться referral links, referral QR и обменом points
- открывать partner cabinet, смотреть earnings и отправлять withdrawal requests

## Что Умеет Панель Управления

Сейчас основная админка находится в Telegram dashboard и покрывает:

- access modes: `PUBLIC`, `INVITED`, `PURCHASE_BLOCKED`, `REG_BLOCKED`, `RESTRICTED`
- принятие правил и обязательную подписку на канал
- поиск пользователей, recent users, blacklist и подробные user cards
- изменение подписок и assignment settings
- настройку plans, durations, prices, availability и squads
- создание и настройку promocodes
- активацию payment gateways, ввод credentials, настройку webhook данных, display order и default currency
- настройку referral program, eligible plans, reward strategy и points exchange
- настройку partner program: проценты, налоги, комиссии gateway, minimum withdrawal и очередь на review
- multi-subscription limits
- branding texts, project name, web title, verification messages и banners
- user/system notifications
- broadcasts по сегментам аудитории
- создание, просмотр, восстановление и отправку backups
- Remnawave integration views и import/sync flows
- statistics и operational snapshots

## Что Можно Настраивать

### Доступ И Продуктовая Логика

- режим доступа к сервису
- обязательное принятие правил
- обязательную подписку на канал
- базовую локаль и список поддерживаемых локалей
- single-subscription или multi-subscription mode

### Каталог И Цены

- планы и длительности
- порядок показа планов
- доступность тарифов
- default currency
- сценарии покупки, продления и дополнительной подписки

### Платежи

В текущем коде поддерживаются 14 gateway types:

- Telegram Stars
- YooKassa
- YooMoney
- Cryptomus
- Heleket
- CryptoPay
- T-Bank
- Robokassa
- Stripe
- Mulenpay
- CloudPayments
- Pal24
- Wata
- Platega

По умолчанию активен только `Telegram Stars`; остальные gateway нужно явно настроить и включить.

### Referral И Partner Механики

- тип реферальной награды: points или extra days
- reward strategy и eligible plans
- exchange points в subscription days, gift subscriptions, discounts и traffic
- проценты по partner levels
- модель комиссии платежных систем
- налоговый процент
- минимальную сумму на вывод

### Брендинг И Пользовательский Текст

- project name и web title
- локализованные verification/recovery messages
- support username links
- banners и локализованный текст

### Инфраструктура

- домен и доверенные proxy IP
- JWT secret для web auth
- CORS origins
- SMTP для verify/reset flows
- backup retention и отправку backup в Telegram

## Как Настроить Правильно

### 1. Подготовить `.env`

```bash
cp .env.example .env
```

### 2. Заполнить обязательные секреты

Минимально нужны:

- `APP_DOMAIN`
- `APP_CRYPT_KEY`
- `BOT_TOKEN`
- `BOT_SECRET_TOKEN`
- `BOT_DEV_ID`
- `BOT_SUPPORT_USERNAME`
- `WEB_APP_JWT_SECRET`
- `REMNAWAVE_TOKEN`
- `REMNAWAVE_WEBHOOK_SECRET`
- `DATABASE_PASSWORD`
- `REDIS_PASSWORD`

### 3. Правильно настроить web и proxy

Чтобы прод не ломался на auth и IP resolution:

- укажи `APP_ORIGINS` с реальными frontend origins
- держи `APP_TRUSTED_PROXY_IPS` синхронным с адресами reverse proxy
- задай `WEB_APP_URL`, если фронтенд живет на отдельном origin
- не ставь `BOT_MINI_APP=true`
  используй либо `false`, либо пустое значение, либо точный URL mini app

### 4. Включить опциональные сценарии

Если нужен email verify/reset flow:

- поставь `EMAIL_ENABLED=true`
- заполни `EMAIL_HOST`
- заполни `EMAIL_FROM_ADDRESS`
- добавь SMTP credentials, если это требует провайдер

### 5. Положить TLS-файлы

```text
nginx/fullchain.pem
nginx/privkey.key
```

### 6. Поднять стек

```bash
docker compose up --build
```

### 7. Проверить публичные точки входа

- `https://<APP_DOMAIN>/webapp/`
- `https://<APP_DOMAIN>/api/v1/auth/branding`

### 8. Сделать первичную настройку в админке бота

Рекомендуемый порядок:

1. Проверить access mode и channel/rules requirements.
2. Создать или проверить планы, длительности и цены.
3. Активировать и настроить payment gateways.
4. Проверить branding и support links.
5. Настроить referral и partner rules, если они нужны.
6. Проверить backup и notification behavior.

## Что Входит В Runtime Surface

Стандартный Docker stack содержит 7 сервисов:

- `webapp-build`
- `altshop-nginx`
- `altshop-db`
- `altshop-redis`
- `altshop`
- `altshop-taskiq-worker`
- `altshop-taskiq-scheduler`

Публичная поверхность:

- `/webapp/` для SPA
- `/assets/` для frontend assets
- `/api/v1/*` для backend API
- `/telegram` для Telegram webhook traffic
- `/remnawave` для Remnawave webhook traffic
- `/payments/*` для payment webhooks

## Структура Репозитория

```text
altshop/
|-- src/                 backend application code
|-- web-app/             React/Vite frontend
|-- assets/              translations и default runtime assets
|-- nginx/               Nginx config и TLS mount paths
|-- docs/                canonical и historical documentation
|-- tests/               developer-only backend test suite
|-- docker-compose.yml   основной deployment contract
`-- Dockerfile           backend container image
```

## Что Из Этого Нужно Пользователю Репозитория

Для deployer или владельца сервиса:

- `tests/` не нужны для runtime и не мешают работе продакшена
- GitHub Actions и локальные QA-команды не нужны для запуска
- Ruff-конфиг лежит в [`pyproject.toml`](./pyproject.toml)
- отдельного `ruff.ini` в этом репозитории нет

## Локальная Разработка

### Backend

```bash
uv sync --locked --group dev
uv run python -m pytest -q
```

### Frontend

```bash
cd web-app
npm ci
npm run lint
npm run type-check
npm run build
```

## Документация

Стартовая точка:

- [`docs/README.md`](./docs/README.md)

Канонические документы:

- [`docs/01-project-overview.md`](./docs/01-project-overview.md)
- [`docs/05-api.md`](./docs/05-api.md)
- [`docs/06-bot-dialogs.md`](./docs/06-bot-dialogs.md)
- [`docs/07-payment-gateways.md`](./docs/07-payment-gateways.md)
- [`docs/08-configuration.md`](./docs/08-configuration.md)
- [`docs/09-deployment.md`](./docs/09-deployment.md)
- [`docs/10-development.md`](./docs/10-development.md)

## CI

Сейчас GitHub Actions гоняет:

- backend `pytest`
- frontend `eslint`
- frontend `tsc --noEmit`
- frontend production build

## Лицензия

MIT. См. [`LICENSE`](./LICENSE).
