.PHONY: up down build logs shell-db seed demo health lint test mcp-build

# ── infra ──────────────────────────────────────────────────────────────────────

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

up-infra:
	docker compose up -d postgres clickhouse redis

# ── dev helpers ────────────────────────────────────────────────────────────────

seed:
	python scripts/seed_demo.py

health:
	python scripts/health_check.py

replay:
	@read -p "Session ID: " sid; python scripts/replay_session.py $$sid

# ── mcp servers ────────────────────────────────────────────────────────────────

mcp-install:
	cd mcp && npm install --workspaces

mcp-build:
	cd mcp && npm run build --workspaces

mcp-dev:
	cd mcp && npm run dev --workspaces

# ── quality ────────────────────────────────────────────────────────────────────

lint:
	ruff check .
	mypy shared/ services/

fmt:
	ruff format .

test:
	pytest -v --cov=shared --cov=services

# ── migrations ─────────────────────────────────────────────────────────────────

migrate:
	alembic upgrade head

migration:
	@read -p "Migration name: " name; alembic revision --autogenerate -m "$$name"
