# Event Coverage Matrix

Date: 2026-04-12

This matrix is derived from current source code send-points and templates.

| Business action | Bot | Web | Mini App | Current state | Primary event key / evidence |
|---|---|---|---|---|---|
| Registration | Yes | Yes | Partial | Exists, payload now enriched | `ntf-event-new-user`, `ntf-event-web-user-registered` |
| Login / auth | No direct operator event | Partial | Partial | Weak / source-specific | `ntf-event-web-user-registered`, `ntf-event-web-account-linked` |
| Purchase | Yes | Yes | Partial | Exists, payload enriched with channel/context | `ntf-event-subscription-new` |
| Renew | Yes | Yes | Partial | Exists, payload enriched with channel/context | `ntf-event-subscription-renew` |
| Upgrade | Yes | Yes | Partial | Exists, payload enriched with channel/context | `ntf-event-subscription-upgrade` |
| Additional purchase | Yes | Yes | Partial | Exists, payload enriched with channel/context | `ntf-event-subscription-additional` |
| Invite / referral attach | Yes | Partial | Partial | Partial, mixed operator visibility | `ntf-event-user-referral-attached`, `ntf-event-partner-referral-registered` |
| Invite-only access denied / accepted | Yes | Missing | Missing | Bot covered in this patch, web/mini app deferred | `ntf-event-access-policy`, `src/services/access.py` |
| Account link / bind | Yes | Yes | Partial | Exists, source-aware payload improved | `ntf-event-web-account-linked`, admin bind handler |
| User-caused backend errors | Yes | Partial | Partial | Generic system error layer enriched | `ntf-event-error`, error middleware, webhook/API send-points |
| Dependency errors | Yes | Yes | Yes | Exists, payload enriched | `ntf-event-error-remnawave`, `ntf-event-error-webhook` |
| Release / update | N/A | N/A | N/A | Exists | `ntf-event-release-update-altshop` |

## Notes

- `Mini App` registration currently flows through Telegram web auth and is differentiated via `WEB_TELEGRAM_WEBAPP`.
- Purchase flows still primarily expose `purchase_channel`; explicit web-vs-mini-app differentiation remains a follow-up.
- Browser-only frontend exception telemetry is intentionally out of scope for this patch.
