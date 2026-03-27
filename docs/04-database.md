# AltShop Database

Last audited against the live repository: `2026-03-26`

## Summary

- SQLAlchemy async models live in `src/infrastructure/database/models/sql/`
- The current schema defines `25` SQL tables
- Migrations are managed with Alembic from `src/infrastructure/database/migrations/versions/`
- The repository currently contains `50` migration revisions: `0001` through `0050`

## Table inventory

| Table | Model file | Purpose |
| --- | --- | --- |
| `users` | `user.py` | Core user identity keyed by Telegram ID |
| `subscriptions` | `subscription.py` | User VPN subscriptions and runtime status |
| `plans` | `plan.py` | Catalog of sellable plans |
| `plan_durations` | `plan.py` | Duration options per plan |
| `plan_prices` | `plan.py` | Gateway and currency specific pricing |
| `transactions` | `transaction.py` | Payment transactions, renewals, and purchase context |
| `payment_gateways` | `payment_gateway.py` | Enabled gateway configuration and credentials |
| `promocodes` | `promocode.py` | Promocode definitions and constraints |
| `promocode_activations` | `promocode.py` | Promocode activation history and snapshots |
| `referral_invites` | `referral.py` | Invite tokens issued by existing users |
| `referrals` | `referral.py` | Referrer to referred-user relationships |
| `referral_rewards` | `referral.py` | Rewards issued through referral events |
| `partners` | `partner.py` | Partner cabinet profile and payout settings |
| `partner_referrals` | `partner.py` | Partner-specific referral relationships |
| `partner_transactions` | `partner.py` | Partner earnings ledger |
| `partner_withdrawals` | `partner.py` | Partner withdrawal requests |
| `settings` | `settings.py` | Global runtime, branding, access, and feature settings |
| `broadcasts` | `broadcast.py` | Broadcast job definitions |
| `broadcast_messages` | `broadcast.py` | Per-user delivery status for broadcasts |
| `web_accounts` | `web_account.py` | Web login, email, and token-version state layered over users |
| `auth_challenges` | `web_account.py` | Email verification, reset, and Telegram-link challenges |
| `user_notification_events` | `user_notification_event.py` | Persisted user-facing notification feed |
| `web_analytics_events` | `web_analytics_event.py` | Frontend and auth funnel telemetry |
| `payment_webhook_events` | `payment_webhook_event.py` | Durable deduplication and processing state for payment webhooks |
| `backup_records` | `backup_record.py` | Metadata for generated backups and Telegram delivery status |

## Persistence zones that matter

### Users and web auth

Web auth is no longer stored only in `users`. The current login flow depends on:

- `web_accounts`
  - username
  - password hash
  - email and verification flags
  - `token_version` for cookie invalidation
  - bootstrap and prompt-snooze state for Telegram linking
- `auth_challenges`
  - one-time codes or tokens
  - challenge type and TTL
  - attempt counters and delivery context

### Purchases, subscriptions, and webhooks

- `transactions` stores purchase type, payment source, pricing snapshot, renew context, and settlement state
- `payment_webhook_events` stores per-gateway deduplication state and enqueue failures
- `subscriptions` stores the active access object, while runtime refresh tasks reconcile data against Remnawave

### Referral and partner systems

- `referral_invites` adds durable invite-token tracking on top of classic referral relationships
- `referrals` and `referral_rewards` model the user referral program
- `partners`, `partner_referrals`, `partner_transactions`, and `partner_withdrawals` model the partner cabinet and payout flow

### Operations and auditability

- `broadcasts` and `broadcast_messages` track outgoing campaigns
- `user_notification_events` gives the web app a persistent notification feed
- `web_analytics_events` captures frontend and auth telemetry
- `backup_records` records backup size, scope, compression, and Telegram delivery metadata

## Model file map

| File | Tables |
| --- | --- |
| `backup_record.py` | `backup_records` |
| `broadcast.py` | `broadcasts`, `broadcast_messages` |
| `partner.py` | `partners`, `partner_referrals`, `partner_transactions`, `partner_withdrawals` |
| `payment_gateway.py` | `payment_gateways` |
| `payment_webhook_event.py` | `payment_webhook_events` |
| `plan.py` | `plans`, `plan_durations`, `plan_prices` |
| `promocode.py` | `promocodes`, `promocode_activations` |
| `referral.py` | `referral_invites`, `referrals`, `referral_rewards` |
| `settings.py` | `settings` |
| `subscription.py` | `subscriptions` |
| `transaction.py` | `transactions` |
| `user.py` | `users` |
| `user_notification_event.py` | `user_notification_events` |
| `web_account.py` | `web_accounts`, `auth_challenges` |
| `web_analytics_event.py` | `web_analytics_events` |

## Alembic revision history

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
0046_add_archived_plan_transitions
0047_add_referral_invites_and_invite_limits
0048_add_invite_mode_started_at
0049_add_bot_menu_settings
0050_create_backup_records
```

## Migration eras

| Range | What changed |
| --- | --- |
| `0001-0008` | Base enums, users, subscriptions, pricing, transactions, promocodes, broadcasts |
| `0009-0017` | Access-mode fixes, channel rules, referrals, device types, enum corrections |
| `0018-0027` | Renew flows, rules acceptance, partner tables, gateway and currency expansion, multi-subscription settings |
| `0028-0036` | Web auth bootstrap, challenge tables, branding, password reset, promocode filters |
| `0037-0045` | Notification events, analytics events, payment webhook inbox, gateway additions, partner balance currencies |
| `0046-0050` | Archived plan transitions, referral invites, invite-mode timestamps, bot-menu settings, backup record audit trail |

## Watch points for future doc updates

- Any new SQLAlchemy model with `__tablename__` must update this file and usually [03-services.md](03-services.md)
- Any new Alembic revision should be appended here with its purpose
- Changes to web auth persistence should update this file together with [05-api.md](05-api.md) and [10-development.md](10-development.md)
