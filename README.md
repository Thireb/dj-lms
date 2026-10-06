# dj-lms

Multi-institute learning management system (Django).

## Local run

```bash
cp .env.example .env && uv sync --group dev
./scripts/dev.sh   # Tailwind, migrate, runserver (loads .env via uv)
make test && make lint && make format-check
```

Requires PostgreSQL matching `DATABASE_URL` in `.env` (`lms` user/db in example). Pytest defaults to database `lms_test` (`config.settings.test`). Production: `DJANGO_SETTINGS_MODULE=config.settings.prod`.
