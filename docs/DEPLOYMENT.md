# DEPLOYMENT (Pethost)

Check Pethost's current docs and pricing before you start. Details change.
Docker is for deployment only. Local dev and CI use Postgres through `DATABASE_URL`, no Docker.

> **Ask Pethost first**
> - Is PostgreSQL offered as a managed service?
> - Is Redis offered as a managed service?
> - How are persistent volumes handled, and do they survive redeploys?
> - How are backups handled, and how often?
>
> If PostgreSQL or Redis is not offered, run it as a container in our compose file with a persistent volume.

## 1. Services we need

All run as Docker containers.

- **web:** Django app run by Gunicorn.
- **worker:** Celery worker.
- **beat:** Celery Beat scheduler (one instance only).
- **PostgreSQL:** main database (Pethost service or our container).
- **Redis:** Celery broker and cache (Pethost service or our container).
- **Object storage:** Cloudflare R2 or S3 for uploads, PDFs, recordings. Do not rely on container disk.

## 2. Docker config

- One `Dockerfile` for the app image, shared by web, worker and beat.
- One production compose file in the repo root that defines all services.
- Image build: install dependencies, build Tailwind CSS, collect static files.
- Start command (web): `gunicorn config.wsgi --timeout 120`. Keep the 120 s timeout until the bulk upload runs in Celery (backlog S8): a 15-row import hashes up to 30 passwords in one request.
- Start command (worker): `celery -A config worker -l info`.
- Start command (beat): `celery -A config beat -l info`.
- Run migrations as a one-off step before the new web container starts, not on every web start.

## 3. Environment variables

Listed in `.env.example`. Set real values in Pethost, never in git.

- `DJANGO_SETTINGS_MODULE=config.settings.prod`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `DATABASE_URL`
- `REDIS_URL` (also the shared cache for sign-in limits; needs the `redis` package, not installed yet)
- `TRUSTED_PROXY_IP_HEADER` (for example `HTTP_X_REAL_IP`, a header the proxy always sets)
- `STORAGE_*` (bucket, key, secret, endpoint)
- `EMAIL_*`
- `SENTRY_DSN` (optional)

## 4. Before first deploy

- [ ] Answers to "Ask Pethost first" recorded in this file.
- [ ] `DEBUG=False`, `ALLOWED_HOSTS` set, `CSRF_TRUSTED_ORIGINS` set.
- [ ] HTTPS-only cookies and HSTS enabled.
- [ ] `SECURE_PROXY_SSL_HEADER` set for the TLS proxy, or `SECURE_SSL_REDIRECT` loops (not built yet, backlog S11).
- [ ] WhiteNoise serving static files (not built yet, backlog S12).
- [ ] Health check URL (`/health/`) returns 200 (not built yet, backlog S13).
- [ ] Redis cache on, so sign-in limits are shared by every worker.
- [ ] Seed command creates the first Super Admin.
- [ ] Backups on for the database.

## 5. Plans and pricing

- Real use needs web, worker, beat, database and Redis running all the time.
- Check Pethost's pricing page for current numbers.

## 6. After deploy

- [ ] Log in as Super Admin and create a test institute.
- [ ] Check that a Celery task runs (recurring lecture generation).
- [ ] Check PDF generation and file upload.
- [ ] Set up uptime monitoring and error tracking.
