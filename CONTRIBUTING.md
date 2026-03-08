# Contributing

## Setup

Backend:

```bash
uv sync --locked --group dev
```

Frontend:

```bash
cd web-app
npm ci
```

## Validation before commit

Backend:

```bash
uv run python -m ruff check src tests
uv run python -m pytest -q
uv run python -m mypy src
```

Frontend:

```bash
cd web-app
npm run lint
npm run type-check
npm run build
```

## Documentation contract

If you change runtime behavior, keep the canonical docs in [`docs/`](./docs) in sync with the code. In practice this usually means updating one or more of:

- [`docs/05-api.md`](./docs/05-api.md) for HTTP surface changes
- [`docs/08-configuration.md`](./docs/08-configuration.md) for env/config changes
- [`docs/09-deployment.md`](./docs/09-deployment.md) for Docker, Nginx, or deployment changes
- [`docs/10-development.md`](./docs/10-development.md) for workflow/tooling changes

Historical documents under `docs/archive/` are not the source of truth.

## What must not be committed

- real `.env` files
- TLS private keys and certificate bundles
- local logs
- generated lint/typecheck report dumps
- frontend build output

The repository-level [`.gitignore`](./.gitignore) already covers these cases; keep it that way.
