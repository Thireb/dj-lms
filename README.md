# dj-lms

Multi-institute learning management system (Django).

## Local setup

```bash
cp .env.example .env
uv sync --group dev
uv run python manage.py migrate
```

Without `DATABASE_URL`, development uses SQLite (`db.sqlite3`).

## Frontend CSS (Tailwind standalone)

Tailwind is built with the **standalone CLI** (no Node.js). Version is pinned in `static/css/TAILWIND_VERSION` (currently 4.1.4).

```bash
chmod +x scripts/build-app-css.sh
./scripts/build-app-css.sh
```

This writes `static/css/app.css` from `static/css/src/input.css`. The compiled file is gitignored; run the script after clone or when CSS sources change.

HTMX, Alpine.js, Chart.js, and Font Awesome Free are vendored under `static/vendor/` (see `static/vendor/VENDOR_VERSIONS.md`).

## Quality checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Settings

- Development: `config.settings.dev` (default for `manage.py`)
- Tests: `config.settings.test` (default for pytest via `pyproject.toml`)
- Production: `config.settings.prod` (`DJANGO_SETTINGS_MODULE=config.settings.prod`)
