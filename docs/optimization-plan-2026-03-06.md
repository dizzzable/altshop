> [!WARNING]
> Исторический документ. Этот файл не входит в канонический комплект документации и не переаудировался в текущем проходе. Актуальная точка входа: [docs/README.md](README.md)

# AltShop Optimization Plan

Date: 2026-03-06

## Progress Update 2026-03-07

- backend quality gates are restored locally: `ruff`, `pytest`, `mypy`, and backend audit pass
- current backend baseline is `229 passed`, `0 mypy errors`, `0 ruff issues`
- auth compatibility work is complete: legacy `/auth/*` router is gone and web auth is cookie-first
- `/subscription/list` orchestration has been moved out of `src/api/endpoints/user.py` into
  `src/services/subscription_runtime.py`
- `/subscription/list` background refresh now batches local subscription loading and collapses
  Remnawave user lookups to one `get_users_by_telegram_id(...)` call per local user
- `/devices/generate` now reuses runtime snapshot preparation instead of doing separate count and URL
  panel fetches in the common path
- Remnawave HWID webhook events now mutate cached runtime `devices_count`, and `/devices` uses that
  runtime snapshot as fallback when panel device fetch fails
- device endpoint orchestration now lives in `src/services/subscription_device.py` instead of
  `src/api/endpoints/user.py`
- `/devices` now uses a short-lived cached HWID list and reuses webhook-driven cache mutation for
  add/delete events instead of hitting Remnawave on every screen refresh
- observed device counts from live `/devices` panel fetches and successful revoke operations are now
  synchronized back into the runtime snapshot cache
- referral portal orchestration now lives in `src/services/referral_portal.py` instead of being
  duplicated across referral endpoints and `partner/info`
- partner dashboard and withdrawal orchestration now lives in `src/services/partner_portal.py`
  instead of `src/api/endpoints/user.py`
- subscription purchase and renew orchestration now lives in `src/services/subscription_purchase.py`
  instead of router-local helper functions in `src/api/endpoints/user.py`
- shared purchase access policy now lives in `src/services/purchase_access.py` instead of
  `_assert_purchase_scope_access` inside `src/api/endpoints/user.py`
- trial eligibility and trial creation now live in `src/services/subscription_trial.py` instead of
  router-local helper chains in `src/api/endpoints/user.py`
- promocode activation gating and subscription-target resolution now live in
  `src/services/promocode_portal.py` instead of route-local helper functions
- transaction history, user notification page assembly, unread/read mutations, and promocode
  activation history now live behind `src/services/user_activity_portal.py` instead of being
  assembled directly in `src/api/endpoints/user.py`
- owned subscription detail, assignment mutation, and delete flows now live in
  `src/services/subscription_portal.py` instead of route-local ownership and mutation helpers
- `/plans` catalog assembly now lives in `src/services/plan_catalog.py`, and channel-aware gateway
  availability is shared with purchase flow through `src/services/purchase_gateway_policy.py`
- runtime snapshot freshness is now split in `src/services/subscription_runtime.py`, so device-count
  cache mutations no longer mark traffic and URL fields as fresh
- referral and partner response contracts plus presenters now live in
  `src/api/presenters/user_portal.py` instead of `src/api/endpoints/user.py`
- user profile, plan, subscription, activity, device, purchase, trial, and promocode response
  presenters now live in `src/api/presenters/user_account.py` instead of
  `src/api/endpoints/user.py`
- the old monolithic user router is now split across `src/api/endpoints/user_account.py`,
  `src/api/endpoints/user_subscription.py`, and `src/api/endpoints/user_portal.py`
- combined user-router composition now lives in `src/api/endpoints/__init__.py`; the temporary
  compatibility facade `src/api/endpoints/user.py` has been removed
- subscription request DTOs and request mappers now live in `src/api/contracts/user_subscription.py`
  instead of `src/api/endpoints/user_subscription.py`
- account and portal request DTOs now live in `src/api/contracts/user_account.py` and
  `src/api/contracts/user_portal.py` instead of their split endpoint modules
- web auth request DTOs now live in `src/api/contracts/web_auth.py` instead of
  `src/api/endpoints/web_auth.py`
- auth response contracts and pure response presenters now live in
  `src/api/presenters/web_auth.py` instead of `src/api/endpoints/web_auth.py`
