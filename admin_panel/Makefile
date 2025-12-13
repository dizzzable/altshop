.PHONY: install dev build start stop logs clean help

# Default target
help:
	@echo "Admin Panel - Available commands:"
	@echo ""
	@echo "  make install    - Install dependencies"
	@echo "  make dev        - Start development servers"
	@echo "  make build      - Build for production"
	@echo "  make docker-up  - Start Docker containers"
	@echo "  make docker-down - Stop Docker containers"
	@echo "  make docker-build - Build Docker images"
	@echo "  make docker-logs - View Docker logs"
	@echo "  make clean      - Clean build artifacts"
	@echo ""

# Install dependencies
install:
	pnpm install

# Development
dev:
	pnpm dev

# Build for production
build:
	pnpm build

# Docker commands
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build

docker-rebuild:
	docker-compose up -d --build

docker-logs:
	docker-compose logs -f

docker-logs-backend:
	docker-compose logs -f admin-backend

docker-logs-frontend:
	docker-compose logs -f admin-frontend

# Clean
clean:
	rm -rf node_modules
	rm -rf apps/backend/node_modules
	rm -rf apps/backend/dist
	rm -rf apps/frontend/node_modules
	rm -rf apps/frontend/dist
	rm -rf .turbo

# Database
db-migrate:
	pnpm --filter backend typeorm migration:run

db-generate:
	pnpm --filter backend typeorm migration:generate

# Lint and format
lint:
	pnpm lint

format:
	pnpm format