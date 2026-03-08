# AltShop Development

Проверено по коду: `2026-03-08`

## Источники Истины

- `pyproject.toml`
- `Makefile`
- `src/__main__.py`
- `src/infrastructure/database/alembic.ini`
- `web-app/package.json`
- `web-app/vite.config.ts`

## Важное Ограничение Публичного Репозитория

GitHub-версия AltShop публикуется как публичный runtime и deployment mirror.

- внутренняя backend QA-папка `tests/` здесь не хранится
- локальный приватный workspace может содержать дополнительные тесты и временные mypy-конфиги
- публичные команды и документация ниже не требуют наличия `tests/`

## Базовый Toolchain

- Python: `>=3.12`
- Backend package manager: `uv`
- Frontend runtime и build: `Node.js` + `npm`
- Frontend dev server: `Vite 7`
- Public backend checks: `ruff`, `mypy`
- Private local QA: `pytest`

## Рекомендуемый Локальный Setup

### 1. Подготовить backend окружение

```bash
uv sync --locked --group dev
```

Если нужен shell activation:

```bash
.venv\Scripts\activate
```

Или на Unix:

```bash
source .venv/bin/activate
```

### 2. Подготовить `.env`

```bash
cp .env.example .env
```

Минимум, который обычно нужно заполнить вручную:

- `APP_DOMAIN`
- `APP_CRYPT_KEY`
- `APP_ORIGINS`
- `WEB_APP_JWT_SECRET`
- `DATABASE_PASSWORD`
- `REDIS_PASSWORD`
- `BOT_TOKEN`
- `BOT_SECRET_TOKEN`
- `REMNAWAVE_TOKEN`
- `REMNAWAVE_WEBHOOK_SECRET`

### 3. Поднять PostgreSQL и Valkey

```bash
docker compose up -d altshop-db altshop-redis
```

Если используются внешние PostgreSQL или Redis, достаточно настроить `DATABASE_*` и `REDIS_*` в `.env`.

### 4. Применить миграции

```bash
uv run alembic -c src/infrastructure/database/alembic.ini upgrade head
```

Или через `make`:

```bash
make migrate
```

### 5. Запустить backend

Предпочтительный dev-вариант, совместимый с frontend proxy:

```bash
uv run uvicorn src.__main__:application --factory --reload --host 0.0.0.0 --port 5000
```

`python -m src` тоже рабочий, но по умолчанию использует другой bind.

### 6. Запустить frontend

```bash
cd web-app
npm ci
npm run dev
```

Что важно:

- Vite dev server слушает `3000`
- proxy для `/api` направлен на `http://localhost:5000`
- `base` для production build зафиксирован как `/webapp/`

## Backend Checks

### Публичные проверки

Рабочие команды:

```bash
uv run python -m ruff check src
uv run python -m mypy src
```

Через `make`:

```bash
make backend-lint
make backend-typecheck
make backend-check
```

`make backend-lint` автоматически подхватит `tests/`, только если эта папка существует локально.

### Приватная локальная QA-suite

Если вы работаете во внутреннем workspace и у вас есть локальная `tests/`, дополнительно доступны:

```bash
make backend-test
uv run python -m pytest -q
```

В публичном GitHub mirror `make backend-test` не падает, а просто сообщает, что приватный test suite не опубликован.

## Frontend Workflow

Актуальные scripts из `web-app/package.json`:

| Script | Что делает |
| --- | --- |
| `npm run dev` | локальный Vite dev server |
| `npm run build` | production build |
| `npm run postbuild` | post-processing путей после сборки |
| `npm run preview` | preview собранного frontend |
| `npm run lint` | ESLint |
| `npm run type-check` | `tsc --noEmit` |
| `npm run check:encoding` | проверка mojibake |
| `npm run check:i18n` | проверка parity словарей |
| `npm run generate:api` | генерация TS client из `http://localhost:5000/openapi.json` |
| `npm run generate:api:download` | скачать `openapi.json`, затем сгенерировать client |

Практический локальный цикл:

1. Запустить backend на `localhost:5000`.
2. В `web-app/` запустить `npm run dev`.
3. Для frontend-проверки использовать `npm run lint` и `npm run type-check`.
4. Для production smoke использовать `npm run build`.

## Full-Stack Smoke

Минимальный сценарий без production Nginx:

1. `docker compose up -d altshop-db altshop-redis`
2. `uv run alembic -c src/infrastructure/database/alembic.ini upgrade head`
3. `uv run uvicorn src.__main__:application --factory --reload --host 0.0.0.0 --port 5000`
4. `cd web-app && npm ci && npm run dev`

Если нужен production-like smoke по текущему compose:

```bash
docker compose up --build webapp-build
docker compose up -d --build
```

## Полезные Замечания

- Для web auth и frontend не забудьте добавить `APP_ORIGINS`, хотя этой переменной нет в `.env.example`.
- Для локального frontend dev backend удобнее держать на порту `5000`, потому что туда смотрит Vite proxy.
- `WEB_APP_JWT_SECRET` нужен уже на этапе локального auth-flow.
- `make setup-env` в текущем виде ориентирован на BSD или macOS shell и не является переносимым без адаптации.

## Release Workflow

Для будущих релизов используется semver-подход:

1. обновите версии в `pyproject.toml` и `web-app/package.json`
2. перенесите изменения из `## [Unreleased]` в новый раздел `CHANGELOG.md`
3. создайте annotated tag вида `v1.0.1`
4. отправьте `main` и tag в GitHub

Публичный workflow `.github/workflows/release.yml` автоматически:

- проверит совпадение tag с версиями backend и frontend
- соберет release notes из `CHANGELOG.md`
- опубликует GitHub Release для tag `v*.*.*`