- auth cookie/session transport helpers now live in `src/api/utils/web_auth_transport.py` instead
  of `src/api/endpoints/web_auth.py`
- auth dependency guards now live in `src/api/dependencies/web_auth.py` instead of
  `src/api/endpoints/web_auth.py`
- the active backend docs root is now cleaned up: `docs/README.md` was rewritten, a canonical
  `docs/BACKEND_OPERATOR_GUIDE.md` was added, and February 2026 handoff reports were moved under
  `docs/archive/2026-02-handoff/`
- backend audit now ignores `docs/archive`, so archived parity notes no longer pollute the current
  documentation audit surface
- shared web-app URL building now lives in `src/api/utils/web_app_urls.py` instead of router-local
  helper functions
- `src.infrastructure.taskiq.tasks` is now lazy-loaded instead of eagerly importing the full task
  package graph
- current-user profile assembly now lives in `src/services/user_profile.py`, shared by
  `src/api/endpoints/user_account.py` and `src/api/endpoints/web_auth.py`
- the next obvious backend cleanup target is the remaining root-level legacy docs
  (`BACKEND_AUTH_IMPLEMENTATION.md`, `QUICK_DEPLOY.md`), followed by a follow-up audit of whether
  runtime and device caches should stay separate or share a different cache boundary

## Goals

- remove the confirmed production-risk issues around payments, access control, and auth
- restore reliable backend quality gates
- reduce backend latency on the most expensive user flows
- reduce frontend bundle weight and avoid unnecessary network traffic
- make the project easier to operate, test, and evolve

## Baseline

Current measured baseline from the audit:

- `pytest`: 23 failed, 34 passed
- `mypy`: 233 errors in 33 files
- `ruff`: 325 issues
- frontend build: pass
- production source maps: enabled
- subscription and notification data: fixed 30-second polling
- `/subscription/list`: remote enrichment per item

## Delivery Principles

- fix correctness and security before micro-optimizations
- remove duplicated architecture before scaling it
- prefer measured changes on hot paths over broad speculative refactors
- restore CI signal early so later work does not regress silently

## Phase 0. Immediate Stabilization

Target window: 1 to 2 days

### Work

1. Repair payment webhook semantics.
   - return `5xx` when durable processing fails
   - keep `4xx` for invalid input or invalid signatures
   - add idempotency by `payment_id`

2. Remove fail-open access behavior.
   - if channel verification is required but unavailable, return a clear blocked or unavailable state
   - log and meter the failure path

3. Make auth rate limiting proxy-aware.
   - trust forwarded headers only from configured reverse proxies
   - verify the behavior through Nginx, not only direct app traffic

4. Disable production source maps by default.
   - move source-map generation behind an environment flag
   - ensure Nginx does not expose `.map` files in standard production deploys

5. Fix the local environment reproducibility gap.
   - replace the broken local virtual environment instead of relying on patched machine-specific paths

### Exit Criteria

- payment retries work correctly after internal processing failure
- access control is not bypassed during Telegram API or config failures
- rate limiting differentiates real users behind the proxy
- standard production frontend builds no longer publish `.map` files

## Phase 1. Auth and Security Consolidation

Target window: 3 to 5 days

### Work

1. Collapse duplicated auth entry points.
   - choose one public auth API
   - deprecate or remove the legacy `/auth` router

2. Move to one web token model.
   - one issuer or secret strategy
   - one refresh flow
   - one revoke and logout model

3. Reduce token exposure in the browser.
   - preferred direction: HttpOnly cookies plus SameSite and CSRF protection
   - fallback direction: keep storage temporarily but harden CSP and shorten token TTLs

4. Normalize security headers at the edge.
   - add a CSP
   - review outdated headers such as `X-XSS-Protection`

### Exit Criteria

- there is one primary web auth contract
- legacy JWT behavior is no longer mixed into modern web login flows
- logout and revoke semantics are consistent across all supported entry paths

## Phase 2. Backend Performance

Target window: 5 to 7 days

### Work

1. Redesign `/subscription/list` enrichment.
   - replace the remaining per-subscription device fan-out with bulk fetches or short-lived cache
     entries
   - separate stable snapshot data from expensive runtime details
   - reuse the same runtime snapshot path across device-management endpoints
   - keep webhook-driven cache mutations as the low-latency path for `devices_count`
   - keep task modules lazy so service boundaries do not regress into import cycles

