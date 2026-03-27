# AltShop API Contract

Проверено по коду: `2026-03-08`

Этот файл описывает transport rules и реальные request/response shapes по текущим `contracts` и `presenters`. Полный инвентарь route decorators см. в [05-api.md](05-api.md).

## Базовые правила

- Base prefix для decorator-defined API: `/api/v1`
- Route decorators в `src/api/endpoints`: `64`
- Отдельно существует programmatic route: `POST /telegram`
- Глобального envelope вида `{data,error}` нет
- Основной web auth transport: secure cookies + CSRF

## Transport и auth contract

### Session cookies

| Cookie | Path | Lifetime | Назначение |
| --- | --- | --- | --- |
| `altshop_access_token` | `/` | `7 days` | основной access token |
| `altshop_refresh_token` | `/api/v1/auth` | `30 days` | refresh token |
| `altshop_csrf_token` | `/` | `30 days` | double-submit CSRF token |

Все три cookie сейчас выставляются с:

- `Secure`
- `SameSite=lax`
- `Cache-Control: no-store` на auth responses

### CSRF

- Для `GET`, `HEAD`, `OPTIONS` CSRF не требуется.
- Для unsafe methods при cookie-auth обязателен заголовок `X-CSRF-Token`.
- Проверяется совпадение header token и `altshop_csrf_token`.

### Bearer fallback

- `get_current_user()` принимает `Authorization: Bearer <token>` как fallback.
- Для browser/web-app это совместимость, а не основной сценарий.
- Analytics endpoint использует optional bearer только для привязки события к пользователю.

## Error body contract

Текущие endpoints возвращают несколько форм `detail`:

- plain string
- dict `{ "code": "...", "message": "..." }`
- dict `{ "code": "...", "message": "...", "unmet_requirements": [...] }`

Типичные статусы:

- `400` validation / bad request / state errors
- `401` not authenticated / invalid token / invalid webhook signature
- `403` access denied / invalid CSRF / invite or purchase restrictions
- `404` entity not found
- `409` telegram link merge conflict
- `429` auth rate limit
- `503` webhook enqueue / infrastructure failures

Дополнительно по web auth:

- `POST /api/v1/auth/register` и `POST /api/v1/auth/telegram` могут вернуть `429`, если сработал Redis-backed throttle по client IP или identity.
- `POST /api/v1/auth/register` специально не различает "username уже занят" и "telegram_id уже привязан" во внешнем `400 detail`, чтобы не давать surface для account discovery.

## Analytics surface

### Route

| Method | Path | Auth | Request | Response |
| --- | --- | --- | --- | --- |
| `POST` | `/api/v1/analytics/web-events` | optional bearer | `WebAnalyticsEventRequest` | `OkResponse` |

### `WebAnalyticsEventRequest`

```json
{
  "event_name": "telegram_auth_success",
  "source_path": "/webapp/auth",
  "session_id": "abc123",
  "device_mode": "web",
  "is_in_telegram": false,
  "has_init_data": false,
  "start_param": "ref_xxx",
  "has_query_id": false,
  "chat_type": null,
  "meta": {}
}
```

Ограничения:

- `event_name` фиксирован literal enum
- `source_path`: `1..255`
- `session_id`: `1..64`
- `device_mode`: `telegram-mobile | telegram-desktop | web`

### `OkResponse`

```json
{
  "ok": true
}
```

## Auth surface

