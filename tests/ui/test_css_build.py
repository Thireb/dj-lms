"""Tailwind build smoke tests (roadmap 0.3)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT / "scripts" / "build-app-css.sh"
APP_CSS = ROOT / "static" / "css" / "app.css"
LEXICON_ROYAL = "#002da8"


def test_build_app_css_uses_the_lexicon_theme() -> None:
    """One Lexicon theme for every portal (roadmap Phase R): utilities read tokens."""
    subprocess.run(
        [str(BUILD_SCRIPT)],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    css = APP_CSS.read_text(encoding="utf-8")

    rule = re.search(r"\.bg-primary\s*\{[^}]+\}", css)
    assert rule is not None, "expected .bg-primary utility in compiled CSS"
    assert "var(--color-primary)" in rule.group(0)
    assert re.search(r"--color-primary:\s*" + LEXICON_ROYAL, css)
    assert "Familjen Grotesk" in css
    assert "--portal-primary" not in css
