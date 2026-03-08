# AltShop Database

Проверено по коду: `2026-03-08`

## Сводка

- SQLAlchemy async models расположены в `src/infrastructure/database/models/sql`
- Сейчас в коде определены 23 SQL-таблицы
- Миграции ведутся Alembic из `src/infrastructure/database/migrations/versions`
- Всего ревизий: 45 (`0001` ... `0045`)

## Таблицы

| Таблица | Модель | Назначение | Основные связи |
| --- | --- | --- | --- |
| `users` | `user.py` | основная пользовательская сущность | связана с subscriptions, transactions, referrals, web account |
| `subscriptions` | `subscription.py` | VPN-подписки пользователя | относится к `users`, ссылается на snapshot плана |
| `plans` | `plan.py` | каталог планов | родитель для `plan_durations` |
| `plan_durations` | `plan.py` | длительности плана | родитель для `plan_prices` |
| `plan_prices` | `plan.py` | цены по gateway/duration | относится к `plan_durations` |
| `transactions` | `transaction.py` | платежные транзакции и renew context | относится к `users`, хранит pricing/plan snapshots |
| `payment_gateways` | `payment_gateway.py` | runtime-конфигурация gateway adapters | используется `PaymentGatewayService` |
| `promocodes` | `promocode.py` | определение промокодов и правил применения | связана с `promocode_activations` |
| `promocode_activations` | `promocode.py` | история применений промокодов | относится к `users`, может ссылаться на subscription snapshot |
| `referrals` | `referral.py` | связи referrer -> invited user | относится к `users` |
| `referral_rewards` | `referral.py` | начисленные referral rewards | относится к referral events/users |
| `partners` | `partner.py` | партнёрский профиль пользователя | относится к `users` |
| `partner_referrals` | `partner.py` | реферальные связи для partner program | относится к `partners`/users |
| `partner_transactions` | `partner.py` | начисления партнёру | относится к `partners` |
| `partner_withdrawals` | `partner.py` | заявки на вывод | относится к `partners` |
| `settings` | `settings.py` | глобальные настройки, branding, feature flags | singleton-like settings storage |
| `broadcasts` | `broadcast.py` | сущности рассылок | родитель для `broadcast_messages` |
| `broadcast_messages` | `broadcast.py` | статусы сообщений в рассылке | относится к `broadcasts` |
| `web_accounts` | `web_account.py` | username/password/email слой поверх `users` | относится к `users`, связан с `auth_challenges` |
| `auth_challenges` | `web_account.py` | временные коды и токены для verify/reset/link flows | относится к `web_accounts` |
| `user_notification_events` | `user_notification_event.py` | persistable user-facing notification events | относится к `users` |
| `web_analytics_events` | `web_analytics_event.py` | события frontend и auth funnel | опционально относится к `users` |
| `payment_webhook_events` | `payment_webhook_event.py` | inbox/deduplication запись payment webhooks | ключи: gateway, payment_id, payload_hash |

## Что важно по текущей схеме

### Пользователи и web auth

Текущий web auth контур хранится не в `users`, а в отдельных таблицах:

- `web_accounts`
  - username
  - password hash
  - email
  - email verification flags
  - `token_version` для invalidation refresh/access tokens
- `auth_challenges`
  - code/token
  - challenge type
  - TTL/attempt counters
  - используется для email verify, password reset и Telegram link confirm

### Подписки и покупки

- `transactions` хранит purchase context, включая `purchase_type`, `channel`, `payment_source`, renew IDs, settlement данные
- `payment_webhook_events` даёт durable record для deduplication входящих webhook deliveries
- `promocode_activations` хранит snapshot применения, а не только факт использования

### Referral и partner

- referral program живёт в `referrals` и `referral_rewards`
- partner program использует отдельные `partners`, `partner_referrals`, `partner_transactions`, `partner_withdrawals`
- это две связанные, но не одинаковые подсистемы

### Settings и branding

Глобальные runtime flags находятся в `settings`, включая:

- `access_mode`
- rules/channel requirements
- branding settings
- referral/partner settings
- notification settings
- multi-subscription settings

## Модельные файлы

| Файл | Какие таблицы содержит |
| --- | --- |
| `user.py` | `users` |
| `subscription.py` | `subscriptions` |
| `plan.py` | `plans`, `plan_durations`, `plan_prices` |
| `transaction.py` | `transactions` |
| `payment_gateway.py` | `payment_gateways` |
| `promocode.py` | `promocodes`, `promocode_activations` |
| `referral.py` | `referrals`, `referral_rewards` |
| `partner.py` | `partners`, `partner_transactions`, `partner_withdrawals`, `partner_referrals` |
| `settings.py` | `settings` |
| `broadcast.py` | `broadcasts`, `broadcast_messages` |
| `web_account.py` | `web_accounts`, `auth_challenges` |
| `user_notification_event.py` | `user_notification_events` |
| `web_analytics_event.py` | `web_analytics_events` |
| `payment_webhook_event.py` | `payment_webhook_events` |

## Alembic migrations

### Полный список ревизий

```text
0001_create_enums
0002_create_base_tables
0003_create_users_and_subscriptions
0004_create_plan_durations
0005_create_plan_prices
0006_create_transactions
0007_create_promocode_activations
0008_create_broadcasts
0009_fix_access_mode
0010_add_channel_id
0011_extend_plans
0012_subscription_external_squad
0013_create_referrals
0014_add_subscription_count
0015_extend_promocodes
0016_add_device_type
0017_fix_enums
0018_add_renew_subscription_id
0019_add_renew_subscription_ids
0020_add_device_types_to_transactions
0021_add_is_rules_accepted
0022_add_referral_eligible_plans
0023_add_currency_and_gateway_types
0024_create_partner_tables
0025_add_partner_settings_column
0026_add_partner_individual_settings
0027_add_multi_subscription_settings
0028_add_auth_fields
0029_repair_auth_fields_if_missing
0030_add_web_accounts_and_auth_challenges
0031_add_promocode_activation_snapshots
0032_add_other_device_type
0033_add_referral_identity_and_exchange_channels
0034_add_branding_settings
0035_add_promocode_allowed_plan_ids
0036_add_web_password_reset_flags
0037_create_user_notification_events
0038_create_web_analytics_events
0039_create_payment_webhook_events
0040_drop_legacy_user_auth_columns
0041_add_web_account_credentials_bootstrapped_at
0042_add_more_payment_gateway_types
0043_add_crypto_payment_assets
0044_add_tbank_partner_balance_and_market_currencies
0045_drop_plan_subscription_count
```

### Ключевые этапы эволюции схемы

| Диапазон | Что изменилось |
| --- | --- |
| `0001-0008` | базовые enums, users/subscriptions, plan pricing, transactions, promocodes, broadcasts |
| `0009-0017` | access mode fixes, channel rules, plan/extensions, referrals, device type, enum fixes |
| `0018-0027` | multi-renew, rules acceptance, referral eligible plans, currencies/gateways, partner tables/settings, multi-subscription |
| `0028-0036` | web auth fields, `web_accounts`, `auth_challenges`, branding, password reset flags, plan filters for promocodes |
| `0037-0045` | notification events, analytics events, payment webhook inbox, cleanup legacy auth fields, новые gateway/currency additions |

## Что поменялось относительно старых документов

- Схема больше не ограничивается старыми user/subscription/payment таблицами.
- Web auth теперь отдельный persistence layer.
- Payment webhooks имеют свою durable таблицу.
- Referral и partner логика существенно расширены.
- Число ревизий выросло до 45, поэтому устаревшие документы с диапазоном `0001-0027` больше не отражают реальность.
