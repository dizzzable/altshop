> [!WARNING]
> Исторический документ. Этот файл не входит в канонический комплект документации и не переаудировался в текущем проходе. Актуальная точка входа: [docs/README.md](README.md)

# Refactor Follow-Up 2026-03-07

## Verified Baseline

Local backend checks were re-run on March 7, 2026 after repairing the moved virtual environment:

- `.venv/pyvenv.cfg` now points to `C:\Users\USER\AppData\Local\Programs\Python\Python312`
- `uv` is not available in `PATH` on this workstation
- `pytest.exe` and `mypy.exe` can fail in this PowerShell with `Failed to canonicalize script path`,
  so the stable local commands are:
  - `.\.venv\Scripts\ruff.exe ...`
  - `.\.venv\Scripts\python.exe -m pytest ...`
  - `.\.venv\Scripts\python.exe -m mypy ...`

Verified commands:

```powershell
.\.venv\Scripts\ruff.exe check src tests
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe scripts\backend_audit_report.py
```

Expected result after this pass:

- `ruff`: pass
- `pytest`: `229 passed`
- `mypy`: pass
- backend audit report: pass

Frontend checks were also re-run in `web-app`:

```powershell
npm run lint
npm run type-check
npm run build
npm run check:encoding
```

Expected frontend result after this pass:

- `lint`: pass
- `type-check`: pass
- `build`: pass
- `check:encoding`: pass

## What Changed In This Pass

### 1. Repaired the local Python environment

The checked-in `.venv` was still bound to the old Windows profile path (`C:\Users\dizzable\...`).
That prevented any local quality gate from running through the environment that already contains the
project dependencies.

The minimal repair was to update `.venv/pyvenv.cfg` so the venv resolves the active Python 3.12
installation again.

### 2. Removed an orphaned legacy auth service

Deleted:

- `src/services/auth.py`

Why it was removed:

- it was no longer referenced by runtime wiring, DI providers, endpoints, or tests
- it still contained the old `users.auth_username/password_hash` logic
- it was the only remaining source-file causing both `ruff` (`C901`) and `mypy` failures
- keeping it in-tree preserved a false impression that legacy user-table auth was still active

Current auth source of truth remains:

- `src/services/web_account.py`
- `src/infrastructure/database/models/sql/web_account.py`
- `/api/v1/auth/*` endpoints

### 3. Removed the legacy `/auth/*` backend router

Changed:

- `src/api/app.py`
- `src/api/endpoints/__init__.py`
- `scripts/backend_audit_report.py`
- `tests/test_app_factory.py`

What changed:

- deleted the deprecated backend `/auth/*` compatibility router entirely
- removed the app-level conditional mounting and the legacy config flag
- the backend audit report now reflects `Auth compatibility surface -> none detected`
- removed the now-obsolete legacy-router test file

Why this matters:

- the compatibility surface no longer exists in runtime code
- the backend auth contract is now unambiguously `/api/v1/auth/*`
- the green backend baseline is smaller and less misleading: `139` tests and `335` source files

### 4. Cleaned frontend auth leftovers from the old token-storage flow

Changed:

- `web-app/src/lib/api.ts`
- `web-app/src/components/auth/AuthProvider.tsx`
- `web-app/src/pages/auth/LoginPage.tsx`
- `web-app/src/pages/auth/RegisterPage.tsx`
- `web-app/src/pages/dashboard/SettingsPage.tsx`
- `web-app/src/components/layout/DashboardLayout.tsx`

What changed:

- removed the dead `getAccessToken()`, `getRefreshToken()`, and `setTokens()` helpers
- renamed storage cleanup to `clearLegacyAuthStorage()`
- successful auth flows now explicitly clear stale legacy `localStorage` tokens instead of pretending
  to persist active session credentials

Why this matters:

- the frontend now reads closer to the real cookie-first auth model
- dead abstractions no longer imply that bearer tokens in `localStorage` are still a live transport

### 5. Switched public auth responses to cookie-first session payloads

Changed:

- `src/api/endpoints/web_auth.py`
- `tests/test_invited_access.py`
- `tests/test_web_auth_session_tokens.py`
- `web-app/src/types/index.ts`
- `web-app/src/lib/api.ts`

What changed:

- login/register/bootstrap/telegram/refresh responses no longer return `access_token` or
  `refresh_token` in JSON
- refresh is now cookie-only and no longer accepts `refresh_token` in the request body
- tests now verify `Set-Cookie` headers instead of response-body tokens
- frontend auth types now describe session establishment instead of bearer-token delivery

Why this matters:

- the public auth contract now matches the real transport: secure cookies
- response JSON no longer pretends that the browser should persist tokens manually
- the test suite now checks the actual session side effect instead of a compatibility artifact

### 6. Moved `/subscription/list` batch orchestration out of the FastAPI endpoint

Changed:

- `src/services/subscription_runtime.py`
- `src/api/endpoints/user.py`
- `tests/test_subscription_runtime.py`

What changed:

