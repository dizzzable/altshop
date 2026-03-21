<div align="center">
  <h1>AltShop</h1>
  <p><strong>Telegram bot, FastAPI API, and React web app for selling VPN subscriptions with Remnawave integration.</strong></p>
  <p>ENGLISH | <a href="./README.ru_RU.md">РУССКИЙ</a></p>
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
> The current `main` branch does not ship a standalone web admin panel in the default runtime stack.
> Administrative control lives in the Telegram dashboard and operator flows inside the bot.

> [!TIP]
> If you already know `snoups/remnashop`, the deployment flow here should feel familiar.
> The environment setup, Docker stack, and Nginx wiring are intentionally close in day-to-day operation.

## ✨ What AltShop Is

AltShop is a production-oriented stack for selling and servicing VPN subscriptions. It combines:

- a Telegram bot on `aiogram`
- a FastAPI backend with cookie-based web authentication
- a separate React/Vite web portal
- PostgreSQL, Valkey, Taskiq workers, and Nginx
- Remnawave integration for subscription lifecycle and synchronization

The current project surface is documented in [`docs/README.md`](./docs/README.md).

## 👥 Who Gets What

| Role | What they get |
| --- | --- |
| Service owner | Product catalog, branding, access rules, payment gateways, referrals, partner mechanics, backups, and Remnawave sync |
| Admin/operator | Telegram dashboard for users, plans, gateways, notifications, broadcasts, imports, partner withdrawals, and operational settings |
| Buyer | Telegram and web purchase flows, trial access, device management, promocodes, referral rewards, partner cabinet, and account recovery |

## 🛍️ What Buyers Actually Get

After deployment, a customer can:

- sign in through username/password or Telegram auth
- see access requirements before registration
- accept rules and pass channel gating if enabled
- open the web cabinet and view subscriptions, transactions, and notifications
- buy a new subscription, renew an existing one, or add another one
- get a trial subscription if your project allows it
- choose a plan, duration, device type, payment method, and payment asset
- manage devices, generate connection links, and revoke old devices
- activate promocodes and review activation history
- link Telegram to a web account
- verify email, reset password by code or link, and change password in profile
- use referral links, referral QR codes, and points exchange flows
- open the partner cabinet, inspect earnings, and request withdrawals

## 🛠️ What The Admin Side Can Manage

The built-in Telegram dashboard currently covers:

- access modes: `PUBLIC`, `INVITED`, `PURCHASE_BLOCKED`, `REG_BLOCKED`, `RESTRICTED`
- rules acceptance and mandatory channel subscription gating
- user search, recent users, blacklist, and detailed user cards
- subscription editing and assignment changes
- plan configuration, durations, prices, availability, and squads
- promocode creation and reward configuration
- payment gateway activation, credentials, webhook settings, display order, and default currency
- referral program rules, eligible plans, reward strategy, and points exchange setup
- partner program percentages, tax model, gateway commissions, minimum withdrawal, and withdrawal review queue
- multi-subscription limits
- branding texts, project name, web title, verification messages, and banners
- user and system notification toggles
- broadcasts and audience segmentation
- backup creation, restore, retention, and Telegram delivery
- Remnawave integration views and import or sync flows
- statistics and operational snapshots

## ⚙️ What You Can Configure

### 🔐 Access And Product Logic

- public, invited, purchase-blocked, registration-blocked, or restricted entry mode
- required rules acceptance
- required Telegram channel subscription
- single-subscription or multi-subscription mode
- locale defaults and enabled locales

### 💳 Catalog And Pricing

- plans and durations
- plan ordering and availability
- renew vs additional purchase flows
- default settlement currency
- per-gateway pricing behavior

### 💸 Payments

The current codebase supports 14 gateway types:

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

`Telegram Stars` is the only gateway enabled by default. The others must be configured and activated by the operator.

### 🎁 Referral And Partner Mechanics

- referral reward type: points or extra days
- reward strategy and eligible plans
- points exchange into subscription days, gift subscriptions, discounts, and traffic
- partner level percentages
- gateway commission model
- tax percent
- minimum withdrawal amount

### 🎨 Branding And Support Surface

- project name and web title
- localized verification and recovery messages
- support username links
- banners and localized text content

### 🧱 Infrastructure

- web domain and proxy trust rules
- web auth JWT secret
- CORS origins
- SMTP for verify and reset flows
- backup retention and Telegram backup delivery

## 🚀 Production Setup

### 1. Copy the environment template

```bash
cp .env.example .env
```

### 2. Fill required secrets

At minimum:

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

### 3. Configure web and proxy behavior correctly

For a stable production setup:

