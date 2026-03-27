# Remnawave Compatibility Contract

This repo treats `src/services/remnawave.py` as the application boundary for Remnawave panel access.
Bot dialogs, Taskiq jobs, and user-facing orchestration code should call `RemnawaveService` methods instead
of reaching into `RemnawaveSDK` controllers directly.

## Target Version Decision

AltShop currently holds the Python SDK on `remnawave 2.4.4`.

- Official SDK contract table on PyPI publishes `2.4.4 -> panel >=2.4.0`.
- Official SDK contract table also publishes `2.6.3 -> panel >=2.6.3`.
- AltShop's Remnawave-focused test slice passes when `2.6.3` is shadowed into `PYTHONPATH`,
  so the repo code is not the blocker by itself.
- We still do **not** auto-adopt `2.6.3` in the manifest until the project intentionally moves
  its supported panel contract to `>=2.6.3` and re-verifies that against a live panel.

## Current SDK Contract

| Surface | AltShop boundary | SDK expectation | Notes |
| --- | --- | --- | --- |
| Panel health and stats | `get_stats_safe()` / `try_connection()` | `remnawave 2.4.4` | Used at startup and in dashboard status views. |
| Internal squads | `get_internal_squads()` | `GetAllInternalSquadsResponseDto` | Consumed by plan/user/importer flows. |
| Hosts / nodes / inbounds | `get_hosts()`, `get_nodes()`, `get_inbounds()` | typed DTO responses | Used by the admin dashboard only through the service boundary. |
| User create / update / enable / disable / delete | `create_user()`, `updated_user()`, `set_user_enabled()`, `delete_user()`, `delete_user_by_uuid()` | current `/users` controller contract | Multi-subscription flows depend on these methods, not raw SDK calls. |
| User lookup and full panel sync | `get_user()`, `get_users_by_telegram_id()`, `get_all_users()` | `UserResponseDto` / `TelegramUserResponseDto` | Used by sync, importer, and runtime refresh flows. |
| Device fetch / delete | `get_devices_by_subscription_uuid()`, `delete_device_by_subscription_uuid()` | HWID controller DTOs | Webhook-driven device sync also updates local device type through this boundary. |
| External squads | `get_external_squads_safe()` | SDK first, raw HTTP fallback second | Keep the fallback on the pinned `2.4.4` line because `subscriptionSettings.*` is still required there. |

## Known Drift To Watch

- Official webhook docs include a top-level `scope` field since panel `2.5.0`, but the Python SDK
  webhook payload model still routes by `event` prefix. AltShop intentionally follows the event-prefix
  contract and tolerates the extra field.
- Official SDK `2.6.3` relaxes the strict `subscriptionSettings.*` fields that currently force the
  `/external-squads` raw fallback, but adopting it also raises the official panel floor to `>=2.6.3`.
- The repo therefore keeps the fallback and the `2.4.4` SDK hold together until a deliberate panel uplift
  is scheduled.

## Known Exception

`src/services/backup.py` still keeps one direct SDK lookup for restore-time panel recovery. That code is
an infrastructure-only exception because `BackupService` is app-scoped and does not participate in bot or
Taskiq request orchestration. If backup/restore grows more panel touchpoints, move them into a dedicated
app-scoped Remnawave adapter instead of adding more direct SDK calls there.