- added `SubscriptionRuntimeService.prepare_for_list_batch(...)`
- the service now owns list preparation, refresh-id collection, lock acquisition, and background
  refresh enqueueing for subscription lists
- `/api/v1/subscription/list` now delegates to the runtime service instead of coordinating
  cache checks and task scheduling inline inside `user.py`
- tests were split accordingly: batch refresh behavior is asserted at the service layer, while the
  endpoint test now checks thin delegation only

Why this matters:

- the hottest subscription-list flow is now testable without the router and taskiq wiring
- `src/api/endpoints/user.py` lost one more orchestration block and is easier to continue
  decomposing
- the remaining optimization target is narrower: the expensive part is now the background runtime
  refresh itself, not the endpoint composition layer

### 7. Reduced Remnawave user fan-out in background subscription runtime refresh

Changed:

- `src/infrastructure/database/repositories/subscription.py`
- `src/services/subscription.py`
- `src/services/remnawave.py`
- `src/services/subscription_runtime.py`
- `tests/test_subscription_runtime.py`

What changed:

- added batch subscription lookup by ids in the repository and service layer
- added `RemnawaveService.get_users_by_telegram_id(...)` as an explicit service wrapper
- `SubscriptionRuntimeService.refresh_user_subscriptions_runtime(...)` now:
  - loads subscriptions in one DB call
  - groups them by `user_telegram_id`
  - prefetches all Remnawave users for that telegram id once
  - falls back to direct `get_user(...)` only when the prefetched set misses a uuid
- device lookups remain per subscription, but user lookups are no longer per-subscription

Why this matters:

- the runtime refresh path no longer performs `N` Remnawave user fetches for `N` subscriptions
- the background task keeps existing behavior but makes fewer remote calls on the hot path
- the next optimization target is now narrower again: device-count fan-out and any panel-side
  bulk device endpoint strategy

### 8. Reused runtime snapshot flow in `/devices/generate`

Changed:

- `src/api/endpoints/user.py`
- `tests/test_user_devices_endpoint.py`

What changed:

- `/api/v1/devices/generate` now uses `SubscriptionRuntimeService.prepare_for_detail(...)`
  before enforcing device limits and building the connection URL
- direct `Remnawave.get_subscription_url(...)` is now fallback-only when the prepared subscription
  still has an empty URL
- the endpoint no longer performs a separate HWID count call plus a separate URL lookup in the
  common case
- added tests for runtime-snapshot reuse, URL fallback, and limit enforcement

Why this matters:

- device-link generation now reuses the same cache-aware runtime preparation path as the detail flow
- in the common case this removes one extra Remnawave user lookup from `/devices/generate`
- the device-related logic in `user.py` is incrementally moving toward one source of truth instead
  of endpoint-local panel orchestration

### 9. Added event-driven device-count updates for runtime snapshots

Changed:

- `src/services/subscription_runtime.py`
- `src/api/endpoints/remnawave.py`
- `src/api/endpoints/user.py`
- `tests/test_subscription_runtime.py`
- `tests/test_remnawave_webhook.py`
- `tests/test_user_devices_endpoint.py`

What changed:

- added `SubscriptionRuntimeService.apply_device_event_to_cached_runtime(...)`
- Remnawave webhook processing now applies `user_hwid_devices.added/deleted` events to an existing
  cached runtime snapshot after successful device-event handling
- `devices_count` mutations are clamp-safe and refresh the snapshot TTL
- `/api/v1/devices` now uses cached runtime snapshot count as its fallback instead of relying only on
  `subscription.devices_count`, which is not persisted in the SQL model

Why this matters:

- recent HWID add/delete events now propagate into runtime cache without waiting for the next panel
  refresh cycle
- device-related endpoints can reuse fresher `devices_count` data even when Remnawave is temporarily
  unavailable
- the remaining fan-out is now concentrated in the actual device-list fetch itself, not in fallback
  count handling

### 10. Moved device endpoint orchestration into `SubscriptionDeviceService`

Changed:

- `src/services/subscription_device.py`
- `src/infrastructure/di/providers/services.py`
- `src/api/endpoints/user.py`
- `tests/test_subscription_device_service.py`
- `tests/test_user_devices_endpoint.py`

What changed:

- added a dedicated `SubscriptionDeviceService` for:
  - listing subscription devices
  - generating device connection links
  - revoking devices
- `/api/v1/devices`, `/api/v1/devices/generate`, and `/api/v1/devices/{hwid}` now delegate to that
  service instead of orchestrating subscription lookup, runtime/cache reads, panel calls, and error
  mapping inline in `user.py`
- device behavior tests moved to the service layer, while endpoint tests now verify thin delegation
  and HTTP status mapping only

Why this matters:

- `src/api/endpoints/user.py` lost another feature-sized block of orchestration
- device behavior is now testable without FastAPI plumbing
- the next device optimization step can happen in one place instead of being duplicated across three
  routes

### 11. Removed eager task-package imports to avoid hidden import cycles

Changed:

- `src/infrastructure/taskiq/tasks/__init__.py`

