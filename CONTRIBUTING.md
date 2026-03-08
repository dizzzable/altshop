# Contributing

## Scope

This GitHub repository is the public runtime and deployment mirror of AltShop.

- internal backend integration tests stay local and are not published here
- runtime code, deployment files, frontend sources, and canonical docs stay public

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

Public backend checks:

```bash
uv run python -m ruff check src
uv run python -m mypy src
```

Frontend:

```bash
cd web-app
npm run lint
npm run type-check
npm run build
```

If you work in the private internal workspace, you can also run the local backend `pytest` suite there.

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
- internal-only QA files such as `tests/` or temporary `mypy-wave*.ini`

The repository-level [`.gitignore`](./.gitignore) already covers these cases; keep it that way.
