# Remnawave Compatibility Contract

This repo treats `src/services/remnawave.py` as the application boundary for Remnawave panel access.
Bot dialogs, Taskiq jobs, and user-facing orchestration code should call `RemnawaveService` methods instead
of reaching into `RemnawaveSDK` controllers directly.

## Current SDK Contract

| Surface | AltShop boundary | SDK expectation | Notes |
| --- | --- | --- | --- |
| Panel health and stats | `get_stats_safe()` / `try_connection()` | `remnawave >= 2.3.2` | Used at startup and in dashboard status views. |
| Internal squads | `get_internal_squads()` | `GetAllInternalSquadsResponseDto` | Consumed by plan/user/importer flows. |
| Hosts / nodes / inbounds | `get_hosts()`, `get_nodes()`, `get_inbounds()` | typed DTO responses | Used by the admin dashboard only through the service boundary. |
| User create / update / enable / disable / delete | `create_user()`, `updated_user()`, `set_user_enabled()`, `delete_user()`, `delete_user_by_uuid()` | current `/users` controller contract | Multi-subscription flows depend on these methods, not raw SDK calls. |
| User lookup and full panel sync | `get_user()`, `get_users_by_telegram_id()`, `get_all_users()` | `UserResponseDto` / `TelegramUserResponseDto` | Used by sync, importer, and runtime refresh flows. |
| Device fetch / delete | `get_devices_by_subscription_uuid()`, `delete_device_by_subscription_uuid()` | HWID controller DTOs | Webhook-driven device sync also updates local device type through this boundary. |
| External squads | `get_external_squads_safe()` | SDK first, raw HTTP fallback second | Keep the fallback until the SDK DTO accepts panel payloads with missing `subscriptionSettings.*` fields. |

## Known Exception

`src/services/backup.py` still keeps one direct SDK lookup for restore-time panel recovery. That code is
an infrastructure-only exception because `BackupService` is app-scoped and does not participate in bot or
Taskiq request orchestration. If backup/restore grows more panel touchpoints, move them into a dedicated
app-scoped Remnawave adapter instead of adding more direct SDK calls there.