What changed:

- the Taskiq task package no longer eagerly imports every task module from `__init__`
- importing one task module now stays lazy and does not implicitly initialize unrelated task graphs

Why this matters:

- it removes reliance on a lucky import order between `RemnawaveService`, payment tasks, and
  subscription tasks
- the new device service tests exposed that the old eager package import was structurally fragile
- backend module loading is now less coupled and easier to extend safely

### 12. Unified current-user profile assembly behind `UserProfileService`

Changed:

- `src/services/user_profile.py`
- `src/infrastructure/di/providers/services.py`
- `src/api/endpoints/user.py`
- `src/api/endpoints/web_auth.py`
- `tests/test_user_identity.py`

What changed:

- added `UserProfileService.build_snapshot(...)` as the single application-layer source of truth for:
  - linked Telegram state
  - email and verification flags
  - link-prompt visibility
  - effective subscription cap
  - active subscription count
  - partner flags
  - public username and safe display name
- `/api/v1/user/me`, `PATCH /api/v1/user/security/email`, and `/api/v1/auth/me` now delegate to
  that service instead of rebuilding the same profile state inline
- the service loads web account, subscriptions, settings, and partner state concurrently when it
  owns the fetch path
- `set_security_email` now returns the same prompt/link semantics as the normal profile endpoints
  instead of keeping a slightly different local reconstruction branch

Why this matters:

- `user.py` and `web_auth.py` no longer maintain three drifting copies of the same profile logic
- profile-related changes now have one testable update point instead of multiple router-local copies
- the next `user.py` extraction can focus on a larger remaining cluster instead of current-user
  identity plumbing

### 13. Added short-lived device-list cache and synced runtime counts from observed panel state

Changed:

- `src/core/storage/keys.py`
- `src/services/subscription_runtime.py`
- `src/services/subscription_device.py`
- `src/api/endpoints/remnawave.py`
- `tests/test_subscription_device_service.py`
- `tests/test_subscription_runtime.py`
- `tests/test_remnawave_webhook.py`

What changed:

- added a dedicated Redis key for cached `/devices` payloads keyed by `user_remna_id`
- `SubscriptionDeviceService.list_devices(...)` now:
  - serves a fresh cached HWID list without calling Remnawave
  - stores fresh panel results into a short-lived cache
  - falls back to stale cached devices when the panel call fails
  - synchronizes observed `devices_count` back into the cached runtime snapshot when a live panel
    fetch succeeds
- `SubscriptionDeviceService.revoke_device(...)` now removes the deleted `hwid` from cached device
  lists immediately after a successful panel delete and synchronizes the cached runtime count when a
  list snapshot is available
- Remnawave webhook device events now update the cached full device list as well as the runtime
  count snapshot, so recent add/delete events stay reflected in `/devices` without waiting for the
  next full panel fetch

Why this matters:

- `/api/v1/devices` no longer needs a Remnawave round-trip on every refresh when the user is
  repeatedly opening the same screen
- the fallback path is more realistic than `devices=[]` because stale cached device entries survive
  temporary panel failures
- device-list state and runtime `devices_count` are now less likely to drift apart across
  `/devices`, `/devices/generate`, and webhook-driven updates

### 14. Moved referral portal orchestration out of `user.py`

Changed:

- `src/services/referral_portal.py`
- `src/api/utils/web_app_urls.py`
- `src/infrastructure/di/providers/services.py`
- `src/api/endpoints/user.py`
- `tests/test_referral_link_fallback.py`
- `tests/test_referral_portal_service.py`

What changed:

- added `ReferralPortalService` as the application-layer owner for:
  - referral access gating for active partners
  - retry/fallback resolution of Telegram vs web referral links
  - referral info aggregation
  - QR target resolution
  - referral list mapping
  - exchange options / execute entry-point orchestration
- `/referral/info`, `/referral/qr`, `/referral/list`, `/referral/exchange/options`,
  `/referral/exchange/execute`, and `/referral/about` now delegate to that service instead of
  keeping the flow inline in `user.py`
- `partner/info` now reuses the same service to prepare referral code + fallback referral links
  instead of owning a second copy of that logic
- extracted shared web-app URL builders into `src/api/utils/web_app_urls.py`, so referral links and
  payment redirect URLs no longer keep separate router-local URL assembly helpers

Why this matters:

- `user.py` lost another cohesive feature cluster and now keeps less cross-endpoint orchestration
- referral link fallback behavior has one source of truth instead of being duplicated between
  referral and partner surfaces
- later partner/referral cleanup can build on one service boundary instead of re-editing multiple
  route handlers and helpers

### 15. Moved partner dashboard and withdrawal orchestration out of `user.py`

Changed:

- `src/services/partner_portal.py`
- `src/infrastructure/di/providers/services.py`
- `src/api/endpoints/user.py`
- `tests/test_partner_portal_service.py`
- `tests/test_referral_link_fallback.py`
- `tests/test_user_identity.py`

What changed:

