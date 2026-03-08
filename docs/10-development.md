# AltShop Development

Проверено по коду: `2026-03-08`

## Источники истины

- `pyproject.toml`
- `Makefile`
- `src/__main__.py`
- `src/infrastructure/database/alembic.ini`
- `web-app/package.json`
- `web-app/vite.config.ts`

## Базовый toolchain

- Python: `>=3.12`
- Backend package manager: `uv`
- Frontend runtime/build: `Node.js` + `npm`
- Frontend dev server: `Vite 7`
- Backend QA: `ruff`, `pytest`, `mypy`

## Рекомендуемый локальный setup

### 1. Подготовить backend окружение

```bash
uv sync --locked --group dev
```

Если нужен shell activation:

```bash
.venv\Scripts\activate
```

или на Unix:

```bash
source .venv/bin/activate
```

### 2. Подготовить `.env`

```bash
cp .env.example .env
```

`make setup-env` существует, но в текущем виде использует `sed -i ''`, то есть ориентирован на BSD/macOS shell. На Linux и Windows этот target не является переносимым без адаптации.

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

Самый простой вариант для локальной разработки:

```bash
docker compose up -d altshop-db altshop-redis
```

Если вы используете внешние PostgreSQL/Redis, достаточно настроить `DATABASE_*` и `REDIS_*` в `.env`.

### 4. Применить миграции

```bash
uv run alembic -c src/infrastructure/database/alembic.ini upgrade head
```

или через `make`:

```bash
make migrate
```

### 5. Запустить backend

Наиболее удобный dev-вариант, совпадающий с frontend proxy:

```bash
uv run uvicorn src.__main__:application --factory --reload --host 0.0.0.0 --port 5000
```

Текущий `python -m src` тоже рабочий, но имеет другой bind по умолчанию:

- host: `0.0.0.0`
- port: `8000`

Поэтому для совместимости с `web-app/vite.config.ts` предпочтительнее явный запуск на `5000`.

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

## Backend QA workflow

Рабочие команды из `Makefile`:

| Command | Что делает |
| --- | --- |
| `make backend-sync` | `uv sync --locked --group dev` |
| `make backend-lint` | `ruff check src tests` |
| `make backend-test` | `pytest -q` |
| `make backend-typecheck` | `mypy src` |
| `make backend-check` | lint + tests + typecheck |
| `make backend-audit` | `backend-check` + legacy report script |
| `make backend-legacy-report` | `python scripts/backend_audit_report.py` |
| `make migration` | `alembic revision --autogenerate` |
| `make migrate` | `alembic upgrade head` |
| `make downgrade` | downgrade на `-1` или на `rev=<revision>` |

Те же команды без `make`:

```bash
uv run python -m ruff check src tests
uv run python -m pytest -q
uv run python -m mypy src
```

## Frontend workflow

Актуальные scripts в `web-app/package.json`:

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
| `npm run generate:api:download` | скачать `openapi.json` и затем сгенерировать client |

Практический локальный цикл:

1. Запустить backend на `localhost:5000`
2. В `web-app/` запустить `npm run dev`
3. Для frontend проверки использовать `npm run lint` и `npm run type-check`
4. Для production smoke использовать `npm run build`

## Full-stack локальный smoke

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

## Цели Makefile, которые сейчас не являются актуальными

В `Makefile` есть цели:

- `make run-local`
- `make run-prod`

Но они ссылаются на файлы:

- `docker-compose.local.yml`
- `docker-compose.prod.external.yml`

Эти compose files отсутствуют в текущем репозитории, поэтому такие цели нельзя считать рабочим источником истины.

## Полезные замечания

- Для web auth и фронтенда не забудьте добавить `APP_ORIGINS`, хотя этой переменной нет в `.env.example`.
- Для локального frontend dev backend удобнее держать на порту `5000`, потому что именно туда смотрит Vite proxy.
- `WEB_APP_JWT_SECRET` нужен уже на этапе локального auth-flow, иначе `/api/v1/auth/*` не сможет выдавать и проверять JWT cookies.
- Если вы редактируете assets или переводы, `uvicorn --reload` подхватит код и FTL изменения, а production container использует `docker-entrypoint.sh` для инициализации assets volume.
