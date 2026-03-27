# AltShop Web App

Last audited against the live repository: `2026-03-26`

## Overview

`web-app/` is the standalone React/Vite frontend served by Nginx under `/webapp/`. It is the buyer-facing web surface for:

- login and registration
- Telegram widget and Telegram Mini App auth
- subscription purchase, renew, and upgrade flows
- devices, referrals, promocodes, partner cabinet, notifications, and settings

There is no separate web admin panel in this project. Operator flows remain in the Telegram dashboard.

## Current stack

- React `19.2.4`
- TypeScript `5.7.x`
- Vite `7.3.x`
- Tailwind CSS `4.x`
- React Router `7.x`
- TanStack Query `5.x`
- Zustand `5.x`
- Radix UI primitives plus local `src/components/ui/*`
- Axios for API calls

## Runtime contract

### Production hosting

- the frontend build is published under the fixed base path `/webapp/`
- exact requests to `/webapp/` are proxied to `/api/v1/auth/webapp-shell` so branding can shape the shell HTML
- other `/webapp/*` paths are served as static SPA assets from Nginx
- frontend API calls target `/api/v1`

### Development hosting

- `npm run dev` starts Vite on `http://localhost:3000`
- `vite.config.ts` proxies `/api` to `http://localhost:5000`
- the production `base` remains `/webapp/`, so route helpers should not assume root hosting

## Route map

Current route ownership from `src/App.tsx`:

| Route | Purpose |
| --- | --- |
| `/` | browser landing page |
| `/entry` | alternate landing entry |
| `/miniapp` | Telegram Mini App landing and auto-auth entry |
| `/payment-return` | payment return handler |
| `/auth/login` | browser login |
| `/auth/register` | browser registration |
| `/auth/forgot-password` | forgot password |
| `/auth/reset-password` | password reset |
| `/auth/telegram/callback` | Telegram widget callback handoff |
| `/dashboard` | protected shell |
| `/dashboard/subscription` | subscription detail entry |
| `/dashboard/subscription/purchase` | new purchase flow |
| `/dashboard/subscription/:id/renew` | renew flow |
| `/dashboard/subscription/:id/upgrade` | upgrade flow |
| `/dashboard/devices` | device management |
| `/dashboard/referrals` | referrals |
| `/dashboard/promocodes` | promocodes |
| `/dashboard/partner` | partner cabinet |
| `/dashboard/settings` | account settings |

## Authentication model

The current frontend does not treat `localStorage` as the source of truth for auth.

### What it uses now

- `axios` with `withCredentials: true`
- secure cookies issued by the backend:
  - `altshop_access_token`
  - `altshop_refresh_token`
  - `altshop_csrf_token`
- automatic refresh retry logic in `src/lib/api.ts`
- `X-CSRF-Token` on unsafe methods when the CSRF cookie is present

### Supported auth entry paths

- username and password via `/api/v1/auth/login`
- browser Telegram widget callback via `/api/v1/auth/telegram`
- Telegram Mini App `initData` auto-auth via `/api/v1/auth/telegram`
- web account bootstrap for already linked users via `/api/v1/auth/web-account/bootstrap`

`src/components/auth/AuthProvider.tsx` is the current source of truth for frontend auth behavior.

## Local development

### Install and run

```bash
cd web-app
npm ci
npm run dev
```

Expected backend companion process:

```bash
uv run uvicorn src.__main__:application --factory --reload --host 0.0.0.0 --port 5000
```

### Useful scripts

| Script | Purpose |
| --- | --- |
| `npm run dev` | start Vite dev server |
| `npm run build` | production build |
| `npm run preview` | preview the build |
| `npm run lint` | ESLint |
| `npm run type-check` | TypeScript type-check |
| `npm run check:encoding` | encoding guard |
| `npm run check:i18n` | i18n parity guard |
| `npm run generate:api` | generate TS API client from backend OpenAPI |

## Key source files

| Path | Why it matters |
| --- | --- |
| `src/App.tsx` | route topology |
| `src/components/auth/AuthProvider.tsx` | auth bootstrap, refresh, Telegram auth handoff |
| `src/lib/api.ts` | cookie auth, CSRF, refresh retry, endpoint wrappers |
| `src/hooks/useTelegramWebApp.ts` | Telegram environment detection |
| `src/pages/landing/LandingPage.tsx` | browser landing surface |
| `src/pages/landing/MiniAppLandingPage.tsx` | Telegram Mini App entry surface |
| `vite.config.ts` | `/webapp/` base path and `/api` dev proxy |

## Historical web-app notes

These files are still useful for implementation history, but they are not current runtime contracts:

| File | Status |
| --- | --- |
| [`AUTH_SYSTEM.md`](AUTH_SYSTEM.md) | historical implementation note |
| [`FIX_SUMMARY.md`](FIX_SUMMARY.md) | historical troubleshooting note |
| [`LANDING_PAGE.md`](LANDING_PAGE.md) | historical landing-page note |

Re-audit those files against code before relying on them for onboarding or deployment work.