- wired `PartnerPortalService` into DI and made it the application-layer owner for:
  - partner info assembly
  - partner referrals list pagination and mapping
  - partner earnings history mapping
  - withdrawal request validation, creation, and notification payload assembly
  - withdrawal list serialization
- `/partner/info`, `/partner/referrals`, `/partner/earnings`, `/partner/withdraw`, and
  `/partner/withdrawals` now delegate to that service instead of keeping policy and orchestration
  inline inside `user.py`
- removed router-local withdrawal helpers and duplicated partner mapping branches from `user.py`
- tightened `src/services/partner_portal.py` itself with explicit DTO typing and dedicated tests, so
  the new boundary passes `ruff` and `mypy` as part of the normal backend gate instead of acting as
  a latent orphan file

Why this matters:

- the remaining partner surface now has one service boundary instead of five route-local branches
- notification fallback and withdrawal semantics are testable without depending on FastAPI wiring
- the next `user.py` reduction can target the remaining purchase/payment cluster instead of partner
  flows that are already extracted

### 16. Moved purchase and renew orchestration out of `user.py`

Changed:

- `src/services/subscription_purchase.py`
- `src/infrastructure/di/providers/services.py`
- `src/api/endpoints/user.py`
- `tests/test_purchase_quantity.py`

What changed:

- added `SubscriptionPurchaseService` as the application-layer owner for:
  - plan and duration validation
  - gateway resolution for web vs Telegram purchase flows
  - subscription-limit and renew-ownership checks
  - device-type expansion for multi-subscription purchases
  - partner-balance debit flow and transaction failure rollback path
  - external payment creation with default web redirect URLs
- `/subscription/purchase` and `/subscription/{subscription_id}/renew` now delegate to that service
  instead of keeping the whole purchase flow inline in `user.py`
- the dedicated renew alias now resolves default `renew_subscription_id` inside the service boundary,
  so the route layer no longer mutates the incoming request model
- purchase tests now target the service contract instead of private route helpers, including renew
  alias behavior and partner-balance failure marking

Why this matters:

- `user.py` dropped another large orchestration cluster and now keeps less payment-specific policy
- purchase behavior is easier to evolve without coupling tests to FastAPI route internals
- future work on trial access, promocode activation, or payment optimization can reuse the same
  purchase boundary instead of editing another set of router-local helpers

### 17. Moved purchase access, trial eligibility, and promocode activation out of `user.py`

Changed:

- `src/services/purchase_access.py`
- `src/services/subscription_trial.py`
- `src/services/promocode_portal.py`
- `src/services/subscription_purchase.py`
- `src/infrastructure/di/providers/services.py`
- `src/api/endpoints/user.py`
- `tests/test_purchase_quantity.py`
- `tests/test_promocode_activate_plan_filter.py`
- `tests/test_subscription_trial_service.py`

What changed:

- added `PurchaseAccessService` as the shared application-layer owner for purchase gating, so web
  purchase disablement and restricted access mode are translated once instead of being reimplemented
  per endpoint
- added `SubscriptionTrialService` to own trial eligibility and trial creation:
  - linked Telegram identity checks
  - first-subscription and already-used checks
  - configured trial plan resolution
  - trial plan validity and duration guards
- added `PromocodePortalService` to own promocode activation orchestration:
  - code normalization
  - eligible subscription resolution
  - subscription-reward vs resource-reward branching
  - activation payload building for the underlying promocode service
- `SubscriptionPurchaseService` now depends on `PurchaseAccessService`, so purchase, renew, trial,
  and promocode flows reuse the same access-policy boundary
- `/subscription/purchase`, `/subscription/{subscription_id}/renew`, `/trial/check`, `/trial`, and
  `/promocode/activate` are now thin wrappers that only translate HTTP I/O and service errors
- tests were moved to the service boundary, so trial and promocode rules are no longer coupled to
  private helpers inside `user.py`

Why this matters:

- `user.py` lost another router-local policy cluster and is now easier to split further
- purchase-related access rules now have one source of truth instead of being partially duplicated
  across purchase, trial, and promocode endpoints
- the next extraction pass can focus on the remaining history or subscription-management clusters,
  not on recreating the same gating logic yet again

### 18. Moved user activity history assembly out of `user.py`

Changed:

- `src/services/user_activity_portal.py`
- `src/infrastructure/di/providers/services.py`
- `src/api/endpoints/user.py`
- `tests/test_user_activity_portal_service.py`

What changed:

- added `UserActivityPortalService` as the application-layer owner for:
  - transaction history page assembly
  - notification list page assembly
  - unread notification count and read mutations
  - promocode activation history page assembly
- `/user/transactions`, `/user/notifications`, `/user/notifications/unread-count`,
  `/user/notifications/{id}/read`, `/user/notifications/read-all`, and
  `/promocode/activations` now delegate to that service instead of building response payloads
  directly inside `user.py`
- route-local helpers for transaction item serialization and notification title generation were
  removed from the router module
- service-level tests now cover history serialization and notification mutation mapping without
  depending on FastAPI wiring