2. Reduce duplicate remote and database reads in dashboard or settings flows.
   - identify repeated profile and access-status calls
   - cache lightweight results where freshness allows it

3. Split oversized endpoint orchestration.
   - move orchestration out of `src/api/endpoints/user.py` (partially completed for
     `/subscription/list`)
   - move orchestration out of `src/api/endpoints/web_auth.py`
   - create testable use-case or service units

4. Add profiling on hot paths.
   - `/subscription/list`
   - `/api/v1/auth/login`
   - `/api/v1/auth/access-status`
   - `/api/v1/user/me`

### Metrics

- cut median `/subscription/list` latency by at least 50 percent
- reduce the number of Remnawave calls per dashboard load
- reduce timeout incidence on subscription-related screens

## Phase 3. Frontend Performance and UX

Target window: 3 to 5 days

### Work

1. Replace fixed polling with adaptive refresh behavior.
   - refresh only while the relevant UI is visible
   - pause work in hidden tabs
   - use focus-based refresh where acceptable
   - add retry backoff after failures

2. Stabilize token refresh behavior.
   - add a refresh mutex or queue
   - prevent multiple parallel refresh calls after burst `401` responses

3. Reduce initial bundle cost.
   - review heavy dependencies in the initial route
   - lazy-load secondary dialogs and dashboard-only modules
   - keep manual chunking only when it measurably helps

4. Fix obvious UI-guideline drifts.
   - replace `transition-all`
   - add `aria-label` to icon-only controls
   - add `autocomplete` to auth forms
   - size static images explicitly

5. Add frontend tests for critical flows.
   - auth
   - purchase
   - settings
   - refresh-token failure and retry behavior

### Metrics

- lower background request volume for inactive tabs
- reduce initial JavaScript download size from the current baseline
- remove refresh-token race conditions under burst unauthorized responses

## Phase 4. Quality Gates and Operability

Target window: 1 to 2 weeks

### Work

1. Restore backend tests.
   - fix the current 23 failed tests
   - separate endpoint integration tests from service-level unit tests
   - stop depending on request-scoped DI state for logic that should be testable in isolation

2. Burn down typing errors in controlled batches.
   - batch 1: auth and user endpoints
   - batch 2: repositories and SQLAlchemy typing hotspots
   - batch 3: services and DTO mismatches

3. Introduce enforced CI gates.
   - backend: `ruff`, `pytest`, `mypy`
   - frontend: `eslint`, `tsc`, `vite build`

4. Clean repository noise.
   - remove generated caches and stale artifacts from source control scope
   - fix broken encodings and unreadable comments
   - document any intentionally committed reports

### Exit Criteria

- backend tests are green
- mypy is green at least for the auth and user critical path
- CI blocks regressions before merge or deploy
- repository noise is materially lower

## Highest-Value Quick Wins

These items provide the best effect-to-effort ratio:

1. Fix webhook `200 on failure`.
2. Close fail-open access checks.
3. Read forwarded IP correctly for rate limiting.
4. Disable production source maps.
5. Add frontend refresh mutex.
6. Reduce unnecessary polling.
7. Cut Remnawave fan-out in subscription listing.

## Recommended Execution Order

### Wave 1

- payment webhook status handling
- fail-open access check removal
- proxy-aware IP extraction
- disable production source maps
- frontend refresh mutex

### Wave 2

- auth router and token consolidation
- `/subscription/list` optimization
- polling reduction
- fix red tests around auth, access, and devices

### Wave 3

- decompose oversized endpoint modules
- complete mypy recovery
- add frontend tests for critical user flows

## Success Metrics Dashboard

Track these metrics during the plan:

- payment webhook retry success rate
- access-check failure mode counts
- auth rate-limit accuracy behind proxy
- median and p95 latency for `/subscription/list`
- number of Remnawave calls per dashboard load
- frontend initial JavaScript size
- background request count per inactive session
- failed test count
- mypy error count

## Expected Outcome

If the phases above are executed in order, the project should move from "feature-working but operationally risky" to "stable, measurable, and maintainable":

- production risks around payments and access control are removed first
- auth behavior becomes simpler and easier to secure
- the most expensive backend screen gets materially faster
- the frontend performs less unnecessary work
- quality gates become reliable enough to prevent regression accumulation