- set `APP_ORIGINS` to the real frontend origin list used by browsers
- keep `APP_TRUSTED_PROXY_IPS` aligned with the actual reverse proxy addresses
- set `WEB_APP_URL` if the frontend is served from a dedicated origin
- do not set `BOT_MINI_APP=true`; use `false`, an empty value, or the exact web app URL

### 4. Configure optional flows

If you want email verification and password recovery:

- set `EMAIL_ENABLED=true`
- fill `EMAIL_HOST`
- fill `EMAIL_FROM_ADDRESS`
- add SMTP credentials if required by your provider

### 5. Issue TLS files on the VPS

Recommended target paths for the pull-based VPS stack:

```bash
acme.sh --issue --standalone -d '<domain>' \
  --key-file /opt/altshop/nginx/remnabot_privkey.key \
  --fullchain-file /opt/altshop/nginx/remnabot_fullchain.pem
```

### 6. Make GHCR packages public after the first release

The release workflow publishes:

- `ghcr.io/dizzzable/altshop-backend`
- `ghcr.io/dizzzable/altshop-nginx`

If GitHub creates them as private packages on the first push, switch both packages to `Public` once in the repository Packages settings. After that, the VPS can pull updates without `docker login`.

### 7. Pull and start the VPS stack

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

Optional production overrides:

- `ALTSHOP_IMAGE_TAG` to pin a backend release instead of `latest`
- `ALTSHOP_NGINX_IMAGE_TAG` to pin an nginx/web release instead of `latest`
- `NGINX_SSL_FULLCHAIN_PATH` and `NGINX_SSL_PRIVKEY_PATH` if your certificates live outside `/opt/altshop/nginx`

### 8. Validate the public surface

- `https://<APP_DOMAIN>/webapp/`
- `https://<APP_DOMAIN>/api/v1/auth/branding`

### 9. Complete first operator setup in the bot

Recommended first actions:

1. Review access mode and channel or rules requirements.
2. Create or verify plans, durations, and pricing.
3. Activate and configure payment gateways.
4. Review branding and support links.
5. Configure referral and partner settings if you use them.
6. Check backup settings and notification behavior.

### Local/manual build fallback

If you intentionally deploy from local sources instead of GHCR, keep using the existing build-based stack:

```text
nginx/fullchain.pem
nginx/privkey.key
```

```bash
docker compose up --build
```

## 🧩 Runtime Stack

The default Docker stack contains 7 services:

- `webapp-build`
- `altshop-nginx`
- `altshop-db`
- `altshop-redis`
- `altshop`
- `altshop-taskiq-worker`
- `altshop-taskiq-scheduler`

Public surface:

- `/webapp/` for the SPA
- `/assets/` for frontend assets
- `/api/v1/*` for the backend API
- `/telegram` for Telegram webhook traffic
- `/remnawave` for Remnawave webhook traffic
- `/payments/*` for payment webhooks

## 🗂️ Public Repository Layout

```text
altshop/
|-- src/                 backend application code
|-- web-app/             React/Vite frontend
|-- assets/              translations and default runtime assets
|-- nginx/               Nginx config and TLS mount paths
|-- docs/                canonical and historical documentation
|-- scripts/             maintenance and audit helpers
|-- docker-compose.yml   default deployment contract
`-- Dockerfile           backend container image
```

## 🔒 What Stays Local

This public GitHub mirror intentionally excludes internal-only QA artifacts.

- `tests/` stays local and is not required for runtime deployment
- temporary `mypy-wave*.ini` files stay local and are not part of the product
- GitHub Actions here only validates the public frontend surface
- Ruff configuration lives in [`pyproject.toml`](./pyproject.toml)
- there is no separate `ruff.ini` in this repository

## 🧪 Optional Local Development

Public mirror checks:

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

If you work in the private internal workspace, you can additionally run the local backend `pytest` suite there.

## 📚 Documentation

Start here:

- [`CHANGELOG.md`](./CHANGELOG.md)
- [`docs/README.md`](./docs/README.md)

Canonical documents:

- [`docs/01-project-overview.md`](./docs/01-project-overview.md)
- [`docs/05-api.md`](./docs/05-api.md)
- [`docs/06-bot-dialogs.md`](./docs/06-bot-dialogs.md)
- [`docs/07-payment-gateways.md`](./docs/07-payment-gateways.md)
- [`docs/08-configuration.md`](./docs/08-configuration.md)
- [`docs/09-deployment.md`](./docs/09-deployment.md)
- [`docs/10-development.md`](./docs/10-development.md)

## ⚖️ License

MIT. See [`LICENSE`](./LICENSE).
