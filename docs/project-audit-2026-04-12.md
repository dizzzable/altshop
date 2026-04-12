# AltShop Project Audit

Date: 2026-04-12

## Summary

The repository is currently in a strong change-ready state:

- backend tests: `244 passed`
- backend lint: `ruff check src tests` passes
- backend typing: `mypy src` passes
- frontend lint/type-check/build all pass

This is no longer a “stabilize the basics first” project. The next gains come from
response-time work, call-path consolidation, and reducing repeated work across
bot, web, mini-app, and background flows.

## Measured Hotspots

### Largest backend service files

1. `src/services/remnawave.py` — ~56 KB
2. `src/services/subscription_purchase.py` — ~55 KB
3. `src/services/payment_gateway.py` — ~43 KB
4. `src/services/partner.py` — ~43 KB
5. `src/services/referral.py` — ~38 KB
6. `src/services/backup.py` — ~35 KB

These are the highest-leverage refactor targets because they combine orchestration,
external I/O, and cross-service branching.

### Heaviest endpoint surfaces

1. `src/api/endpoints/web_auth.py` — ~53 KB
2. `src/api/endpoints/user_subscription.py` — ~19 KB
3. `src/api/endpoints/user_portal.py` — ~9 KB

`web_auth.py` remains the largest single HTTP entrypoint and still owns multiple
auth, link, analytics, and UX branches.

## External Call Fan-out Findings

Confirmed current patterns:

- `subscription_runtime.py` already batches by Telegram ID where possible, but still falls back
  to per-user `get_user(...)` calls in some paths.
- `web_cabinet_admin.py` still does per-subscription `remnawave_service.get_user(...)`
  for preview rendering.
- `taskiq/tasks/notifications.py` builds expiry summaries with per-subscription
  `remnawave_service.get_user(...)`.
- dashboard/admin user getters still have direct per-subscription Remnawave fetches.
- `remnawave.py` contains repeated raw `AsyncClient(...)` construction for low-level fallback paths.
- `market_quote.py` also creates standalone `AsyncClient(...)` instances for provider fetches.

## Frontend Polling Map

Current active polling or refetch-sensitive areas:

- `useSubscriptionsQuery.ts`
  - optional visible-only polling
  - `refetchOnWindowFocus: true`
  - `staleTime: 10_000`
  - custom exponential `retryDelay`
- `NotificationCenterDialog.tsx`
  - unread count polling every 60s while visible
  - list polling every 60s while open + visible
  - duplicated retry/backoff configuration
- `useAccessStatusQuery.ts`
  - `staleTime: 15_000`
  - `refetchOnWindowFocus: true`
- `main.tsx`
  - QueryClient default `retry: 1`
  - QueryClient default `refetchOnWindowFocus: false`

Observation:
the frontend has already moved away from naive background polling, but the
query policy is still split between global defaults, hooks, and component-local
`useQuery(...)` declarations.

## Query / Cache Defaults

Current effective defaults are inconsistent:

- global QueryClient disables focus refetch
- some hooks re-enable focus refetch locally
- polling hooks each define their own retry delay
- pages like `SettingsPage`, `ReferralsPage`, `PromocodesPage`, and `DashboardPage`
  still mix direct `useQuery(...)` with shared hooks

This is a maintainability and performance smell rather than an outright bug.

## Reliability / Retry Surfaces

Current important retry-or-failure edges:

- inbound payment webhooks
- Remnawave webhooks
- Taskiq middleware error path
- Remnawave fallback raw HTTP requests
- market quote provider fetches
- frontend auth refresh path via Axios retry-once session refresh

Positive note:
event/error observability is better than before, and operator events now carry
more context. The remaining gap is not “no diagnostics”, but lack of a broad
performance/reliability simplification pass across the hottest service paths.

## Ranked Bottlenecks

### High Priority

1. `RemnawaveService` raw + SDK fetch orchestration is too large and owns both
   connection policy and business syncing.
2. `SubscriptionPurchaseService` still combines request normalization, pricing,
   gateway selection, and execution in one heavy orchestration file.
3. Frontend query policy is duplicated across hooks/components, causing drift in
   focus refetch, polling, and backoff semantics.

### Medium Priority

4. Admin/user getters still do per-item Remnawave lookups in some read paths.
5. Notification-related background summary builders do synchronous fan-out style
   lookups where grouped fetches or short-lived caches would be cheaper.
6. `web_auth.py` remains the heaviest remaining HTTP edge and should continue to
   lose orchestration to helpers/services.

### Lower Priority

7. `market_quote.py` raw client creation should eventually share the same request
   policy discipline as other external integrations.
8. Some docs in `docs/` are historical and no longer reflect current green baseline.

## Fix-First Shortlist

### Slice 1

- create one shared frontend query-defaults helper and move subscription,
  notification, and access-status policies onto it
- centralize Remnawave raw HTTP client policy in `remnawave.py`
- keep quality gates green

### Slice 2

- split `remnawave.py` into connection/raw-client, fetch/sync, and event-handling lanes
- reduce remaining per-subscription Remnawave fetches in admin and notification flows

### Slice 3

- split `subscription_purchase.py` by responsibility:
  - request normalization
  - quote/pricing
  - gateway selection
  - execution/post-payment

## References

Official implementation guidance relevant to the next slice:

- HTTPX async client reuse and pooling:
  `https://www.python-httpx.org/async/`
- TanStack Query important defaults:
  `https://tanstack.com/query/v4/docs/react/guides/important-defaults`
- FastAPI behind a proxy / forwarded headers:
  `https://fastapi.tiangolo.com/advanced/behind-a-proxy/`
