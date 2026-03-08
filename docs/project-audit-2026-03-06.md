> [!WARNING]
> Исторический документ. Этот файл не входит в канонический комплект документации и не переаудировался в текущем проходе. Актуальная точка входа: [docs/README.md](README.md)

# AltShop Project Audit

Date: 2026-03-06

## Executive Summary

AltShop is functionally alive, but it is operating with a high level of production risk.
The most important issues are not cosmetic:

- the payments webhook acknowledges some internal failures as success
- channel-access enforcement degrades in fail-open mode
- rate limiting does not use the real client IP behind Nginx
- authentication is split across legacy and new flows with different JWT semantics
- backend quality gates are effectively red

The frontend compiles cleanly, but the production build is heavier than necessary, ships public source maps, and generates avoidable background traffic through fixed polling.

## Project Shape

- Backend:
  - FastAPI
  - aiogram
  - SQLAlchemy
  - Redis or Valkey
  - Taskiq
  - Remnawave integration
- Frontend:
  - React 19
  - Vite 7
  - TanStack Query 5
  - Radix UI
  - Zustand
- Infra:
  - Docker Compose
  - Nginx
  - Postgres 17

## Audit Method

The audit combined source inspection, local static checks, test execution, and a targeted review of official external guidance.

Reviewed areas:

- `src/api/endpoints/*`
- `src/services/*`
- `src/core/config/*`
- `src/infrastructure/*`
- `web-app/src/*`
- `docker-compose.yml`
- `nginx/nginx.conf`
- `Dockerfile`
- `docker-entrypoint.sh`

Commands executed:

- `.\.venv\Scripts\ruff.exe check .`
- `.\.venv\Scripts\python.exe -m pytest -q`
- `.\.venv\Scripts\python.exe -m mypy src`
- `npm ci`
- `npm run lint`
- `npm run type-check`
- `npm run build`

Official references were used where current behavior depends on modern framework guidance:

- FastAPI proxy handling
- Vite production build behavior
- TanStack Query fetch defaults
- Telegram Mini Apps init data model
- OWASP browser storage guidance
- Vercel Web Interface Guidelines

## Current State Snapshot

### Backend

- `ruff`: 325 issues
- `pytest`: 23 failed, 34 passed
- `mypy`: 233 errors in 33 files

Representative failure clusters:

- endpoint tests break because `@inject` expects request-scoped Dishka state
- `EmailRecoveryService` constructor drift broke existing tests
- `AccessService` does not tolerate `aiogram_user.language_code=None`
- command or mini-app URL tests no longer match current implementation

### Frontend

- `npm run lint`: pass
- `npm run type-check`: pass
- `npm run build`: pass

Largest production artifacts:

- `react-vendor-*.js`: about 247.63 KB
- `index-*.js`: about 180.01 KB
- `radix-vendor-*.js`: about 108.97 KB
- `react-vendor-*.js.map`: about 1435.17 KB
- `radix-vendor-*.js.map`: about 543.24 KB
- `index-*.js.map`: about 427 KB

Operational hygiene observations:

- 53 `__pycache__` directories exist under `src/` and `tests/`
- `web-app/react-doctor.latest.txt` points to an old path: `D:\altshop-0.9.3\web-app`
- several files contain mojibake or broken comments
- the local virtual environment was misconfigured and had to be repaired to run backend checks

## Confirmed Findings

### Critical

#### A1. Payments webhook returns HTTP 200 even after internal failure

Evidence:

- `src/api/endpoints/payments.py:42`
- `src/api/endpoints/payments.py:43`
- `src/api/endpoints/payments.py:53`
- `src/api/endpoints/payments.py:71`

Why it matters:

- the payment provider can stop retrying because it sees a successful delivery
- local payment state can drift from the provider state
- users can pay successfully while the application never finalizes access

Recommendation:

- return `5xx` when durable processing has not completed
- keep `4xx` only for validation or signature problems
- add idempotency protection keyed by `payment_id`

#### A2. Required channel membership check is implemented in fail-open mode

Evidence:

- `src/services/web_access_guard.py:176`
- `src/services/web_access_guard.py:179`
- `src/services/web_access_guard.py:198`
- `src/services/web_access_guard.py:204`

Why it matters:

- access restrictions are bypassed when configuration is wrong
- access restrictions are also bypassed when the Telegram API is unavailable
- the system becomes least secure exactly when dependencies are unstable

Recommendation:

- treat verification failure as an explicit unavailable state
- do not silently grant access when the result is unknown
- surface the incident in logs and metrics

#### A3. Web auth rate limiting ignores forwarded client IP headers

Evidence:

- `src/api/endpoints/web_auth.py:601`
- `src/api/endpoints/web_auth.py:602`
- `nginx/nginx.conf:74`
- `nginx/nginx.conf:92`
- `nginx/nginx.conf:108`
- `nginx/nginx.conf:124`
- `nginx/nginx.conf:142`

Why it matters:

- all users behind the reverse proxy can share one rate-limit bucket
- brute-force protection becomes inaccurate
- noisy clients can accidentally throttle unrelated users

Recommendation:

- read `X-Forwarded-For` or `X-Real-IP` only from trusted proxy hops
- configure FastAPI or Uvicorn proxy behavior explicitly
- test rate limiting through Nginx, not only direct localhost requests

### High

#### A4. Authentication surface is split across legacy and new flows

Evidence:

- `src/__main__.py:29`
- `src/api/endpoints/auth.py:11`
- `src/api/endpoints/auth.py:34`
- `src/api/endpoints/auth.py:63`
- `src/api/endpoints/web_auth.py:56`
- `src/api/endpoints/web_auth.py:734`
- `src/api/endpoints/web_auth.py:771`
- `src/api/endpoints/web_auth.py:924`
- `src/api/endpoints/web_auth.py:1137`
- `src/api/endpoints/web_auth.py:1192`
- `src/services/auth.py`
- `src/services/web_account.py`

Why it matters:

- the application exposes both `/auth` and `/api/v1/auth`
- Telegram web auth still issues legacy bot-secret JWTs
- password-based web auth uses a different token model with versioned revocation semantics
- policy drift is likely over time

Recommendation:

- select one public auth API
- migrate all web tokens to one issuer and one refresh model
- remove or isolate legacy routes behind explicit compatibility rules

#### A5. Subscription list performs expensive per-item remote enrichment

Evidence:

- `src/api/endpoints/user.py:587`
- `src/api/endpoints/user.py:658`
- `src/api/endpoints/user.py:669`
- `src/api/endpoints/user.py:853`

Why it matters:

- each subscription can trigger separate Remnawave requests
- latency grows with the number of subscriptions
- external API pressure rises and timeout risk increases

Recommendation:

- batch or cache Remnawave enrichment
- separate cheap snapshot data from expensive live runtime data
- measure endpoint latency before and after the change

#### A6. Backend quality gates are not trustworthy in the current state

Evidence:

- `pytest`: 23 failed
- `mypy`: 233 errors
- `ruff`: 325 issues

Representative examples:

- `src/services/access.py:70` to `src/services/access.py:73`
- `src/services/email_recovery.py`
- `src/services/command.py`
- `src/api/endpoints/web_auth.py`
- `src/api/endpoints/user.py`

Why it matters:

- strict tooling exists on paper, but it is not protecting the project
- regressions can pass unnoticed because the signal is buried in baseline noise
- DI-driven endpoint tests are fragile and not isolated enough

Recommendation:

- fix the red tests first
- reduce `mypy` error count in the auth and user critical path
- split endpoint orchestration from testable business logic

#### A7. Frontend production build ships public source maps

Evidence:

- `web-app/vite.config.ts:29`
- Nginx serves `/webapp/` and `/assets/` as static files

Why it matters:

- deployment artifacts are larger than necessary
- source structure is exposed publicly
- the generated `.map` files are larger than several runtime chunks

Recommendation:

- make source maps opt-in through environment flags
- default production builds to `sourcemap: false`
- keep private debug builds only for controlled environments

### Medium

#### A8. Frontend uses fixed polling for subscriptions and notifications

Evidence:

- `web-app/src/hooks/useSubscriptionsQuery.ts:28`
- `web-app/src/components/layout/NotificationCenterDialog.tsx:52`
- `web-app/src/components/layout/NotificationCenterDialog.tsx:59`

Why it matters:

- the client keeps generating traffic every 30 seconds
- background tabs still create avoidable work
- the backend pays the cost even when data freshness is not critical

Recommendation:

- refetch only when the screen is active
- pause work in hidden tabs
- prefer focus-based refresh where acceptable
- add retry backoff after failures

#### A9. Access and refresh tokens are stored in `localStorage`

Evidence:

- `web-app/src/lib/api.ts:68`
- `web-app/src/lib/api.ts:82`

Why it matters:

- any successful XSS can immediately exfiltrate both tokens
- the risk is amplified by the mixed auth surface

Recommendation:

- prefer HttpOnly cookies with SameSite and CSRF protection
- if browser storage must remain, harden CSP and reduce token lifetime

#### A10. Frontend test coverage is effectively absent

Evidence:

- no `*.test.*` or `*.spec.*` files were found under `web-app/`

Why it matters:

- auth, purchase, settings, and dashboard flows are protected mainly by manual testing
- frontend regressions can ship even when lint and type checks are green

Recommendation:

- add at least a smoke suite for auth, purchase, and settings flows
- cover refresh-token behavior and route guards first

#### A11. Several UI and accessibility details drift from current guidance

Evidence:

- `web-app/src/components/ui/button.tsx:8`
- `web-app/src/components/layout/Header.tsx:139`
- `web-app/src/pages/auth/LoginPage.tsx:94`
- `web-app/src/pages/auth/RegisterPage.tsx:193`
- `web-app/src/pages/dashboard/PurchasePage.tsx:312`
- `web-app/src/pages/dashboard/PurchasePage.tsx:765`

Examples:

- base button styling uses `transition-all`
- the profile icon trigger in the header does not expose a clear `aria-label`
- auth inputs are missing autocomplete hints
- a payment-gateway image is rendered without explicit size or loading hints

Why it matters:

- unnecessary animation scope increases repaint and layout work
- keyboard and assistive-technology usability drops
- browser autofill support is worse than it should be

Recommendation:

- replace `transition-all` with property-specific transitions
- add labels for icon-only controls
- add `autocomplete` values to auth forms
- size static images explicitly

### Low

#### A12. Repository hygiene is noisy

Evidence:

- 53 `__pycache__` directories under `src/` and `tests/`
- stale `web-app/react-doctor.latest.txt`
- mojibake in files such as `src/services/remnawave.py`, `docker-compose.yml`, `nginx/nginx.conf`, and `src/lifespan.py`

Why it matters:

- code review becomes harder
- stale artifacts create false confidence
- broken comments reduce maintainability

Recommendation:

- remove generated artifacts from the working tree
- fix encoding issues
- regenerate reports only when they are part of a documented workflow

## Areas Not Fully Proven In This Audit

These are plausible concerns, but they were not promoted to confirmed findings without stronger evidence:

- payment persistence commit timing inside request-scoped unit of work
- live production latency distribution under real traffic
- browser-only race conditions outside the inspected auth refresh path

The current report intentionally favors confirmed issues over speculative ones.

## Recommended Order

1. Fix webhook status handling.
2. Remove fail-open access behavior.
3. Make rate limiting proxy-aware.
4. Disable production source maps.
5. Consolidate auth flows and token semantics.
6. Cut Remnawave fan-out on subscription listing.
7. Recover test and typing gates.
8. Reduce frontend polling and add targeted frontend tests.

## External References

- FastAPI, "Behind a Proxy":
  - https://fastapi.tiangolo.com/advanced/behind-a-proxy/
- TanStack Query, "Important Defaults":
  - https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults
- Vite, "Build Guide":
  - https://vite.dev/guide/build
- Telegram Mini Apps, "Init Data":
  - https://docs.telegram-mini-apps.com/platform/init-data
- OWASP, "HTML5 Security Cheat Sheet":
  - https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html
- Vercel Web Interface Guidelines:
  - https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
