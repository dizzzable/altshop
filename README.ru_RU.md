<div align="center">
  <h1>AltShop</h1>
  <p><strong>Telegram-бот, FastAPI API и React web app для продажи VPN-подписок с интеграцией Remnawave.</strong></p>
  <p><a href="./README.md">ENGLISH</a> | РУССКИЙ</p>
  <p>
    <a href="https://github.com/dizzzable/altshop/actions/workflows/ci.yml">
      <img src="https://img.shields.io/github/actions/workflow/status/dizzzable/altshop/ci.yml?branch=main&label=CI&logo=githubactions&logoColor=white" alt="CI status" />
    </a>
    <a href="https://github.com/dizzzable/altshop/actions/workflows/release.yml">
      <img src="https://img.shields.io/github/actions/workflow/status/dizzzable/altshop/release.yml?label=Release&logo=githubactions&logoColor=white" alt="Release status" />
    </a>
    <a href="https://github.com/dizzzable/altshop/releases/latest">
      <img src="https://img.shields.io/github/v/release/dizzzable/altshop?display_name=tag&logo=github" alt="Latest release" />
    </a>
    <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12" />
    <img src="https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white" alt="FastAPI Backend" />
    <img src="https://img.shields.io/badge/React-19-149ECA?logo=react&logoColor=white" alt="React 19" />
    <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose" />
    <img src="https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL 17" />
    <img src="https://img.shields.io/github/license/dizzzable/altshop" alt="MIT License" />
  </p>
</div>

> [!IMPORTANT]
> В текущей ветке `main` нет отдельной web admin panel в составе стандартного runtime stack.
> Основная админка сейчас встроена в Telegram dashboard и operator flows внутри бота.

> [!TIP]
> Если ты уже работал с `snoups/remnashop`, деплой здесь будет очень знакомым.
> По практике настройки `.env`, Docker Compose и Nginx этот проект ощущается почти один в один.

## ✨ Что Это За Проект

AltShop это production-ориентированный стек для продажи и обслуживания VPN-подписок. Репозиторий объединяет:

- Telegram-бота на `aiogram`
- FastAPI backend с cookie-based web auth
- отдельный React/Vite frontend
- PostgreSQL, Valkey, Taskiq workers и Nginx
- интеграцию с Remnawave для жизненного цикла подписок и синхронизации

Актуальная точка входа в документацию находится в [`docs/README.md`](./docs/README.md).

## 👥 Что Получает Каждая Роль

| Роль | Что получает |
| --- | --- |
| Владелец сервиса | Каталог тарифов, branding, access rules, платежные шлюзы, referral и partner механики, backup и синхронизацию с Remnawave |
| Админ или оператор | Telegram dashboard для пользователей, тарифов, шлюзов, уведомлений, рассылок, импортов, partner withdrawals и operational settings |
| Покупатель | Telegram и web purchase flow, trial access, device management, promocodes, referral rewards, partner cabinet и account recovery |

## 🛍️ Что Получает Покупатель Подписки

После запуска сервиса пользователь может:

- авторизоваться по username/password или через Telegram auth
- заранее видеть требования к регистрации и доступу
- принимать правила и проходить channel gating, если он включен
- открывать web cabinet и видеть подписки, транзакции и уведомления
- покупать новую подписку, продлевать текущую или докупать дополнительную
- получать trial subscription, если она разрешена настройками
- выбирать тариф, длительность, тип устройства, способ оплаты и платежный asset
- управлять устройствами, генерировать connection links и отзывать старые устройства
- активировать промокоды и смотреть историю активаций
- привязывать Telegram к web account
- подтверждать email, восстанавливать пароль по коду или ссылке и менять пароль в профиле
- использовать referral links, referral QR и обмен points
- открывать partner cabinet, смотреть earnings и отправлять withdrawal requests

## 🛠️ Что Умеет Панель Управления

Основная встроенная админка в Telegram сейчас покрывает:

- access modes: `PUBLIC`, `INVITED`, `PURCHASE_BLOCKED`, `REG_BLOCKED`, `RESTRICTED`
- принятие правил и обязательную подписку на канал
- поиск пользователей, recent users, blacklist и подробные user cards
- изменение подписок и assignment settings
- настройку plans, durations, prices, availability и squads
- создание и настройку promocodes
- активацию payment gateways, ввод credentials, webhook settings, display order и default currency
- настройку referral program, eligible plans, reward strategy и points exchange
- настройку partner program: проценты, налоги, комиссии gateway, minimum withdrawal и очередь на review
- multi-subscription limits
- branding texts, project name, web title, verification messages и banners
- user и system notifications
- broadcasts по сегментам аудитории
- создание, просмотр, восстановление и отправку backups
- Remnawave integration views и import/sync flows
- statistics и operational snapshots

## ⚙️ Что Можно Настраивать

### 🔐 Доступ И Продуктовая Логика

- режим доступа к сервису
- обязательное принятие правил
- обязательную подписку на канал
- single-subscription или multi-subscription mode
- базовую локаль и список доступных локалей

### 💳 Каталог И Цены

- тарифы и длительности
- порядок показа и доступность тарифов
- сценарии продления и дополнительной покупки
- default settlement currency
- поведение цен по отдельным gateway

### 💸 Платежи

Сейчас в кодовой базе поддерживаются 14 gateway types:

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

