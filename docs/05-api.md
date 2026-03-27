# AltShop API Inventory

Last audited against the live repository: `2026-03-26`

## Base rules

- Decorator-defined routes live under the base prefix `/api/v1`
- The current backend defines `64` decorator routes in `src/api/endpoints/`
- There is one separate programmatic route registered directly on the FastAPI app: `POST /telegram`
- Browser auth uses secure cookies plus `X-CSRF-Token` on unsafe methods when auth cookies are present

## Auth labels used below

- `none`: public route
- `user auth`: requires `get_current_user`
- `product access`: requires `require_web_product_access`
- `bearer secret`: requires `Authorization: Bearer <secret>`
- `telegram secret`: requires `X-Telegram-Bot-Api-Secret-Token`
- `gateway-specific`: validated by the selected payment gateway adapter
- `optional token`: user token is optional and used only for attribution

## Transport notes

### Primary browser transport

- access cookie: `altshop_access_token`
- refresh cookie: `altshop_refresh_token`
- CSRF cookie: `altshop_csrf_token`
- unsafe methods with cookie auth must include `X-CSRF-Token`

### Compatibility transport

`get_current_user()` also accepts `Authorization: Bearer ...`, but the web app uses cookie auth with `withCredentials`.

## Programmatic route

| Method | Path | Auth | Request | Response | Notes |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/telegram` | telegram secret | Telegram `Update` body | empty JSON `200` | registered through `TelegramWebhookEndpoint.register(...)`, not through a decorator router |

## Internal

| Method | Path | Auth | Request model | Response model | Notes |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/internal/release-notify` | bearer secret | `ReleaseNotifyRequest` | `UpdateCheckAuditSnapshot` | release version must match `tag_name`; returns `503` if the secret is not configured |

## Analytics

| Method | Path | Auth | Request model | Response model | Notes |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/analytics/web-events` | optional token | `WebAnalyticsEventRequest` | `OkResponse` | used for frontend and auth-funnel telemetry |

## Authentication routes

| Method | Path | Auth | Request model | Response model | Notes |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/auth/register` | none | `RegisterRequest` | `SessionResponse` | supports `telegram_id`, `name`, `referral_code`, `accept_rules`, `accept_channel_subscription`; Redis-backed per-IP plus per-identity throttles may return `429`, and duplicate identity failures are intentionally collapsed into a generic `400` |
| `GET` | `/api/v1/auth/registration/access-requirements` | none | query only | `RegistrationAccessRequirementsResponse` | rules and channel requirements for the UI |
| `GET` | `/api/v1/auth/access-status` | user auth | `force_channel_recheck` query | `AccessStatusResponse` | returns access level plus unmet requirements |
| `POST` | `/api/v1/auth/access/rules/accept` | user auth | none | `AccessStatusResponse` | records rules acceptance and re-evaluates access |
| `POST` | `/api/v1/auth/login` | none | `LoginRequest` | `SessionResponse` | username and password login |
| `POST` | `/api/v1/auth/web-account/bootstrap` | user auth | `WebAccountBootstrapRequest` | `SessionResponse` | creates username and password for an already linked web account |
| `POST` | `/api/v1/auth/telegram` | none | `TelegramAuthRequest` | `SessionResponse` | supports browser widget auth and Telegram Mini App `initData` auth; Redis-backed per-IP plus per-Telegram-identity throttles may return `429` and increment `web_auth_rate_limit_rejections_total` |
| `POST` | `/api/v1/auth/refresh` | refresh cookie | empty body | `SessionResponse` | validates refresh cookie and CSRF header when cookie auth is used |
| `POST` | `/api/v1/auth/logout` | user auth | none | `LogoutResponse` | increments `token_version` and clears cookies |
| `GET` | `/api/v1/auth/me` | user auth | none | `AuthMeResponse` | current authenticated profile |
| `GET` | `/api/v1/auth/branding` | none | none | `WebBrandingResponse` | branding, project name, locales, support links |
| `GET` | `/api/v1/auth/webapp-shell` | none | query passthrough | HTML | hidden route used by exact `/webapp/` requests so branding can shape the shell response |
| `POST` | `/api/v1/auth/telegram-link/request` | user auth | `TelegramLinkRequestPayload` | `TelegramLinkRequestResponse` | sends a Telegram confirmation code |
| `POST` | `/api/v1/auth/telegram-link/confirm` | user auth | `TelegramLinkConfirmPayload` | `TelegramLinkConfirmResponse` | may return `409` for merge-required conflicts |
| `POST` | `/api/v1/auth/telegram-link/remind-later` | user auth | none | `TelegramLinkStatusResponse` | snoozes the link prompt |
| `POST` | `/api/v1/auth/email/verify/request` | user auth | none | `MessageResponse` | requests email verification |
| `POST` | `/api/v1/auth/email/verify/confirm` | user auth | `VerifyEmailConfirmRequest` | `MessageResponse` | accepts either `code` or `token` |
| `POST` | `/api/v1/auth/password/forgot` | none | `ForgotPasswordRequest` | `MessageResponse` | username or email initiation |
| `POST` | `/api/v1/auth/password/forgot/telegram` | none | `ForgotPasswordTelegramRequest` | `MessageResponse` | Telegram reset initiation |
| `POST` | `/api/v1/auth/password/reset/by-link` | none | `ResetPasswordByLinkRequest` | `MessageResponse` | token-based reset |
| `POST` | `/api/v1/auth/password/reset/by-code` | none | `ResetPasswordByCodeRequest` | `MessageResponse` | email code reset |
| `POST` | `/api/v1/auth/password/reset/by-telegram-code` | none | `ResetPasswordByTelegramCodeRequest` | `MessageResponse` | Telegram code reset |
| `POST` | `/api/v1/auth/password/change` | user auth | `ChangePasswordRequest` | `MessageResponse` | changes password and reissues auth cookies |

