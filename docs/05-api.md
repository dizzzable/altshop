# AltShop API Inventory

Проверено по коду: `2026-03-08`

## Базовые правила

- Base prefix для decorator-defined API: `/api/v1`
- Всего route decorators в `src/api/endpoints`: 60
- Отдельно существует programmatic Telegram webhook route
- Основной web auth transport: secure cookies + CSRF header на unsafe methods

## Аутентификация и transport

### Primary auth transport

- access cookie: `altshop_access_token`
- refresh cookie: `altshop_refresh_token`
- csrf cookie: `altshop_csrf_token`
- для unsafe methods cookie-auth требует `X-CSRF-Token`

### Compatibility transport

`get_current_user()` также принимает `Authorization: Bearer ...`, но для browser/web-app это fallback, а не основной сценарий.

### Auth labels в таблицах ниже

- `none` — endpoint открыт
- `user auth` — требуется `get_current_user`
- `product access` — требуется `require_web_product_access`
- `optional token` — токен читается опционально

## Programmatic route

| Method | Path | Auth | Request | Response | Notes |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/telegram` | `X-Telegram-Bot-Api-Secret-Token` | Telegram `Update` | empty JSON `200` | route регистрируется `TelegramWebhookEndpoint.register(...)`, не через decorator |

## Analytics

| Method | Path | Auth | Request model | Response model | Notes |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/analytics/web-events` | optional token | `WebAnalyticsEventRequest` | `OkResponse` | token нужен только для optional user attribution |

## Auth routes

| Method | Path | Auth | Request model | Response model | Notes |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/auth/register` | none | `RegisterRequest` | `SessionResponse` | username/password register, optional `telegram_id`, `referral_code` |
| `GET` | `/api/v1/auth/registration/access-requirements` | none | query only | `RegistrationAccessRequirementsResponse` | rules/channel requirements для UI |
| `GET` | `/api/v1/auth/access-status` | user auth | `force_channel_recheck` query | `AccessStatusResponse` | возвращает full/read_only/blocked access level |
| `POST` | `/api/v1/auth/access/rules/accept` | user auth | none | `AccessStatusResponse` | фиксирует принятие правил |
| `POST` | `/api/v1/auth/login` | none | `LoginRequest` | `SessionResponse` | cookie session login |
| `POST` | `/api/v1/auth/web-account/bootstrap` | user auth | `WebAccountBootstrapRequest` | `SessionResponse` | создаёт username/password для уже связанного web account |
| `POST` | `/api/v1/auth/telegram` | none | `TelegramAuthRequest` | `SessionResponse` | widget и Mini App auth |
| `POST` | `/api/v1/auth/refresh` | refresh cookie | empty body | `SessionResponse` | требует CSRF при cookie transport |
| `POST` | `/api/v1/auth/logout` | user auth | none | `LogoutResponse` | инкрементирует `token_version`, чистит cookies |
| `GET` | `/api/v1/auth/me` | user auth | none | `AuthMeResponse` | web-auth oriented профиль |
| `GET` | `/api/v1/auth/branding` | none | none | `WebBrandingResponse` | project name, locales, support URL |
| `POST` | `/api/v1/auth/telegram-link/request` | user auth | `TelegramLinkRequestPayload` | `TelegramLinkRequestResponse` | шлёт код в Telegram |
| `POST` | `/api/v1/auth/telegram-link/confirm` | user auth | `TelegramLinkConfirmPayload` | `TelegramLinkConfirmResponse` | может вернуть `409` для merge-required конфликтов |
| `POST` | `/api/v1/auth/telegram-link/remind-later` | user auth | none | `TelegramLinkStatusResponse` | snooze link prompt |
| `POST` | `/api/v1/auth/email/verify/request` | user auth | none | `MessageResponse` | отправка verify email |
| `POST` | `/api/v1/auth/email/verify/confirm` | user auth | `VerifyEmailConfirmRequest` | `MessageResponse` | принимает `code` или `token` |
| `POST` | `/api/v1/auth/password/forgot` | none | `ForgotPasswordRequest` | `MessageResponse` | username or email |
| `POST` | `/api/v1/auth/password/forgot/telegram` | none | `ForgotPasswordTelegramRequest` | `MessageResponse` | reset flow через Telegram code |
| `POST` | `/api/v1/auth/password/reset/by-link` | none | `ResetPasswordByLinkRequest` | `MessageResponse` | token-based reset |
| `POST` | `/api/v1/auth/password/reset/by-code` | none | `ResetPasswordByCodeRequest` | `MessageResponse` | email code reset |
| `POST` | `/api/v1/auth/password/reset/by-telegram-code` | none | `ResetPasswordByTelegramCodeRequest` | `MessageResponse` | Telegram code reset |
| `POST` | `/api/v1/auth/password/change` | user auth | `ChangePasswordRequest` | `MessageResponse` | меняет пароль и перевыпускает auth cookies |

## User profile, plans и activity

| Method | Path | Auth | Request model | Response model | Notes |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/user/me` | user auth | none | `UserProfileResponse` | агрегированный профиль пользователя |
| `PATCH` | `/api/v1/user/security/email` | user auth | `SetSecurityEmailRequest` | `UserProfileResponse` | задаёт email и запускает verify flow |
| `PATCH` | `/api/v1/user/partner-balance-currency` | user auth | `SetPartnerBalanceCurrencyRequest` | `UserProfileResponse` | nullable currency override |
| `GET` | `/api/v1/plans` | user auth | `channel` query | `list[PlanResponse]` | `channel` = `WEB` или `TELEGRAM` |
| `GET` | `/api/v1/user/transactions` | user auth | `page`, `limit` | `TransactionHistoryResponse` | paginated history |
| `GET` | `/api/v1/user/notifications` | user auth | `page`, `limit` | `UserNotificationListResponse` | paginated notifications |
| `GET` | `/api/v1/user/notifications/unread-count` | user auth | none | `UnreadCountResponse` | unread counter |
| `POST` | `/api/v1/user/notifications/{notification_id}/read` | user auth | path only | `MarkReadResponse` | single mark read |
| `POST` | `/api/v1/user/notifications/read-all` | user auth | none | `MarkReadResponse` | bulk mark read |

