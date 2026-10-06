#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION_FILE="$ROOT/static/css/TAILWIND_VERSION"
CHECKSUMS_FILE="$ROOT/static/css/TAILWIND_CHECKSUMS"
BIN="$ROOT/scripts/tailwindcss"
INPUT="$ROOT/static/css/src/input.css"
OUTPUT="$ROOT/static/css/app.css"

if [[ ! -f "$VERSION_FILE" ]]; then
  echo "Missing $VERSION_FILE" >&2
  exit 1
fi

if [[ ! -f "$CHECKSUMS_FILE" ]]; then
  echo "Missing $CHECKSUMS_FILE" >&2
  exit 1
fi

VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"

detect_platform_id() {
  local os arch
  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  case "$os" in
    linux) os="linux" ;;
    darwin) os="macos" ;;
    mingw* | msys* | cygwin* | windows*) os="windows" ;;
    *)
      echo "Unsupported OS: $(uname -s)" >&2
      exit 1
      ;;
  esac

  arch="$(uname -m)"
  case "$arch" in
    x86_64 | amd64) arch="x64" ;;
    aarch64 | arm64) arch="arm64" ;;
    *)
      echo "Unsupported architecture: $(uname -m)" >&2
      exit 1
      ;;
  esac

  echo "${os}-${arch}"
}

PLATFORM_ID="$(detect_platform_id)"

lookup_checksum() {
  local platform="$1"
  awk -v platform="$platform" '
    /^#/ || NF == 0 { next }
    $1 == platform { print $2; exit }
  ' "$CHECKSUMS_FILE"
}

EXPECTED_SHA256="$(lookup_checksum "$PLATFORM_ID")"
if [[ -z "$EXPECTED_SHA256" ]]; then
  echo "No checksum for platform ${PLATFORM_ID} in $CHECKSUMS_FILE" >&2
  exit 1
fi

if [[ "$PLATFORM_ID" == windows-* ]]; then
  RELEASE_ASSET="tailwindcss-${PLATFORM_ID}.exe"
else
  RELEASE_ASSET="tailwindcss-${PLATFORM_ID}"
fi

DOWNLOAD_URL="https://github.com/tailwindlabs/tailwindcss/releases/download/v${VERSION}/${RELEASE_ASSET}"

verify_binary() {
  local file="$1"
  local actual
  actual="$(sha256sum "$file" | awk '{print $1}')"
  if [[ "$actual" != "$EXPECTED_SHA256" ]]; then
    echo "Checksum mismatch for $file (expected $EXPECTED_SHA256, got $actual)" >&2
    return 1
  fi
}

if [[ -x "$BIN" ]]; then
  if ! verify_binary "$BIN"; then
    echo "Removing invalid cached binary $BIN" >&2
    rm -f "$BIN"
  fi
fi

if [[ ! -x "$BIN" ]]; then
  echo "Downloading Tailwind CSS standalone v${VERSION} (${PLATFORM_ID})..."
  curl -fsSL "$DOWNLOAD_URL" -o "$BIN"
  chmod +x "$BIN"
  verify_binary "$BIN"
fi

"$BIN" -i "$INPUT" -o "$OUTPUT"
echo "Wrote $OUTPUT"