По умолчанию активен только `Telegram Stars`. Остальные gateway нужно явно настроить и включить.

### 🎁 Referral И Partner Механики

- тип referral-награды: points или extra days
- reward strategy и eligible plans
- обмен points в subscription days, gift subscriptions, discounts и traffic
- проценты по partner levels
- модель комиссий платежных систем
- налоговый процент
- минимальную сумму на вывод

### 🎨 Брендинг И Пользовательский Контур

- project name и web title
- локализованные verification и recovery messages
- support username links
- banners и локализованный текст

### 🧱 Инфраструктура

- домен и доверенные proxy IP
- JWT secret для web auth
- CORS origins
- SMTP для verify и reset flow
- backup retention и отправку backup в Telegram

## 🚀 Как Правильно Настроить И Запустить

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
- не ставь `BOT_MINI_APP=true`; используй `false`, пустое значение или точный URL mini app

### 4. Включить опциональные сценарии

Если нужен email verify и password recovery:

- поставь `EMAIL_ENABLED=true`
- заполни `EMAIL_HOST`
- заполни `EMAIL_FROM_ADDRESS`
- добавь SMTP credentials, если это требует провайдер

### 5. Выпустить TLS-файлы прямо на VPS

Для pull-based production стека рекомендуемый выпуск сертификатов такой:

```bash
acme.sh --issue --standalone -d '<domain>' \
  --key-file /opt/altshop/nginx/remnabot_privkey.key \
  --fullchain-file /opt/altshop/nginx/remnabot_fullchain.pem
```

### 6. Один раз открыть GHCR packages

Release workflow публикует два пакета:

- `ghcr.io/dizzzable/altshop-backend`
- `ghcr.io/dizzzable/altshop-nginx`

Если GitHub создаст их приватными при первой публикации, один раз переведи оба пакета в `Public` в настройках Packages этого репозитория. После этого VPS сможет делать `pull` без `docker login`.

### 7. Обновить и поднять VPS стек

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

Доступные production overrides:

- `ALTSHOP_IMAGE_TAG` для pin конкретного backend release вместо `latest`
- `ALTSHOP_NGINX_IMAGE_TAG` для pin конкретного nginx/web release вместо `latest`
- `NGINX_SSL_FULLCHAIN_PATH` и `NGINX_SSL_PRIVKEY_PATH`, если сертификаты лежат не в `/opt/altshop/nginx`

### 8. Проверить публичные точки входа

- `https://<APP_DOMAIN>/webapp/`
- `https://<APP_DOMAIN>/api/v1/auth/branding`

### 9. Сделать первичную настройку в админке бота

Рекомендуемый порядок:

1. Проверить access mode и channel or rules requirements.
2. Создать или проверить планы, длительности и цены.
3. Активировать и настроить payment gateways.
4. Проверить branding и support links.
5. Настроить referral и partner rules, если они нужны.
6. Проверить backup и notification behavior.

### Локальный/manual build fallback

Если нужен старый сценарий с локальной сборкой из исходников, продолжай использовать существующий `docker-compose.yml`:

```text
nginx/fullchain.pem
nginx/privkey.key
```

```bash
docker compose up --build
```

## 🧩 Что Входит В Runtime Stack

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

## 🗂️ Структура Публичного Репозитория

```text
altshop/
|-- src/                 backend application code
|-- web-app/             React/Vite frontend
|-- assets/              translations и default runtime assets
|-- nginx/               Nginx config и TLS mount paths
|-- docs/                canonical и historical documentation
|-- scripts/             maintenance и audit helpers
|-- docker-compose.yml   основной deployment contract
`-- Dockerfile           backend container image
```

## 🔒 Что Остается Только Локально

Этот GitHub-репозиторий намеренно не содержит внутренние QA-артефакты.

- `tests/` остается локально и не нужен для runtime deploy
- временные `mypy-wave*.ini` остаются локально и не являются частью продукта
- GitHub Actions здесь проверяет только публичную frontend-поверхность
- Ruff-конфиг лежит в [`pyproject.toml`](./pyproject.toml)
- отдельного `ruff.ini` в этом репозитории нет

## 🧪 Локальная Разработка

Публичные backend checks:

```bash
uv sync --locked --group dev
uv run python -m ruff check src
uv run python -m mypy src
```

Frontend:

```bash
cd web-app
npm ci
npm run lint
npm run type-check
npm run build
```

Если работа идет во внутреннем локальном workspace, дополнительно можно гонять приватный backend `pytest` suite.

## 📚 Документация

Стартовая точка:

- [`CHANGELOG.md`](./CHANGELOG.md)
- [`docs/README.md`](./docs/README.md)

Канонические документы:

- [`docs/01-project-overview.md`](./docs/01-project-overview.md)
- [`docs/05-api.md`](./docs/05-api.md)
- [`docs/06-bot-dialogs.md`](./docs/06-bot-dialogs.md)
- [`docs/07-payment-gateways.md`](./docs/07-payment-gateways.md)
- [`docs/08-configuration.md`](./docs/08-configuration.md)
- [`docs/09-deployment.md`](./docs/09-deployment.md)
- [`docs/10-development.md`](./docs/10-development.md)

## ⚖️ Лицензия

MIT. См. [`LICENSE`](./LICENSE).