Why this matters:

- `user.py` dropped another presenter-heavy cluster and now focuses more on HTTP translation than on
  assembling application snapshots
- transaction, notification, and promocode-history behavior can now evolve under one service
  boundary instead of being spread across unrelated route handlers
- the next extraction pass can target the remaining subscription-management logic instead of more
  history formatting code

### 19. Moved subscription detail, assignment, and delete flows out of `user.py`

Changed:

- `src/services/subscription_portal.py`
- `src/infrastructure/di/providers/services.py`
- `src/api/endpoints/user.py`
- `tests/test_subscription_portal_service.py`
- `tests/test_user_subscription_endpoint.py`
- `tests/test_subscription_runtime.py`

What changed:

- added `SubscriptionPortalService` as the application-layer owner for:
  - owned subscription detail lookup
  - assignment update policy and snapshot mutation
  - delete flow validation and persistence result handling
- `/subscription/{id}`, `/subscription/{id}/assignment`, and `/subscription/{id}` `DELETE` now
  delegate to that service instead of carrying ownership checks and assignment mutation rules
  directly in `user.py`
- the old route-local `_apply_plan_assignment_update(...)` helper is gone; explicit field presence is
  now translated once into `SubscriptionAssignmentUpdate`
- delete flow now fails loudly on a failed `delete_subscription(...)` persistence call instead of
  returning a false-positive success response
- tests were split between service-level policy coverage and thin endpoint HTTP mapping

Why this matters:

- `user.py` dropped another subscription-management cluster and is down to a smaller, more
  maintainable router surface
- ownership and assignment policy now have one service boundary instead of being embedded in three
  endpoint branches
- silent false-positive delete responses are gone, which removes one more legacy-quality footgun

### 20. Moved `/plans` catalog assembly out of `user.py`

Changed:

- `src/services/plan_catalog.py`
- `src/services/purchase_gateway_policy.py`
- `src/api/utils/web_app_urls.py`
- `src/services/subscription_purchase.py`
- `src/infrastructure/di/providers/services.py`
- `src/api/endpoints/user.py`
- `tests/test_plan_catalog_service.py`
- `tests/test_user_plan_endpoint.py`

What changed:

- added `PlanCatalogService` as the application-layer owner for `/plans` read-model assembly:
  - available plan lookup
  - active gateway lookup
  - channel-aware gateway filtering
  - per-duration price projection
- extracted shared purchase-channel gateway policy into `src/services/purchase_gateway_policy.py`, so
  `/plans` and `SubscriptionPurchaseService` now use the same gateway-availability rules
- moved default web payment redirect URL construction into `src/api/utils/web_app_urls.py` and
  removed the dead router-local helper from `user.py`
- `/plans` now delegates to the plan catalog service and only maps snapshots to HTTP response models
- added service-level coverage for WEB vs TELEGRAM gateway filtering and endpoint-level coverage for
  thin delegation

Why this matters:

- `user.py` dropped another read-model cluster and is down to a smaller router surface
- gateway availability rules no longer risk drifting between catalog display and real purchase flow
- one more dead helper path is gone from the router module, which reduces false signals during later
  cleanup

### 21. Split runtime freshness semantics for subscription cache snapshots

Changed:

- `src/services/subscription_runtime.py`
- `tests/test_subscription_runtime.py`

What changed:

- `SubscriptionRuntimeSnapshot` now keeps separate freshness timestamps for:
  - core runtime fields (`traffic_used`, `traffic_limit`, `device_limit`, `url`)
  - device-count mutations
- device-only cache mutations from observed counts and HWID webhook events now update
  `devices_refreshed_at` without bumping `core_refreshed_at`
- list and detail preparation now use core freshness instead of the old shared `refreshed_at`
  signal, so a recent device event no longer prevents runtime refresh of stale traffic or URL data
- device-only cache rewrites preserve the remaining Redis TTL when possible instead of always
  extending the snapshot lifetime
- compatibility with already-stored snapshots is preserved by normalizing missing refresh timestamps
  from legacy `refreshed_at`

Why this matters:

- device count is still updated quickly from webhook and `/devices` paths, but it no longer masks
  stale runtime URL or traffic state
- `/subscription/list` and detail flows regain a more accurate refresh signal without losing the
  fast device-count fallback path
- the remaining runtime work is now smaller and more explicit than the old shared freshness model

### 22. Extract referral and partner presenters from the user router

Changed:

- `src/api/presenters/user_portal.py`
- `src/api/endpoints/user.py`
- `tests/test_user_portal_presenter.py`

What changed:

- moved referral and partner response contracts plus snapshot-to-response mapping out of
  `src/api/endpoints/user.py` into `src/api/presenters/user_portal.py`
- moved referral and partner HTTP error adapters into the same presenter layer so the router only
  keeps request parsing, dependency wiring, and status-code mapping call sites
- kept request models in `user.py` where tests and route signatures still import them, but removed
  the large referral/partner response-model blocks and builder functions from the router module
