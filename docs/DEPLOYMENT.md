# DEPLOYMENT (Render)

Check Render's current docs and pricing before you start. Details change.

## 1. Services we need

- **Web service:** Django app run by Gunicorn.
- **Background worker:** Celery worker.
- **Scheduler:** Celery Beat (as its own worker) or Render cron jobs.
- **PostgreSQL:** main database.
- **Key Value (Redis-compatible):** Celery broker and cache.
- **Object storage:** Cloudflare R2 or S3 for uploads, PDFs, recordings. Render's local disk is not permanent unless you attach a disk.

## 2. Render config

- Keep a `render.yaml` blueprint in the repo root that defines all services.
- Build command: install dependencies, collect static files.
- Start command (web): `gunicorn config.wsgi`.
- Start command (worker): `celery -A config worker -l info`.
- Start command (beat): `celery -A config beat -l info`.
- Run migrations as a pre-deploy command, not on every web start.

## 3. Environment variables

Listed in `.env.example`. Set real values in Render, never in git.

- `DJANGO_SETTINGS_MODULE=config.settings.prod`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `DATABASE_URL`
- `REDIS_URL`
- `STORAGE_*` (bucket, key, secret, endpoint)
- `EMAIL_*`
- `SENTRY_DSN` (optional)

## 4. Before first deploy

- [ ] `DEBUG=False`, `ALLOWED_HOSTS` set, `CSRF_TRUSTED_ORIGINS` set.
- [ ] HTTPS-only cookies and HSTS enabled.
- [ ] WhiteNoise serving static files.
- [ ] Health check URL (`/health/`) returns 200.
- [ ] Seed command creates the first Super Admin.
- [ ] Backups on for the database.

## 5. Free vs paid tiers

- Free services may sleep when idle. Fine for a demo, not for scheduled jobs or real institutes.
- Real use needs at least paid web, worker, and database.
- Check Render's pricing page for current numbers.

## 6. Using Render's MCP server

- Render offers an MCP server so an AI agent can inspect and manage services.
- Set it up from Render's own docs and add it to Cursor's MCP settings.
- Use a Render API key with the smallest access that works. Never commit it.
- Good first uses for the agent: read logs, check deploy status, list env vars (names only), trigger a deploy.
- Do not let the agent delete services or databases without your approval.

## 7. After deploy

- [ ] Log in as Super Admin and create a test institute.
- [ ] Check that a Celery task runs (recurring lecture generation).
- [ ] Check PDF generation and file upload.
- [ ] Set up uptime monitoring and error tracking.