## User profile, plans, and notifications

| Method | Path | Auth | Request model | Response model | Notes |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/user/me` | user auth | none | `UserProfileResponse` | aggregated user profile snapshot |
| `PATCH` | `/api/v1/user/security/email` | user auth | `SetSecurityEmailRequest` | `UserProfileResponse` | sets email and starts verify flow |
| `PATCH` | `/api/v1/user/partner-balance-currency` | user auth | `SetPartnerBalanceCurrencyRequest` | `UserProfileResponse` | nullable currency override |
| `GET` | `/api/v1/plans` | user auth | `channel` query | `list[PlanResponse]` | `channel` can be `WEB` or `TELEGRAM` |
| `GET` | `/api/v1/user/transactions` | user auth | `page`, `limit` | `TransactionHistoryResponse` | paginated transaction history |
| `GET` | `/api/v1/user/notifications` | user auth | `page`, `limit` | `UserNotificationListResponse` | paginated notification feed |
| `GET` | `/api/v1/user/notifications/unread-count` | user auth | none | `UnreadCountResponse` | unread counter |
| `POST` | `/api/v1/user/notifications/{notification_id}/read` | user auth | path only | `MarkReadResponse` | mark one notification as read |
| `POST` | `/api/v1/user/notifications/read-all` | user auth | none | `MarkReadResponse` | mark all notifications as read |

## Subscriptions, devices, and promocodes

| Method | Path | Auth | Request model | Response model | Notes |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/subscription/list` | product access | none | `SubscriptionListResponse` | list view may enqueue runtime refresh tasks |
| `GET` | `/api/v1/subscription/{subscription_id}/purchase-options` | product access | `purchase_type`, `channel` query | `SubscriptionPurchaseOptionsResponse` | supports `RENEW` and `UPGRADE` options |
| `GET` | `/api/v1/subscription/{subscription_id}` | product access | path only | `SubscriptionResponse` | full subscription snapshot |
| `PATCH` | `/api/v1/subscription/{subscription_id}/assignment` | product access | `SubscriptionAssignmentRequest` | `SubscriptionResponse` | partial update of `plan_id` and or `device_type` |
| `DELETE` | `/api/v1/subscription/{subscription_id}` | product access | path only | `dict` | `{success, message}` |
| `POST` | `/api/v1/subscription/purchase` | product access | `PurchaseRequest` | `PurchaseResponse` | supports `NEW`, `RENEW`, and `ADDITIONAL` |
| `POST` | `/api/v1/subscription/quote` | product access | `PurchaseQuoteRequest` | `PurchaseQuoteResponse` | quote without starting payment |
| `POST` | `/api/v1/subscription/{subscription_id}/renew` | product access | `PurchaseRequest` | `PurchaseResponse` | renewal alias |
| `POST` | `/api/v1/subscription/{subscription_id}/upgrade` | product access | `PurchaseRequest` | `PurchaseResponse` | upgrade alias |
| `GET` | `/api/v1/subscription/trial/eligibility` | product access | none | `TrialEligibilityResponse` | checks current trial eligibility |
| `POST` | `/api/v1/subscription/trial` | product access | `TrialRequest` or empty body | `SubscriptionResponse` | creates a trial subscription |
| `GET` | `/api/v1/devices` | product access | `subscription_id` query | `DeviceListResponse` | list devices for a subscription |
| `POST` | `/api/v1/devices/generate` | product access | `GenerateDeviceRequest` | `GenerateDeviceResponse` | generates a device link |
| `DELETE` | `/api/v1/devices/{hwid}` | product access | `subscription_id` query | `dict` | `{success, message}` |
| `POST` | `/api/v1/promocode/activate` | product access | `PromocodeActivateRequest` | `PromocodeActivateResponse` | may return `next_step` guidance |
| `GET` | `/api/v1/promocode/activations` | user auth | `page`, `limit` | `PromocodeActivationHistoryResponse` | activation history feed |

