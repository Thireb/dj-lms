# dj-lms

Multi-institute learning management system (Django).

## Local setup

```bash
cp .env.example .env
uv sync --group dev
uv run python manage.py migrate
```

Without `DATABASE_URL`, development uses SQLite (`db.sqlite3`).

## Quality checks

```bash
uv run pytest
uv run ruff check .
```

## Settings

- Development: `config.settings.dev` (default for `manage.py`)
- Tests: `config.settings.test` (default for pytest via `pyproject.toml`)
- Production: `config.settings.prod` (`DJANGO_SETTINGS_MODULE=config.settings.prod`)
