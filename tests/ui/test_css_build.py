"""Tailwind build smoke tests (roadmap 0.3)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT / "scripts" / "build-app-css.sh"
APP_CSS = ROOT / "static" / "css" / "app.css"
ADMIN_PRIMARY_HEX = "#005e78"


def test_build_app_css_portal_primary_not_baked() -> None:
    """Portal theme colors must stay as CSS variables, not admin hex literals."""
    subprocess.run(
        [str(BUILD_SCRIPT)],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    css = APP_CSS.read_text(encoding="utf-8")

    match = re.search(r"\.bg-primary\s*\{[^}]+\}", css)
    assert match is not None, "expected .bg-primary utility in compiled CSS"

    rule = match.group(0)
    assert "var(--portal-primary)" in rule, rule
    assert ADMIN_PRIMARY_HEX not in rule, rule
