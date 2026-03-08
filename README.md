<div align="center">
  <h1>AltShop</h1>
  <p><strong>Telegram bot, FastAPI API, and React web app for selling VPN subscriptions with Remnawave integration.</strong></p>
  <p>ENGLISH | <a href="./README.ru_RU.md">РУССКИЙ</a></p>
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
> The current main branch does not ship a standalone web admin panel in the default runtime stack.
> Administrative control is built into the Telegram bot dashboard and operator flows.

## Overview

AltShop is a production-oriented stack for selling and servicing VPN subscriptions. It combines:

- a Telegram bot on `aiogram`
- a FastAPI backend with cookie-based web authentication
- a separate React/Vite web portal
- PostgreSQL, Valkey, Taskiq workers, and Nginx
- Remnawave integration for subscription lifecycle and synchronization

The current project surface is documented in [`docs/README.md`](./docs/README.md).

## What The Project Gives You

| Role | What they get |
| --- | --- |
| Service owner | Product catalog, payments, branding, access rules, referral and partner mechanics, backups, analytics, and Remnawave integration |
| Admin/operator | Telegram dashboard for users, plans, gateways, notifications, broadcasts, branding, partner withdrawals, imports, and backups |
| Buyer | Telegram and web purchase flows, device management, trial access, promocodes, notifications, referral rewards, partner cabinet, and account recovery |

## Buyer Experience

After deployment, a customer can:

- sign in through username/password or Telegram auth
- view access requirements before registration
- accept rules and pass channel gating if enabled
- open the web cabinet and see subscriptions, transactions, and notifications
- buy a new subscription, renew an existing one, or purchase an additional one
- get a trial subscription if the project allows it
- choose plan, duration, device type, payment method, and payment asset
- manage devices, generate connection links, and revoke old devices
- activate promocodes and view activation history
- link Telegram to a web account
- verify email, reset password by code or link, and change password from the profile
- use referral links, referral QR codes, and points exchange flows
- open the partner cabinet, inspect earnings, and request withdrawals

## Admin And Operator Capabilities

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
- backup creation, listing, restore, retention, and Telegram delivery
- Remnawave integration views and import/sync flows
- statistics and operational snapshots

## What Can Be Configured

### Product And Access

- public vs invited vs restricted access mode
- required rules acceptance
- required channel subscription
- default locale and supported locales
- single-subscription or multi-subscription mode

### Catalog And Pricing

- plans and durations
- plan availability and ordering
- per-gateway pricing behavior
- default settlement currency
- renew vs additional purchase flows

### Payments

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

`Telegram Stars` is the only gateway enabled by default; the rest must be configured and activated by the operator.

### Referral And Partner Programs

- referral reward type: points or extra days
- reward strategy and eligible plans
- points exchange for subscription days, gift subscriptions, discounts, and traffic
- partner level percentages
- gateway commission model
- tax percent
- minimum withdrawal amount

### User-Facing Branding

- project name and web title
- localized verification and recovery messages
- support username links
- banners and localized text content

### Infrastructure

- web domain and proxy trust rules
- web auth JWT secret
- CORS origins
- SMTP for verify/reset flows
- backup retention and Telegram backup delivery

## Deployment Checklist

### 1. Copy environment template

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

- set `APP_ORIGINS` to the real frontend origin list used by the browser
- keep `APP_TRUSTED_PROXY_IPS` aligned with the actual reverse proxy addresses
- set `WEB_APP_URL` if the frontend is served from a dedicated origin
- do not set `BOT_MINI_APP=true`
  use either `false`, an empty value, or the exact web app URL

### 4. Configure optional flows

If you want email verification and password recovery:

- set `EMAIL_ENABLED=true`
- fill `EMAIL_HOST`
- fill `EMAIL_FROM_ADDRESS`
- add SMTP credentials if required by your provider

### 5. Place TLS files

```text
nginx/fullchain.pem
nginx/privkey.key
```

### 6. Start the stack

```bash
docker compose up --build
```

### 7. Validate the public surface

- `https://<APP_DOMAIN>/webapp/`
- `https://<APP_DOMAIN>/api/v1/auth/branding`

### 8. Perform first admin setup in the bot dashboard

Recommended first actions:

1. Review access mode and channel/rules requirements.
2. Create or verify plans, durations, and pricing.
3. Activate and configure payment gateways.
4. Review branding and support links.
5. Configure referral and partner settings if you use them.
6. Check backup settings and notification behavior.

## Runtime Surface

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

## Repository Layout

```text
altshop/
|-- src/                 backend application code
|-- web-app/             React/Vite frontend
|-- assets/              translations and default runtime assets
|-- nginx/               Nginx config and TLS mount paths
|-- docs/                canonical and historical documentation
|-- tests/               developer-only backend test suite
|-- docker-compose.yml   default deployment contract
`-- Dockerfile           backend container image
```

## Developer-Only Files

For deployers and service owners:

- `tests/` is not required to run the project in production
- GitHub Actions and local QA scripts are not required for runtime
- Ruff configuration lives in [`pyproject.toml`](./pyproject.toml)
- there is no separate `ruff.ini` in this repository

## Local Development

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

## Documentation

Start here:

- [`docs/README.md`](./docs/README.md)

Canonical documents:

- [`docs/01-project-overview.md`](./docs/01-project-overview.md)
- [`docs/05-api.md`](./docs/05-api.md)
- [`docs/06-bot-dialogs.md`](./docs/06-bot-dialogs.md)
- [`docs/07-payment-gateways.md`](./docs/07-payment-gateways.md)
- [`docs/08-configuration.md`](./docs/08-configuration.md)
- [`docs/09-deployment.md`](./docs/09-deployment.md)
- [`docs/10-development.md`](./docs/10-development.md)

## CI

GitHub Actions currently runs:

- backend `pytest`
- frontend `eslint`
- frontend `tsc --noEmit`
- frontend production build

## License

MIT. See [`LICENSE`](./LICENSE).