### Routes

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/register` | `RegisterRequest` | `SessionResponse` |
| `GET` | `/api/v1/auth/registration/access-requirements` | query only | `RegistrationAccessRequirementsResponse` |
| `GET` | `/api/v1/auth/access-status` | query `force_channel_recheck` | `AccessStatusResponse` |
| `POST` | `/api/v1/auth/access/rules/accept` | empty | `AccessStatusResponse` |
| `POST` | `/api/v1/auth/login` | `LoginRequest` | `SessionResponse` |
| `POST` | `/api/v1/auth/web-account/bootstrap` | `WebAccountBootstrapRequest` | `SessionResponse` |
| `POST` | `/api/v1/auth/telegram` | `TelegramAuthRequest` | `SessionResponse` |
| `POST` | `/api/v1/auth/refresh` | empty | `SessionResponse` |
| `POST` | `/api/v1/auth/logout` | empty | `LogoutResponse` |
| `GET` | `/api/v1/auth/me` | empty | `AuthMeResponse` |
| `GET` | `/api/v1/auth/branding` | empty | `WebBrandingResponse` |
| `POST` | `/api/v1/auth/telegram-link/request` | `TelegramLinkRequestPayload` | `TelegramLinkRequestResponse` |
| `POST` | `/api/v1/auth/telegram-link/confirm` | `TelegramLinkConfirmPayload` | `TelegramLinkConfirmResponse` |
| `POST` | `/api/v1/auth/telegram-link/remind-later` | empty | `TelegramLinkStatusResponse` |
| `POST` | `/api/v1/auth/email/verify/request` | empty | `MessageResponse` |
| `POST` | `/api/v1/auth/email/verify/confirm` | `VerifyEmailConfirmRequest` | `MessageResponse` |
| `POST` | `/api/v1/auth/password/forgot` | `ForgotPasswordRequest` | `MessageResponse` |
| `POST` | `/api/v1/auth/password/forgot/telegram` | `ForgotPasswordTelegramRequest` | `MessageResponse` |
| `POST` | `/api/v1/auth/password/reset/by-link` | `ResetPasswordByLinkRequest` | `MessageResponse` |
| `POST` | `/api/v1/auth/password/reset/by-code` | `ResetPasswordByCodeRequest` | `MessageResponse` |
| `POST` | `/api/v1/auth/password/reset/by-telegram-code` | `ResetPasswordByTelegramCodeRequest` | `MessageResponse` |
| `POST` | `/api/v1/auth/password/change` | `ChangePasswordRequest` | `MessageResponse` |

### Auth request models

`RegisterRequest`

```json
{
  "username": "john_doe",
  "password": "secret123",
  "telegram_id": 123456789,
  "name": "John Doe",
  "referral_code": "ref_xxxx",
  "accept_rules": true,
  "accept_channel_subscription": true
}
```

`LoginRequest`

```json
{
  "username": "john_doe",
  "password": "secret123"
}
```

`WebAccountBootstrapRequest`

```json
{
  "username": "john_doe",
  "password": "secret123"
}
```

`TelegramAuthRequest` поддерживает два режима:

1. Telegram widget fields:

```json
{
  "id": 123456789,
  "first_name": "John",
  "last_name": "Doe",
  "username": "john_doe",
  "photo_url": "https://...",
  "auth_date": 1710000000,
  "hash": "..."
}
```

2. Mini App payload:

```json
{
  "initData": "query_id=...&user=...&auth_date=...&hash=...",
  "queryId": "...",
  "isTest": false,
  "referralCode": "ref_xxxx"
}
```

Другие auth payloads:

- `TelegramLinkRequestPayload`: `{ "telegram_id": 123456789 }`
- `TelegramLinkConfirmPayload`: `{ "telegram_id": 123456789, "code": "123456" }`
- `VerifyEmailConfirmRequest`: `{ "code": "123456" }` или `{ "token": "..." }`
- `ForgotPasswordRequest`: `{ "username": "john" }` или `{ "email": "user@example.com" }`
- `ResetPasswordByLinkRequest`: `{ "token": "...", "new_password": "..." }`
- `ResetPasswordByCodeRequest`: `{ "email": "user@example.com", "code": "123456", "new_password": "..." }`
- `ForgotPasswordTelegramRequest`: `{ "username": "john" }`
- `ResetPasswordByTelegramCodeRequest`: `{ "username": "john", "code": "123456", "new_password": "..." }`
- `ChangePasswordRequest`: `{ "current_password": "...", "new_password": "..." }`

### Auth response models

`SessionResponse`

```json
{
  "expires_in": 604800,
  "is_new_user": false,
  "auth_source": "WEB_PASSWORD"
}
```

Важно: access/refresh tokens находятся не в body, а в response cookies.

`LogoutResponse`

```json
{
  "message": "Logged out successfully"
}
```

`MessageResponse`

```json
{
  "message": "Email verified"
}
```

`AuthMeResponse`

```json
{
  "telegram_id": 123456789,
  "username": "john_doe",
  "name": "John Doe",
  "role": "USER",
  "points": 0,
  "language": "ru",
  "default_currency": "RUB",
  "personal_discount": 0,
  "purchase_discount": 0,
  "partner_balance_currency_override": null,
  "effective_partner_balance_currency": "RUB",
  "is_blocked": false,
  "is_bot_blocked": false,
  "created_at": "2026-03-08T10:00:00+00:00",
  "updated_at": "2026-03-08T10:00:00+00:00",
  "email": "user@example.com",
  "email_verified": false,
  "telegram_linked": false,
  "linked_telegram_id": null,
  "show_link_prompt": false,
  "requires_password_change": false,
  "effective_max_subscriptions": 1,
  "active_subscriptions_count": 0,
  "is_partner": false,
  "is_partner_active": false,
  "has_web_account": true,
  "needs_web_credentials_bootstrap": false
}
```

`RegistrationAccessRequirementsResponse`

```json
{
  "access_mode": "OPEN",
  "rules_required": false,
  "channel_required": false,
  "rules_link": null,
  "channel_link": null,
  "requires_telegram_id": false,
  "tg_id_helper_bot_link": "https://t.me/userinfobot",
  "verification_bot_link": null
}
```

`AccessStatusResponse`

```json
{
  "access_mode": "OPEN",
  "rules_required": false,
  "channel_required": false,
  "requires_telegram_id": false,
  "access_level": "full",
  "channel_check_status": "not_required",
  "rules_accepted": true,
  "telegram_linked": false,
  "channel_verified": false,
  "linked_telegram_id": null,
  "rules_link": null,
  "channel_link": null,
  "tg_id_helper_bot_link": "https://t.me/userinfobot",
  "verification_bot_link": null,
  "unmet_requirements": [],
  "can_use_product_features": true
}
```

`WebBrandingResponse`

```json
{
  "project_name": "AltShop",
  "web_title": "AltShop",
  "default_locale": "ru",
  "supported_locales": ["ru", "en"],
  "support_url": "https://t.me/support_username"
}
```

`TelegramLinkRequestResponse`

```json
{
  "message": "Code sent",
  "delivered": true,
  "expires_in_seconds": 600
}
```

`TelegramLinkConfirmResponse`

```json
{
  "message": "Telegram linked",
  "linked_telegram_id": 123456789
}
```

`TelegramLinkStatusResponse`

```json
{
  "telegram_linked": false,
  "linked_telegram_id": null,
  "show_link_prompt": false
}
```

## User account surface

### Routes

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| `GET` | `/api/v1/user/me` | empty | `UserProfileResponse` |
| `PATCH` | `/api/v1/user/security/email` | `SetSecurityEmailRequest` | `UserProfileResponse` |
| `PATCH` | `/api/v1/user/partner-balance-currency` | `SetPartnerBalanceCurrencyRequest` | `UserProfileResponse` |
| `GET` | `/api/v1/plans` | query `channel` | `list[PlanResponse]` |
| `GET` | `/api/v1/user/transactions` | query `page`, `limit` | `TransactionHistoryResponse` |
| `GET` | `/api/v1/user/notifications` | query `page`, `limit` | `UserNotificationListResponse` |
| `GET` | `/api/v1/user/notifications/unread-count` | empty | `UnreadCountResponse` |
| `POST` | `/api/v1/user/notifications/{notification_id}/read` | path only | `MarkReadResponse` |
| `POST` | `/api/v1/user/notifications/read-all` | empty | `MarkReadResponse` |

### Key request models

- `SetSecurityEmailRequest`: `{ "email": "user@example.com" }`
- `SetPartnerBalanceCurrencyRequest`: `{ "currency": "RUB" }` или `{ "currency": null }`

### Key response models

`UserProfileResponse` по полям совпадает с `AuthMeResponse`.

`PlanResponse`

- top-level fields:
  - `id`, `name`, `description`, `tag`, `type`, `availability`
  - `traffic_limit`, `device_limit`, `order_index`, `is_active`
  - `allowed_user_ids`, `internal_squads`, `external_squad`
  - `durations`, `created_at`, `updated_at`
- `durations[]`:
  - `id`, `plan_id`, `days`, `prices`
- `prices[]`:
  - `id`, `duration_id`, `gateway_type`, `price`, `original_price`
  - `currency`, `discount_percent`, `discount_source`, `discount`
  - `supported_payment_assets`

`TransactionHistoryResponse`

```json
{
  "transactions": [
    {
      "payment_id": "txn_123",
      "user_telegram_id": 123456789,
      "status": "PENDING",
      "purchase_type": "NEW",
      "channel": "WEB",
      "gateway_type": "YOOKASSA",
      "pricing": {
        "original_amount": 1000.0,
        "discount_percent": 10,
        "final_amount": 900.0
      },
      "currency": "RUB",
      "payment_asset": null,
      "plan": {},
      "renew_subscription_id": null,
      "renew_subscription_ids": null,
      "device_types": null,
      "is_test": false,
      "created_at": "2026-03-08T10:00:00+00:00",
      "updated_at": "2026-03-08T10:00:00+00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 20
}
```

`UserNotificationListResponse`

```json
{
  "notifications": [
    {
      "id": 1,
      "type": "SYSTEM",
      "title": "Title",
      "message": "Body",
      "is_read": false,
      "read_at": null,
      "created_at": "2026-03-08T10:00:00+00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 20,
  "unread": 1
}
```

`UnreadCountResponse`

```json
{
  "unread": 1
}
```

`MarkReadResponse`

```json
{
  "updated": 1
}
```

## Subscription, devices и promocodes

### Routes

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| `GET` | `/api/v1/subscription/list` | empty | `SubscriptionListResponse` |
| `GET` | `/api/v1/subscription/{subscription_id}` | path only | `SubscriptionResponse` |
| `PATCH` | `/api/v1/subscription/{subscription_id}/assignment` | `SubscriptionAssignmentRequest` | `SubscriptionResponse` |
| `DELETE` | `/api/v1/subscription/{subscription_id}` | path only | `{"success": bool, "message": str}` |
| `POST` | `/api/v1/subscription/purchase` | `PurchaseRequest` | `PurchaseResponse` |
| `POST` | `/api/v1/subscription/quote` | `PurchaseQuoteRequest` | `PurchaseQuoteResponse` |
| `POST` | `/api/v1/subscription/{subscription_id}/renew` | `PurchaseRequest` | `PurchaseResponse` |
| `GET` | `/api/v1/subscription/trial/eligibility` | empty | `TrialEligibilityResponse` |
| `POST` | `/api/v1/subscription/trial` | `TrialRequest` or empty | `SubscriptionResponse` |
| `GET` | `/api/v1/devices` | query `subscription_id` | `DeviceListResponse` |
| `POST` | `/api/v1/devices/generate` | `GenerateDeviceRequest` | `GenerateDeviceResponse` |
| `DELETE` | `/api/v1/devices/{hwid}` | query `subscription_id` | `{"success": bool, "message": str}` |
| `POST` | `/api/v1/promocode/activate` | `PromocodeActivateRequest` | `PromocodeActivateResponse` |
| `GET` | `/api/v1/promocode/activations` | query `page`, `limit` | `PromocodeActivationHistoryResponse` |

### Key request models

`SubscriptionAssignmentRequest`

```json
{
  "plan_id": 1,
  "device_type": "IOS"
}
```

`PurchaseRequest` / `PurchaseQuoteRequest`

```json
{
  "purchase_type": "NEW",
  "payment_source": "EXTERNAL",
  "channel": "WEB",
  "plan_id": 1,
  "duration_days": 30,
  "device_type": "IOS",
  "gateway_type": "YOOKASSA",
  "renew_subscription_id": null,
  "renew_subscription_ids": null,
  "device_types": null,
  "quantity": 1,
  "promocode": null,
  "payment_asset": null,
  "success_redirect_url": null,
  "fail_redirect_url": null
}
```

`TrialRequest`

```json
{
  "plan_id": 1
}
```

`GenerateDeviceRequest`

```json
{
  "subscription_id": 1,
  "device_type": "IOS"
}
```

`PromocodeActivateRequest`

```json
{
  "code": "WELCOME",
  "subscription_id": 1,
  "create_new": false
}
```

### Key response models

`SubscriptionResponse`

```json
{
  "id": 1,
  "user_remna_id": "00000000-0000-0000-0000-000000000000",
  "user_telegram_id": 123456789,
  "status": "ACTIVE",
  "is_trial": false,
  "traffic_limit": 0,
  "traffic_used": 0,
  "device_limit": 3,
  "devices_count": 1,
  "internal_squads": [],
  "external_squad": null,
  "expire_at": "2026-04-08T10:00:00+00:00",
  "url": "https://...",
  "device_type": "IOS",
  "plan": {},
  "created_at": "2026-03-08T10:00:00+00:00",
  "updated_at": "2026-03-08T10:00:00+00:00"
}
```

`SubscriptionListResponse`

```json
{
  "subscriptions": []
}
```

`PurchaseResponse`

```json
{
  "transaction_id": "txn_123",
  "payment_url": "https://gateway.example/pay",
  "url": null,
  "status": "PENDING",
  "message": "Payment created"
}
```

`PurchaseQuoteResponse`

```json
{
  "price": 900.0,
  "original_price": 1000.0,
  "currency": "RUB",
  "settlement_price": 900.0,
  "settlement_original_price": 1000.0,
  "settlement_currency": "RUB",
  "discount_percent": 10,
  "discount_source": "personal_discount",
  "payment_asset": null,
  "quote_source": "catalog",
  "quote_expires_at": "2026-03-08T10:10:00+00:00",
  "quote_provider_count": 1
}
```

`TrialEligibilityResponse`

```json
{
  "eligible": true,
  "reason_code": null,
  "reason_message": null,
  "requires_telegram_link": false,
  "trial_plan_id": 1
}
```

`DeviceListResponse`

```json
{
  "devices": [
    {
      "hwid": "device-1",
      "device_type": "IOS",
      "first_connected": null,
      "last_connected": null,
      "country": null,
      "ip": null
    }
  ],
  "subscription_id": 1,
  "device_limit": 3,
  "devices_count": 1
}
```

`GenerateDeviceResponse`

```json
{
  "hwid": "device-1",
  "connection_url": "https://...",
  "device_type": "IOS"
}
```

`PromocodeActivateResponse`

```json
{
  "message": "Promocode activated",
  "reward": {
    "type": "SUBSCRIPTION_DAYS",
    "value": 30
  },
  "next_step": null,
  "available_subscriptions": null
}
```

`PromocodeActivationHistoryResponse`

```json
{
  "activations": [
    {
      "id": 1,
      "code": "WELCOME",
      "reward": {
        "type": "SUBSCRIPTION_DAYS",
        "value": 30
      },
      "target_subscription_id": 1,
      "activated_at": "2026-03-08T10:00:00+00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 20
}
```

## Referral и partner surface

### Routes

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| `GET` | `/api/v1/referral/info` | empty | `ReferralInfoResponse` |
| `GET` | `/api/v1/referral/qr` | query `target` | raw `image/png` |
| `GET` | `/api/v1/referral/list` | query `page`, `limit` | `ReferralListResponse` |
| `GET` | `/api/v1/referral/exchange/options` | empty | `ReferralExchangeOptionsResponse` |
| `POST` | `/api/v1/referral/exchange/execute` | `ReferralExchangeExecuteRequest` | `ReferralExchangeExecuteResponse` |
| `GET` | `/api/v1/referral/about` | empty | `ReferralAboutResponse` |
| `GET` | `/api/v1/partner/info` | empty | `PartnerInfoResponse` |
| `GET` | `/api/v1/partner/referrals` | query `page`, `limit` | `PartnerReferralsListResponse` |
| `GET` | `/api/v1/partner/earnings` | query `page`, `limit` | `PartnerEarningsListResponse` |
| `POST` | `/api/v1/partner/withdraw` | `PartnerWithdrawalRequest` | `PartnerWithdrawalResponse` |
| `GET` | `/api/v1/partner/withdrawals` | empty | `PartnerWithdrawalsListResponse` |

### Key request models

`ReferralExchangeExecuteRequest`

```json
{
  "exchange_type": "SUBSCRIPTION_DAYS",
  "subscription_id": 1,
  "gift_plan_id": null
}
```

`PartnerWithdrawalRequest`

```json
{
  "amount": 1000.00,
  "method": "SBP",
  "requisites": "phone or wallet"
}
```

### Key response models

`ReferralInfoResponse`

```json
{
  "referral_count": 10,
  "qualified_referral_count": 4,
  "reward_count": 3,
  "referral_link": "https://t.me/...",
  "telegram_referral_link": "https://t.me/...",
  "web_referral_link": "https://example.com/webapp/?ref=...",
  "referral_code": "abcd1234",
  "points": 100
}
```

`ReferralListResponse`

- `referrals[]` fields:
  - `telegram_id`, `username`, `name`, `level`
  - `invited_at`, `joined_at`, `invite_source`
  - `is_active`, `is_qualified`, `qualified_at`, `qualified_purchase_channel`
  - `rewards_issued`, `rewards_earned`
  - `events[]` with `type`, `at`, `source`, `channel`
- pagination fields: `total`, `page`, `limit`

`ReferralExchangeOptionsResponse`

```json
{
  "exchange_enabled": true,
  "points_balance": 100,
  "types": [
    {
      "type": "SUBSCRIPTION_DAYS",
      "enabled": true,
      "available": true,
      "points_cost": 10,
      "min_points": 10,
      "max_points": 100,
      "computed_value": 30,
      "requires_subscription": true,
      "gift_plan_id": null,
      "gift_duration_days": null,
      "max_discount_percent": null,
      "max_traffic_gb": null
    }
  ],
  "gift_plans": []
}
```

`ReferralExchangeExecuteResponse`

```json
{
  "success": true,
  "exchange_type": "SUBSCRIPTION_DAYS",
  "points_spent": 10,
  "points_balance_after": 90,
  "result": {
    "days_added": 30,
    "traffic_gb_added": null,
    "discount_percent_added": null,
    "gift_promocode": null,
    "gift_plan_name": null,
    "gift_duration_days": null
  }
}
```

`ReferralAboutResponse`

```json
{
  "title": "Referral program",
  "description": "Description",
  "how_it_works": ["step 1", "step 2"],
  "rewards": {
    "invite": "..."
  },
  "faq": [
    {
      "question": "...",
      "answer": "..."
    }
  ]
}
```

`PartnerInfoResponse`

- `is_partner`, `is_active`, `can_withdraw`
- `apply_support_url`
- `effective_currency`
- `min_withdrawal_rub`, `min_withdrawal_display`
- `balance`, `balance_display`
- `total_earned`, `total_earned_display`
- `total_withdrawn`, `total_withdrawn_display`
- `referrals_count`, `level2_referrals_count`, `level3_referrals_count`
- `referral_link`, `telegram_referral_link`, `web_referral_link`
- `use_global_settings`, `effective_reward_type`, `effective_accrual_strategy`
- `level_settings[]`:
  - `level`, `referrals_count`, `earned_amount`
  - `global_percent`, `individual_percent`, `individual_fixed_amount`
  - `effective_percent`, `effective_fixed_amount`, `uses_global_value`

`PartnerReferralsListResponse`

- `referrals[]` fields:
  - `telegram_id`, `username`, `name`, `level`
  - `joined_at`, `invite_source`
  - `is_active`, `is_paid`, `first_paid_at`
  - `total_paid_amount`, `total_earned`
  - `total_paid_amount_display`, `total_earned_display`, `display_currency`
- pagination fields: `total`, `page`, `limit`

`PartnerEarningsListResponse`

- `earnings[]` fields:
  - `id`, `referral_telegram_id`, `referral_username`, `level`
  - `payment_amount`, `payment_amount_display`
  - `percent`, `earned_amount`, `earned_amount_display`
  - `display_currency`, `created_at`
- pagination fields: `total`, `page`, `limit`

`PartnerWithdrawalResponse`

```json
{
  "id": 1,
  "amount": 100000,
  "display_amount": 1000.0,
  "display_currency": "RUB",
  "requested_amount": 1000.0,
  "requested_currency": "RUB",
  "quote_rate": 1.0,
  "quote_source": "manual",
  "status": "PENDING",
  "method": "SBP",
  "requisites": "phone or wallet",
  "admin_comment": null,
  "created_at": "2026-03-08T10:00:00+00:00",
  "updated_at": "2026-03-08T10:00:00+00:00"
}
```

`PartnerWithdrawalsListResponse`

```json
{
  "withdrawals": []
}
```

## Webhooks и non-JSON surface

| Method | Path | Contract |
| --- | --- | --- |
| `POST` | `/telegram` | Telegram webhook route, ожидает header `X-Telegram-Bot-Api-Secret-Token`, body `Update`, возвращает пустой `200` JSON response |
| `GET` | `/api/v1/payments/yoomoney/redirect` | HTML auto-submit form; принимает query `token` |
| `POST` | `/api/v1/payments/{gateway_type}` | raw gateway webhook; response строится конкретным gateway adapter |
| `POST` | `/api/v1/remnawave` | raw Remnawave webhook; валидация подписи через `REMNAWAVE_WEBHOOK_SECRET`; ответ `200` или `401` |
| `GET` | `/api/v1/referral/qr` | raw `image/png` |

## Что не следует предполагать

- Не предполагайте bearer-only auth как основной сценарий для web UI.
- Не предполагайте единый response envelope.
- Не предполагайте, что `WEB_APP_JWT_EXPIRY`, `WEB_APP_JWT_REFRESH_ENABLED` и `WEB_APP_API_SECRET_TOKEN` уже управляют всеми auth flows: часть этих полей пока только конфигурируется.
- Не предполагайте JSON body для `referral/qr`, `payments/yoomoney/redirect`, payment webhooks и Telegram webhook.