## Referral and partner portal

| Method | Path | Auth | Request model | Response model | Notes |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/referral/info` | user auth | none | `ReferralInfoResponse` | referral links, code, and points |
| `GET` | `/api/v1/referral/qr` | user auth | `target` query | raw PNG | `target=telegram|web` |
| `GET` | `/api/v1/referral/list` | user auth | `page`, `limit` | `ReferralListResponse` | referral events and qualification status |
| `GET` | `/api/v1/referral/exchange/options` | user auth | none | `ReferralExchangeOptionsResponse` | exchangeable reward options |
| `POST` | `/api/v1/referral/exchange/execute` | product access | `ReferralExchangeExecuteRequest` | `ReferralExchangeExecuteResponse` | executes points exchange |
| `GET` | `/api/v1/referral/about` | user auth | none | `ReferralAboutResponse` | explainer and FAQ payload |
| `GET` | `/api/v1/partner/info` | user auth | none | `PartnerInfoResponse` | partner cabinet summary |
| `GET` | `/api/v1/partner/referrals` | user auth | `page`, `limit` | `PartnerReferralsListResponse` | partner referral list |
| `GET` | `/api/v1/partner/earnings` | user auth | `page`, `limit` | `PartnerEarningsListResponse` | earnings history |
| `POST` | `/api/v1/partner/withdraw` | product access | `PartnerWithdrawalRequest` | `PartnerWithdrawalResponse` | creates a withdrawal request |
| `GET` | `/api/v1/partner/withdrawals` | user auth | none | `PartnerWithdrawalsListResponse` | withdrawal history |

## Payments and service webhooks

| Method | Path | Auth | Request | Response | Notes |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/payments/yoomoney/redirect` | token query | `token` query | HTML page | auto-submit redirect form to YooMoney |
| `POST` | `/api/v1/payments/{gateway_type}` | gateway-specific | raw webhook payload | gateway response or `400` or `403` or `503` | records dedup state in `PaymentWebhookEventService` before enqueue |
| `POST` | `/api/v1/remnawave` | Remnawave signature | raw webhook payload | `200 OK` or auth error | route path comes from `REMNAWAVE_WEBHOOK_PATH` |

`src/core/config/app.py` builds payment webhook URLs with the `/api/v1/payments/{gateway_type}` prefix. Treat that path as the canonical operator contract.

## Error semantics

Common patterns in the current endpoints:

- `400`: validation or malformed request
- `401`: missing auth, invalid token, or unsupported auth scheme
- `403`: access denied or invalid CSRF token
- `404`: entity not found
- `409`: Telegram-link merge conflict
- `422`: release version mismatch in the internal release-notify endpoint
- `429`: rate-limit exceeded
- `503`: secret missing or infrastructure failure during webhook enqueue

`detail` varies by route:

- plain string for simple errors
- object `{code, message}` for some referral, partner, and Telegram-link conflicts
- object `{code, message, unmet_requirements}` for web-access guard responses

## Related docs

- Full request and response shapes: [API_CONTRACT.md](API_CONTRACT.md)
- Payment-specific notes: [07-payment-gateways.md](07-payment-gateways.md)
- Cookie and CSRF behavior: [02-architecture.md](02-architecture.md)
- Env and deployment prerequisites: [08-configuration.md](08-configuration.md), [09-deployment.md](09-deployment.md)
