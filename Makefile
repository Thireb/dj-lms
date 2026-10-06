.PHONY: dev css migrate test lint format

dev:
	./scripts/dev.sh

css:
	./scripts/build-app-css.sh

migrate:
	uv run --env-file .env python manage.py migrate

test:
	uv run pytest

lint:
	uv run ruff check .

format-check:
	uv run ruff format --check .
