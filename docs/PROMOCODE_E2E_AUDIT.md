> [!WARNING]
> Исторический документ. Этот файл не входит в канонический комплект документации и не переаудировался в текущем проходе. Актуальная точка входа: [docs/README.md](README.md)

# Promocode E2E Audit (Web + API + Configurator)

## Scope of this iteration
- Activation branching for `SUBSCRIPTION`, `DURATION`, `TRAFFIC`, `DEVICES`.
- Case-insensitive code handling (`trim + uppercase`).
- Plan filter support via `allowed_plan_ids`.
- Configurator support for:
  - plan filter selection,
  - ALLOWED users search and selection,
  - separate activation limit setting.

Out of scope (kept as-is): `DURATION/TRAFFIC/DEVICES` do **not** create a new subscription when user has no eligible active subscriptions.

## API Decision Matrix

| Reward type | Active subscriptions | Eligible by `allowed_plan_ids` | Request params | Expected result |
|---|---:|---:|---|---|
| `SUBSCRIPTION` | 0 | 0 | none | `next_step="CREATE_NEW"` |
| `SUBSCRIPTION` | >0 | 0 | none | `next_step="CREATE_NEW"` |
| `SUBSCRIPTION` | >0 | 1 | none | immediate success |
| `SUBSCRIPTION` | >0 | >1 | none | `next_step="SELECT_SUBSCRIPTION"` with filtered `available_subscriptions` |
| `SUBSCRIPTION` | any | n/a | `create_new=true` | immediate success (create new) |
| `SUBSCRIPTION` | any | target ineligible | `subscription_id=X` | `400 Subscription plan is not eligible for this promocode` |
| `DURATION/TRAFFIC/DEVICES` | 0 | 0 | none | `400 No eligible active subscriptions to apply this promocode` |
| `DURATION/TRAFFIC/DEVICES` | >0 | 0 | none | `400 No eligible active subscriptions to apply this promocode` |
| `DURATION/TRAFFIC/DEVICES` | >0 | 1 | none | immediate success |
| `DURATION/TRAFFIC/DEVICES` | >0 | >1 | none | `next_step="SELECT_SUBSCRIPTION"` with filtered `available_subscriptions` |
| `DURATION/TRAFFIC/DEVICES` | any | target ineligible | `subscription_id=X` | `400 Subscription plan is not eligible for this promocode` |

Rules:
- `allowed_plan_ids=[]` means no plan filter (all plans are eligible).
- `code` is normalized server-side before lookup (`trim().toUpperCase()`).

## Validation Checklist

- [x] API case-insensitive activation.
- [x] API plan-filter branching for `SUBSCRIPTION`.
- [x] API plan-filter rejection for `DURATION/TRAFFIC/DEVICES`.
- [x] Web normalization in both activation screens.
- [x] Configurator states/UI for plan filter and ALLOWED users.
- [x] Translation keys for new configurator blocks.

Automated tests:
- `tests/test_promocode_activate_plan_filter.py` (5 scenarios)

Manual checks still recommended:
- Bot dialog flow UX for ALLOWED users search/remove in real Telegram client.
- DB migration application on staging (`0035_add_promocode_allowed_plan_ids`).
