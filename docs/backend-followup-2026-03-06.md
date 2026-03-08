> [!WARNING]
> Исторический документ. Этот файл не входит в канонический комплект документации и не переаудировался в текущем проходе. Актуальная точка входа: [docs/README.md](README.md)

# Backend Follow-Up Backlog

Date: 2026-03-06

## Current Verified Baseline

The backend state after Wave 5B is materially better than the initial March 6 audit. The remaining
work is now mostly about compatibility sunset and future provider onboarding, not emergency runtime
cleanup.

Verified locally in the repaired `uv` environment:

- `uv run python -m ruff check src tests scripts`: pass
- `uv run python -m pytest -q`: `139 passed`
- `uv run python -m mypy src`: pass (`Success: no issues found in 335 source files`)
- `uv run python scripts/backend_audit_report.py`: pass

For convenience, `make backend-audit` now runs:

1. `backend-check`
2. `backend-legacy-report`

This target is now expected to stay green.

`make backend-legacy-report` currently prints:

- current full-`mypy` hotspots
- remaining `auth_username` references grouped into runtime, migrations, tests, docs, and tooling
- auth compatibility surface separately from payment legacy cleanup
- payment compatibility code still present in runtime

Current audit snapshot:

- auth compatibility surface:
  - none detected
- payment compatibility code present:
  - none detected

## Remaining Legacy and Stability Clusters

### 1. Legacy auth schema still exists beside the web-account model

The largest auth-related legacy problem is no longer an active runtime split. It is now
concentrated in the old `users.auth_username/password_hash` schema and its migration history,
while live auth behavior already runs through `web_accounts`.

Primary evidence:

- `src/infrastructure/database/migrations/versions/0028_add_auth_fields.py`
- `src/infrastructure/database/migrations/versions/0029_repair_auth_fields_if_missing.py`
- `src/infrastructure/database/migrations/versions/0030_add_web_accounts_and_auth_challenges.py`
- `src/infrastructure/database/migrations/versions/0040_drop_legacy_user_auth_columns.py`

Why it still hurts:

- migration history still references those columns for add/repair/backfill/drop flows
- environments that have not yet applied `0040` still physically retain the legacy columns
- rollback safety still depends on the downgrade path restoring a compatible snapshot from
  `web_accounts`

What is already removed:

- deprecated runtime `AuthService` wiring
- analytics acceptance of legacy bot-secret access JWTs
- endpoint-level reads from `user.auth_username`
- runtime writes to `users.auth_username`
- runtime `users.password_hash` mirroring
- `UserRepository.get_by_auth_username(...)`
- runtime exposure of legacy auth fields from `UserDto` and the active ORM model

Current compatibility write paths:

- none in active backend runtime paths

Current compatibility read or fallback paths:

- none in active backend runtime paths
- `make backend-legacy-report` currently finds `auth_username` only in four migration files, this
  document, and the audit tooling

Recommended next step:

1. Roll out migration `0040` across all environments so the live schema matches the runtime model.
2. Treat `web_accounts` as the only writable source of truth for username and password.
3. Remove or clearly mark now-obsolete repair migrations as historical-only after rollout is complete.

### 2. Legacy auth compatibility router is removed

The deprecated `/auth/*` compatibility router has been deleted from active runtime code.

Primary evidence:

- `src/api/app.py`
- `src/api/endpoints/__init__.py`
- `scripts/backend_audit_report.py`

Current state:

- `/auth/register`, `/auth/login`, and `/auth/logout` no longer exist as backend API routes
- the app factory no longer mounts a compatibility auth router
- `make backend-legacy-report` now prints `Auth compatibility surface -> none detected`

Why it matters:

- the backend auth contract is now limited to `/api/v1/auth/*`
- there is no remaining opt-in path that could silently preserve the old public API shape

Recommended next step:

1. Track any operational fallout only at the ingress/log level if external callers were still using
   `/auth/*`.
2. Keep the audit report as a guardrail so this router does not return unnoticed.

### 3. Frontend auth still looks token-driven even though runtime auth is cookie-first

This is no longer a backend correctness bug, but it still preserves misleading compatibility
shapes and slows future cleanup.

Primary evidence:

- `web-app/src/lib/api.ts`
- `web-app/src/pages/auth/LoginPage.tsx`
- `web-app/src/pages/auth/RegisterPage.tsx`
- `web-app/src/pages/dashboard/SettingsPage.tsx`
- `web-app/src/components/layout/DashboardLayout.tsx`
- `web-app/src/types/index.ts`

Current state:

- auth JSON responses are now cookie-first and no longer expose `access_token` or `refresh_token`
- dead `setTokens(...)`, `getAccessToken()`, and `getRefreshToken()` helpers are removed
- the remaining cleanup is explicit legacy storage deletion via `clearLegacyAuthStorage()`
- refresh is now cookie-only and no longer accepts `refresh_token` in the request body

Recommended next step:

1. Remove stale docs and examples that still show token JSON or localStorage-based refresh flows.
2. Decide whether Bearer-header fallback should remain for non-browser clients or be narrowed next.

### 4. Full mypy debt is currently cleared

The backend now passes full-repo type checking:

- `uv run python -m mypy src`: pass
- `uv run python scripts/backend_audit_report.py`: `0` typing errors, `0` files with errors

What this implies:

- `backend-check` can keep enforcing full `mypy src`
- CI can keep enforcing full backend typing
- new mypy regressions should be treated as blocking, not as future cleanup

