# dj-lms

Multi-institute learning management system (Django).

## Local run

```bash
cp .env.example .env && uv sync --group dev
./scripts/dev.sh   # Tailwind, migrate, runserver (loads .env via uv)
make test && make lint && make format-check
```

Requires PostgreSQL matching `DATABASE_URL` in `.env` (`lms` user/db in example). Background tasks (Celery) run inside the request in dev while `CELERY_ALWAYS_EAGER=true`; to use a worker, run Redis, set it to `false`, and start `uv run celery -A config worker -B -l info`. Beat jobs (the nightly schedule extension and the 5-minute lecture finish) need that worker: with `CELERY_ALWAYS_EAGER=true` and no worker, lectures past their end stay "Scheduled" in dev. Tests never need Redis. Pytest defaults to database `lms_test` (`config.settings.test`). Production: `DJANGO_SETTINGS_MODULE=config.settings.prod`.

After pulling a change that introduces `AUTH_USER_MODEL=accounts.User`, drop and recreate your dev database (or use a new database name), then run `migrate` from scratch. Existing databases that already applied migrations with Django's default user cannot be upgraded in place.
