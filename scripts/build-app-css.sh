#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION_FILE="$ROOT/static/css/TAILWIND_VERSION"
BIN="$ROOT/scripts/tailwindcss"
INPUT="$ROOT/static/css/src/input.css"
OUTPUT="$ROOT/static/css/app.css"

if [[ ! -f "$VERSION_FILE" ]]; then
  echo "Missing $VERSION_FILE" >&2
  exit 1
fi

VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"

if [[ ! -x "$BIN" ]]; then
  echo "Downloading Tailwind CSS standalone v${VERSION}..."
  curl -fsSL \
    "https://github.com/tailwindlabs/tailwindcss/releases/download/v${VERSION}/tailwindcss-linux-x64" \
    -o "$BIN"
  chmod +x "$BIN"
fi

"$BIN" -i "$INPUT" -o "$OUTPUT"
echo "Wrote $OUTPUT"