## Subscriptions, devices и promocodes

| Method | Path | Auth | Request model | Response model | Notes |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/subscription/list` | product access | none | `SubscriptionListResponse` | batch runtime refresh через background task |
| `GET` | `/api/v1/subscription/{subscription_id}` | product access | path only | `SubscriptionResponse` | detail snapshot |
| `PATCH` | `/api/v1/subscription/{subscription_id}/assignment` | product access | `SubscriptionAssignmentRequest` | `SubscriptionResponse` | частичное обновление `plan_id` и/или `device_type` |
| `DELETE` | `/api/v1/subscription/{subscription_id}` | product access | path only | `dict` | `{success, message}` |
| `POST` | `/api/v1/subscription/purchase` | product access | `PurchaseRequest` | `PurchaseResponse` | NEW, RENEW, ADDITIONAL |
| `POST` | `/api/v1/subscription/quote` | product access | `PurchaseQuoteRequest` | `PurchaseQuoteResponse` | расчёт quote без запуска платежа |
| `POST` | `/api/v1/subscription/{subscription_id}/renew` | product access | `PurchaseRequest` | `PurchaseResponse` | renewal alias endpoint |
| `GET` | `/api/v1/subscription/trial/eligibility` | product access | none | `TrialEligibilityResponse` | проверка eligibility |
| `POST` | `/api/v1/subscription/trial` | product access | `TrialRequest` or empty | `SubscriptionResponse` | создание trial subscription |
| `GET` | `/api/v1/devices` | product access | `subscription_id` query | `DeviceListResponse` | device list по подписке |
| `POST` | `/api/v1/devices/generate` | product access | `GenerateDeviceRequest` | `GenerateDeviceResponse` | создаёт device link |
| `DELETE` | `/api/v1/devices/{hwid}` | product access | `subscription_id` query | `dict` | `{success, message}` |
| `POST` | `/api/v1/promocode/activate` | product access | `PromocodeActivateRequest` | `PromocodeActivateResponse` | может вернуть `next_step` |
| `GET` | `/api/v1/promocode/activations` | user auth | `page`, `limit` | `PromocodeActivationHistoryResponse` | history UI |

## Referral и partner portal

| Method | Path | Auth | Request model | Response model | Notes |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/referral/info` | user auth | none | `ReferralInfoResponse` | referral links, code, points |
| `GET` | `/api/v1/referral/qr` | user auth | `target` query | raw PNG | `target=telegram|web` |
| `GET` | `/api/v1/referral/list` | user auth | `page`, `limit` | `ReferralListResponse` | events, qualification, invite source |
| `GET` | `/api/v1/referral/exchange/options` | user auth | none | `ReferralExchangeOptionsResponse` | доступные exchange types |
| `POST` | `/api/v1/referral/exchange/execute` | product access | `ReferralExchangeExecuteRequest` | `ReferralExchangeExecuteResponse` | subscription/gift/discount/traffic exchange |
| `GET` | `/api/v1/referral/about` | user auth | none | `ReferralAboutResponse` | explainer/FAQ |
| `GET` | `/api/v1/partner/info` | user auth | none | `PartnerInfoResponse` | partner status, currency, level settings |
| `GET` | `/api/v1/partner/referrals` | user auth | `page`, `limit` | `PartnerReferralsListResponse` | partner referral list |
| `GET` | `/api/v1/partner/earnings` | user auth | `page`, `limit` | `PartnerEarningsListResponse` | earnings history |
| `POST` | `/api/v1/partner/withdraw` | product access | `PartnerWithdrawalRequest` | `PartnerWithdrawalResponse` | creates withdrawal request |
| `GET` | `/api/v1/partner/withdrawals` | user auth | none | `PartnerWithdrawalsListResponse` | withdrawal history |

## Payment и service webhooks

| Method | Path | Auth | Request | Response | Notes |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/payments/yoomoney/redirect` | token query | `token` query | HTML page | auto-submit redirect form to YooMoney |
| `POST` | `/api/v1/payments/{gateway_type}` | gateway-specific | raw webhook payload | gateway response / `400` / `403` / `503` | deduplicates via `PaymentWebhookEventService` |
| `POST` | `/api/v1/remnawave` | Remnawave signature | raw webhook payload | `200 OK` or auth error | route path comes from `REMNAWAVE_WEBHOOK_PATH` |

## Error semantics

Основные patterns:

- validation and bad request: `400`
- auth required / invalid token: `401`
- access denied: `403`
- not found: `404`
- Telegram link merge conflict: `409`
- rate limit exceeded: `429`
- webhook enqueue or infrastructure failure: `503`

`detail` shape зависит от route:

- string detail для простых ошибок
- dict `{code, message}` для части referral/partner/web access ошибок
- dict `{code, message, unmet_requirements}` для web access guard responses

## Что дальше

- Полные request/response shapes: [API_CONTRACT.md](API_CONTRACT.md)
- Cookie/CSRF details: [02-architecture.md](02-architecture.md)
- Env и proxy prerequisites: [08-configuration.md](08-configuration.md)