- added direct presenter tests for nested referral exchange option mapping, partner level-setting
  mapping, and structured referral access-denied error serialization

Why this matters:

- `user.py` loses another large serialization-only cluster and moves closer to a pure HTTP adapter
- referral and partner contracts now live in one place, which makes later OpenAPI/schema extraction
  or endpoint splitting easier
- presenter mapping is now protected both by endpoint tests and by small direct unit tests that fail
  faster than full route integration tests

### 23. Extract the remaining user account presenters from the user router

Changed:

- `src/api/presenters/user_account.py`
- `src/api/endpoints/user.py`
- `tests/test_user_account_presenter.py`

What changed:

- moved user profile, plans, subscriptions, transactions, notifications, purchase, trial, device,
  and promocode response contracts plus snapshot-to-response mapping out of
  `src/api/endpoints/user.py` into `src/api/presenters/user_account.py`
- moved subscription, purchase-access, purchase, and device HTTP error adapters into the same
  presenter layer so the router keeps only request parsing, dependency wiring, and exception
  catch sites
- kept request models and request-to-service mapper helpers in `user.py` so existing tests and route
  signatures stay stable while the serialization layer moves out
- added direct presenter coverage for profile, plan, subscription, transaction, notification,
  device, promocode, and HTTP error adapter mapping

Why this matters:

- `user.py` is now much closer to a thin controller: it mostly contains routes, request DTOs, and
  a small amount of request normalization
- response contracts for the non-portal user surface now live in one adapter module instead of being
  mixed with business orchestration and HTTP wiring
- the next cleanup step is clearer because the remaining local helpers are request-shaping helpers,
  not serialization code

### 24. Split the user router into context-specific endpoint modules

Changed:

- `src/api/endpoints/user_account.py`
- `src/api/endpoints/user_subscription.py`
- `src/api/endpoints/user_portal.py`
- `src/api/endpoints/user.py`
- `tests/test_app_factory.py`

What changed:

- split the old `src/api/endpoints/user.py` route surface into three bounded endpoint modules:
  account/activity, subscription/purchase/device/promocode, and referral/partner portal
- converted `src/api/endpoints/user.py` into a compatibility facade that only composes child routers
  and re-exports the endpoint callables and request DTOs still imported by tests
- kept route paths, response contracts, and endpoint function objects stable from the caller side,
  so existing endpoint tests still import from `src.api.endpoints.user`
- added an app-factory smoke test to assert that the composed router still mounts representative
  split routes such as `/api/v1/user/me`, `/api/v1/subscription/list`, and `/api/v1/referral/info`

Why this matters:

- the largest HTTP adapter in the backend is no longer a single 700+ line file
- route wiring now follows the same context split that services and presenters already use, which
  makes later extraction of request DTOs and module-level cleanup much cheaper
- `src/api/endpoints/user.py` is now an intentional compatibility boundary instead of a monolithic
  implementation file

### 25. Move tests off the user compatibility facade

Changed:

- `tests/test_referral_link_fallback.py`
- `tests/test_subscription_runtime.py`
- `tests/test_user_subscription_endpoint.py`
- `tests/test_user_identity.py`
- `tests/test_user_plan_endpoint.py`
- `tests/test_user_devices_endpoint.py`
- `src/api/endpoints/user.py`

What changed:

- moved endpoint-level tests to import directly from `src.api.endpoints.user_account`,
  `src.api.endpoints.user_subscription`, and `src.api.endpoints.user_portal`
- reduced `src/api/endpoints/user.py` to a pure router-composition module that only combines the
  split routers for application mounting
- removed test-side dependence on facade re-exports, so the compatibility layer is no longer part
  of the normal unit-test import surface

Why this matters:

- split endpoint modules are now the primary source of truth for test coverage instead of a
  backward-compatibility shim
- `src/api/endpoints/user.py` became small enough that its remaining value is explicit and easy to
  evaluate: keep it as a composition boundary or delete it later
- future refactors in request DTOs or endpoint-local helpers no longer need to preserve facade
  exports for internal tests

### 26. Remove the user compatibility facade module

Changed:

- `src/api/endpoints/__init__.py`
- deleted `src/api/endpoints/user.py`

What changed:

- moved the final user-router composition up into `src/api/endpoints/__init__.py`
- removed `src/api/endpoints/user.py` entirely after tests and internal imports stopped depending on
  its facade re-exports
- kept the mounted `user_router` public at the package level, so `src/api/app.py` and the rest of
  the application still include one combined user API router without knowing about the split files

Why this matters:

- one more compatibility-only layer is gone from the endpoint tree
- the split endpoint modules are now the only implementation source for the user API surface
- next refactors can target request DTO extraction directly instead of preserving an extra facade

### 27. Extract subscription request contracts out of the split endpoint module

Changed:

- `src/api/contracts/__init__.py`
- `src/api/contracts/user_subscription.py`
- `src/api/endpoints/user_subscription.py`
- `tests/test_user_subscription_contract.py`

What changed:

- added a dedicated `src/api/contracts` package for lightweight API request contracts and request
  mappers
- moved subscription assignment, purchase, trial, device-generation, and promocode activation
  request DTOs out of `src/api/endpoints/user_subscription.py`
- moved the subscription request-shaping helpers into `src/api/contracts/user_subscription.py`
- kept the endpoint module API stable by importing the moved request models and mapper helpers back
  into `src/api/endpoints/user_subscription.py`
- added contract-level tests for `model_fields_set` handling and tuple normalization of
  `renew_subscription_ids` and `device_types`

Why this matters:

- `user_subscription.py` is now closer to a pure HTTP adapter and no longer mixes route wiring with
  contract definitions
- request normalization for subscription flows has one explicit home that can be reused or tested
  without importing FastAPI endpoints
- the next extraction step is narrower and more mechanical: apply the same pattern to
  `user_account.py` and `user_portal.py`

### 28. Extract account and portal request contracts out of split endpoint modules

Changed:

- `src/api/contracts/__init__.py`
- `src/api/contracts/user_account.py`
- `src/api/contracts/user_portal.py`
- `src/api/endpoints/user_account.py`
- `src/api/endpoints/user_portal.py`
- `tests/test_user_account_contract.py`
- `tests/test_user_portal_contract.py`

What changed:

- moved `SetSecurityEmailRequest` out of `src/api/endpoints/user_account.py` into
  `src/api/contracts/user_account.py`
- moved `ReferralExchangeExecuteRequest` and `PartnerWithdrawalRequest` out of
  `src/api/endpoints/user_portal.py` into `src/api/contracts/user_portal.py`
- expanded `src/api/contracts/__init__.py` so the shared request-contract package now covers the
  full split user API surface, not only subscription flows
- kept endpoint module imports stable by importing the moved request models back into
  `user_account.py` and `user_portal.py`
- added direct contract tests for email validation and partner/referral request payload validation

Why this matters:

- the split user endpoint modules now keep routing and HTTP mapping almost exclusively, instead of
  mixing those concerns with local Pydantic request model declarations
- request contracts for the whole split user surface now live in one bounded package, which makes
  later refactors or OpenAPI/type-generation work cheaper
- the next backend cleanup target is no longer the user endpoint contracts, but either stale docs
  or the remaining cache-boundary decisions

### 29. Extract web auth request contracts out of the auth endpoint module

Changed:

- `src/api/contracts/__init__.py`
- `src/api/contracts/web_auth.py`
- `src/api/endpoints/web_auth.py`
- `tests/test_web_auth_contract.py`

What changed:

- moved web auth request payload models out of `src/api/endpoints/web_auth.py` into
  `src/api/contracts/web_auth.py`
- included the whole request surface there: login, register, bootstrap, Telegram auth, Telegram
  link request/confirm, email verification confirm, forgot/reset password, and password change
- kept the public endpoint module API stable by importing the moved request models back into
  `src/api/endpoints/web_auth.py`, so existing tests and call sites continue to import from the
  endpoint module if they want to
- added direct contract tests for the custom validators and field constraints that matter most in
  the auth flow

Why this matters:

- `web_auth.py` is now closer to a pure auth adapter and keeps less Pydantic contract noise beside
  cookie/session handling, access guards, and auth orchestration
- the request-contract split is now consistent across the split user API and the main auth surface
- the next cleanup decision is no longer "should we extract auth request models", but whether to
  keep the remaining auth response/presenter layer inside `web_auth.py` or move on to docs/cache
  cleanup first

### 30. Extract auth response presenters out of the auth endpoint module

Changed:

- `src/api/presenters/web_auth.py`
- `src/api/endpoints/web_auth.py`
- `tests/test_branding.py`
- `tests/test_user_identity.py`
- `tests/test_web_auth_presenter.py`

What changed:

- moved auth response contracts and pure presenter helpers out of `src/api/endpoints/web_auth.py`
  into `src/api/presenters/web_auth.py`
- transferred `AuthMeResponse`, `AccessStatusResponse`, `WebBrandingResponse`,
  `RegistrationAccessRequirementsResponse`, `SessionResponse`, the small message/link response
  models, and the pure auth presenters for auth-me, access-status, branding, and locale resolution
- kept cookie mutation and session transport wiring inside `web_auth.py`, so the endpoint module
  still owns auth cookies, CSRF checks, and response side effects while pure response assembly now
  has one explicit home
- moved pure helper tests to the presenter boundary by switching branding and auth-me tests to the
  new module and adding direct presenter coverage for access-status and registration requirements

Why this matters:

- `web_auth.py` is now much closer to a focused controller module instead of another mixed
  controller-plus-presenter file
- pure auth response assembly is now testable without importing the endpoint module at all
- the remaining work in `web_auth.py` is now mostly transport/auth-flow logic rather than DTO and
  presentation glue

### 31. Extract auth session and cookie transport helpers out of the auth endpoint module

Changed:

- `src/api/utils/web_auth_transport.py`
- `src/api/endpoints/web_auth.py`
- `tests/test_web_auth_transport.py`