### 5. Payment compatibility cleanup is complete for active runtime gateways

The payment deletion wave is complete for the compatibility branches that remained after Wave 5A.
The backend no longer keeps fallback request or webhook contracts for `Heleket`, `Platega`, or
`Pal24`.

Primary evidence:

- `src/infrastructure/payment_gateways/heleket.py`
- `src/infrastructure/payment_gateways/platega.py`
- `src/infrastructure/payment_gateways/pal24.py`
- `scripts/backend_audit_report.py`

Current state:

- Heleket now uses only the documented `v1` create-payment and payment-info flow
- Heleket webhook verification no longer accepts the older legacy signature mode
- Heleket mode counters are now official-only:
  - `payment_gateway_request_mode_total{gateway_type="HELEKET", operation="create_payment"|"payment_info", mode="v1"}`
  - `payment_gateway_webhook_signature_mode_total{gateway_type="HELEKET", mode="v1"}`
- Platega now accepts only the documented callback body and required callback headers
- Platega no longer accepts the old headerless `payload`-based webhook contract
- Platega mode counters are now official-only:
  - `payment_gateway_webhook_mode_total{gateway_type="PLATEGA", mode="official_callback", auth_mode="callback_headers"}`
- Pal24 now accepts only the documented form-based create-payment and official form postback webhook
- Pal24 no longer keeps the old JSON `/bills/create` + `X-Signature` runtime contract
- Pal24 mode counters are now official-only:
  - `payment_gateway_request_mode_total{gateway_type="PAL24", operation="create_payment", mode="official_form"}`
  - `payment_gateway_webhook_mode_total{gateway_type="PAL24", mode="official_form_postback"}`
- `make backend-legacy-report` now prints `Payment compatibility code present -> none detected`

Why it matters:

- each active gateway now has one request contract and one webhook contract
- future provider audits no longer need to account for hidden fallback behavior in these modules
- the next payment work can focus on provider onboarding or provider correctness, not legacy sunset

Recommended next step:

1. Keep `backend-legacy-report` as a guardrail so payment compatibility code does not return unnoticed.
2. If a payment audit resumes, focus on contract correctness or onboarding of a new provider.

### 6. Provider onboarding is still manual

The repo now has a cleaner payment baseline, but adding a new provider is still a manual pass
through multiple backend, bot, and web touchpoints.

Current state:

- dormant in-repo candidates:
  - `CRYPTOMUS`
  - `ROBOKASSA`
- both already exist in `PaymentGatewayType`, DTO settings types, and web `PaymentGatewayType`
  unions, but they are not wired into gateway DI or default gateway creation
- asset/doc-ready but runtime-not-ready candidates:
  - `Stripe`
  - `CloudPayments`
  - `MulenPay`
- `.svg` assets already exist for those names in `web-app/src/assets/payment-gateways`
- there is still no generic provider-registration mechanism; onboarding remains manual

Manual touchpoints that still need to be updated for each new provider:

1. `PaymentGatewayType` enum and `Currency.from_gateway_type(...)`
2. gateway settings DTO plus the `AnyGatewaySettingsDto` discriminator union
3. gateway class export and DI map in payment gateway provider wiring
4. `PaymentGatewayService.create_default()` so the gateway can be provisioned in new environments
5. partner commission defaults and partner bot/admin UI
6. web icon mapping in `web-app/src/lib/payment-gateway-icons.ts`
7. backend tests for create-payment, webhook handling, compatibility policy, and audit visibility

Why it matters:

- "half-added" providers are easy to create because assets, enum values, and DTO shells can exist
  without runtime wiring
- `CRYPTOMUS` and `ROBOKASSA` are the cheapest next providers because the repo already contains part
  of that groundwork
- `Stripe`, `CloudPayments`, and `MulenPay` should not be started as quick wins unless the team is
  willing to do the full onboarding pass above

Recommended next step:

1. If provider expansion resumes soon, start with `CRYPTOMUS` or `ROBOKASSA`.
2. If multiple new providers are expected, build generic onboarding/scaffolding first so partner
   commissions, icon mapping, and default provisioning stop being manual one-off edits.

### 7. Warning debt from the previous wave is now cleared

The backend test run is green without the earlier warning summary.

What changed:

- config validators were moved from deprecated `FieldValidationInfo` to `ValidationInfo`
- taskiq tasks now use `@inject(patch_module=True)` to match current Dishka expectations

What this implies:

- the next follow-up should not spend time on the earlier pydantic/taskiq warning stream unless it
  returns after dependency updates
- any new warning class should be treated as a fresh regression, not as known carry-over debt

## Suggested Execution Order

1. Keep `web_accounts` as the sole runtime auth source of truth and roll out migration `0040` that drops `users.auth_*`.
2. Keep `/api/v1/auth/*` as the only backend auth surface and prevent `/auth/*` compatibility code from returning.
3. If provider work resumes, prefer `CRYPTOMUS` / `ROBOKASSA` first or invest in generic onboarding scaffolding before `Stripe` / `CloudPayments` / `MulenPay`.
4. Remove or archive obsolete migration-era tooling as soon as it no longer protects a real deployment path.

## Useful Commands

Stable backend gates:

- `uv sync --locked --group dev`
- `uv run python -m ruff check src tests scripts`
- `uv run python -m pytest -q`
- `uv run python -m mypy src`

Full follow-up audit:

- `make backend-check`
- `make backend-audit`
- `make backend-legacy-report`
