#!/usr/bin/env bash
# Open every portal page as its demo role at 360px and 1440px in Chromium.
# Playwright is not a project dependency: uv adds it for this run only.
# First time on a machine: uv run --with playwright playwright install chromium
# Options (env): WALK_ONLY=<route text>, WALK_SHOTS=<dir>, WALK_AXE_FAIL=1.
set -euo pipefail
cd "$(dirname "$0")/.."
export DJANGO_ALLOW_ASYNC_UNSAFE=1  # Playwright's sync API inside the test
export SEED_DEMO_PASSWORD="${SEED_DEMO_PASSWORD:-browser-walk-only-1}"
export TEST_DB_NAME="${TEST_DB_NAME:-lms_test_walk}"
# --create-db: the walk empties its tables at the end (a transaction test).
exec uv run --with playwright pytest browser_walk -q -s -p no:cacheprovider \
  --create-db "$@"