What changed:

- moved auth cookie names, CSRF guard logic, auth cookie set/clear helpers, session response
  assembly, and token subject/version parsing out of `src/api/endpoints/web_auth.py`
- added a focused transport utility module `src/api/utils/web_auth_transport.py` that now owns the
  cookie/session boundary for auth endpoints
- kept endpoint behavior unchanged by importing the transport helpers back into `web_auth.py`
- added direct tests for session cookie emission, cache-control behavior, CSRF validation, and token
  payload parsing

Why this matters:

- `web_auth.py` now contains less framework-side transport glue and reads closer to pure auth flow
  orchestration plus dependency wiring
- cookie/CSRF behavior has a direct test surface instead of being verified only through endpoint
  side effects
- the remaining auth work is now narrower: mostly dependency extraction or docs cleanup, not
  another broad mixed-responsibility module split

### 32. Extract auth dependency guards out of the auth endpoint module

Changed:

- `src/api/dependencies/web_auth.py`
- `src/api/dependencies/__init__.py`
- `src/api/endpoints/web_auth.py`
- `src/api/endpoints/user_account.py`
- `src/api/endpoints/user_portal.py`
- `src/api/endpoints/user_subscription.py`
- `tests/test_web_auth_session_tokens.py`

What changed:

- moved `get_current_user`, `get_current_web_account`, and `require_web_product_access` out of
  `src/api/endpoints/web_auth.py` into a dedicated dependency module
- updated split user endpoints to import auth guards from `src/api/dependencies/web_auth.py`
  instead of reaching back into the auth endpoint module
- kept runtime behavior stable by importing the new dependency functions back into `web_auth.py`,
  so existing FastAPI dependency wiring and external imports still resolve
- expanded dependency coverage with direct tests for missing web-account rejection and read-only
  product-access gating on `GET` requests

Why this matters:

- `web_auth.py` now reads more like an auth flow controller and less like a mixed endpoint plus
  dependency registry
- shared auth guards now have one explicit home for reuse across split endpoint modules
- the next auth cleanup decision is narrower: either leave flow helpers where they are, or extract
  only the remaining auth-specific orchestration pieces instead of digging through dependency glue

### 33. Clean the active backend docs surface and archive February handoff noise

Changed:

- `docs/README.md`
- `docs/BACKEND_OPERATOR_GUIDE.md`
- `docs/archive/2026-02-handoff/README.md`
- `docs/PRODUCTION_DEPLOYMENT_GUIDE.md`
- `scripts/backend_audit_report.py`
- `docs/archive/2026-02-handoff/*`

What changed:

- replaced the old mojibake-heavy docs index with a clean canonical `docs/README.md`
- added `docs/BACKEND_OPERATOR_GUIDE.md` as the new operator-facing backend entrypoint for runtime,
  deploy, and quality-gate work
- moved the February 20-21, 2026 AI-generated handoff/completion reports out of the main `docs/`
  surface into `docs/archive/2026-02-handoff/`
- updated deployment docs to point at the new operator guide instead of stale completion reports
- changed the backend audit script to ignore `docs/archive`, so archived handoff material no longer
  creates false-positive documentation noise in current audits

Why this matters:

- the active docs root is smaller and closer to the current runtime truth instead of a mix of live
  references and historical session artifacts
- backend operators now have one clear starting point instead of multiple competing “status”
  documents
- archived parity/handoff notes are still available for archaeology without polluting current audit
  output or daily engineering navigation

## Remaining Known Cleanup Area

- frontend source files currently pass `check:encoding`
- active files under `docs/` no longer show the common mojibake markers that were present in the old
  index and handoff surface
- the remaining stale documentation now sits mostly in archived handoff files or root-level legacy
  docs such as `BACKEND_AUTH_IMPLEMENTATION.md` and `QUICK_DEPLOY.md`

## Current Practical Rules

- Treat `web_accounts` as the only writable username/password model.
- Do not reintroduce runtime reads or writes to `users.auth_username` or `users.password_hash`.
- Keep migration files as historical records until rollout confidence for `0040` is complete.
- Use `.\.venv\Scripts\ruff.exe` for `ruff`, and `.\.venv\Scripts\python.exe -m ...` for `pytest`
  and `mypy` on this machine until the shell canonicalization issue is resolved.

## Highest-Value Next Steps

1. Rewrite or archive the remaining root-level legacy docs (`BACKEND_AUTH_IMPLEMENTATION.md`,
   `QUICK_DEPLOY.md`) so the current backend contract lives only in canonical docs.
2. Audit whether the remaining runtime/device caches should share one Redis key or be split further
   by concern now that freshness semantics are separate.
3. Continue profiling `/subscription/list`, `/api/v1/auth/login`, and `/api/v1/user/me` after the
   docs cleanup no longer competes with backend structure work.

## Fast Re-Check

If a later refactor touches auth, run this exact sequence first:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check src tests
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe scripts\backend_audit_report.py
```

