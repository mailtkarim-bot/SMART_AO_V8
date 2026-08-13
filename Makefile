.PHONY: install lint format test test-domain test-architecture db-up db-down migrate up down

install:
	uv sync --group dev

lint:
	uv run ruff check .

format:
	uv run ruff format .

test:
	uv run pytest

test-domain:
	uv run pytest -m 'schema or domain'

test-architecture:
	uv run pytest -m architecture

db-up:
	docker compose up -d postgres

db-down:
	docker compose down --remove-orphans

migrate:
	uv run alembic -c alembic.ini upgrade head

up:
	docker compose up --build

down:
	docker compose down --remove-orphans
