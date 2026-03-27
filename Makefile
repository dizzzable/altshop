ALEMBIC_INI=src/infrastructure/database/alembic.ini
BACKEND_RUFF_PATHS=src $(if $(wildcard tests),tests,)

.PHONY: backend-sync
backend-sync:
	uv sync --locked --group dev

.PHONY: backend-lint
backend-lint:
	uv run python -m ruff check $(BACKEND_RUFF_PATHS)

.PHONY: backend-test
backend-test:
	@if [ -d tests ]; then \
		uv run python -m pytest -q; \
	else \
		echo "Private backend test suite is not part of the public GitHub mirror."; \
	fi

.PHONY: backend-typecheck
backend-typecheck:
	uv run python -m mypy src

.PHONY: backend-check
backend-check: backend-lint backend-test backend-typecheck

.PHONY: backend-audit
backend-audit: backend-check backend-legacy-report

.PHONY: docs-verify
docs-verify:
	uv run python scripts/verify_operator_docs.py

.PHONY: backend-legacy-report
backend-legacy-report:
	uv run python scripts/backend_audit_report.py

.PHONY: setup-env
setup-env:
	@sed -i '' "s|^APP_CRYPT_KEY=.*|APP_CRYPT_KEY=$(shell openssl rand -base64 32 | tr -d '\n')|" .env
	@sed -i '' "s|^BOT_SECRET_TOKEN=.*|BOT_SECRET_TOKEN=$(shell openssl rand -hex 64 | tr -d '\n')|" .env
	@sed -i '' "s|^DATABASE_PASSWORD=.*|DATABASE_PASSWORD=$(shell openssl rand -hex 24 | tr -d '\n')|" .env
	@sed -i '' "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$(shell openssl rand -hex 24 | tr -d '\n')|" .env
	@echo "Secrets updated. Check your .env file"

.PHONY: migration
migration:
	uv run alembic -c $(ALEMBIC_INI) revision --autogenerate

.PHONY: migrate
migrate:
	uv run alembic -c $(ALEMBIC_INI) upgrade head

.PHONY: downgrade
downgrade:
	@if [ -z "$(rev)" ]; then \
		echo "No revision specified. Downgrading by 1 step."; \
		uv run alembic -c $(ALEMBIC_INI) downgrade -1; \
	else \
		uv run alembic -c $(ALEMBIC_INI) downgrade $(rev); \
	fi

.PHONY: run-local
run-local:
	@docker compose -f docker-compose.yml up --build
	
.PHONY: run-prod
run-prod:
	@docker compose -f docker-compose.prod.yml pull
	@docker compose -f docker-compose.prod.yml up -d
	@docker compose -f docker-compose.prod.yml logs -f

# .PHONY: run-dev
# run-dev:
# 	@docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
# 	@docker compose logs -f

