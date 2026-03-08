> [!WARNING]
> Исторический документ. Этот файл не входит в канонический комплект документации и не переаудировался в текущем проходе. Актуальная точка входа: [docs/README.md](README.md)

# Wave 3 Lint Burn-Down (2026-03-06)

## Baseline
- Scope: `ruff check src tests --select E501,C901`
- Before Wave 3: `146` issues (`125 E501`, `21 C901`)

## Result
- Current result: `0` issues for `E501/C901` in `src` and `tests`.
- Current gate:
  - `python -m ruff check src tests`
  - `python -m ruff check src tests --select C901 --ignore-noqa --line-length 100`

## Applied Changes
- Removed global ignores for `E501` and `C901`.
- Kept `line-length = 100`.
- Removed non-migration `E501` `per-file-ignores`.
- Removed runtime and bot `# noqa: C901` suppressions from `src`.
- Promoted CI strict complexity gate to full backend scope:
  - `uv run python -m ruff check src tests --select C901 --ignore-noqa --line-length 100`

## Remaining Exceptions
- Historical migrations keep the only remaining `E501` exceptions:
  - `src/infrastructure/database/migrations/versions/0023_add_currency_and_gateway_types.py`
  - `src/infrastructure/database/migrations/versions/0025_add_partner_settings_column.py`
  - `src/infrastructure/database/migrations/versions/0026_add_partner_individual_settings.py`
  - `src/infrastructure/database/migrations/versions/0034_add_branding_settings.py`

## Closure
- Wave 3 closed on `2026-03-06`.
- Further cleanup is now optional maintenance, not a blocker for backend quality gates.
