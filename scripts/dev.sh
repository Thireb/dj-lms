#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE — copy .env.example to .env and adjust values." >&2
  exit 1
fi

uv sync --group dev
"$ROOT/scripts/build-app-css.sh"
uv run --env-file "$ENV_FILE" python manage.py migrate --noinput
exec uv run --env-file "$ENV_FILE" python manage.py runserver "$@"
