"""Smoke tests for base layout templates (roadmap 0.3)."""

from __future__ import annotations

from pathlib import Path

from django.template.loader import render_to_string


def test_base_template_loads_static_paths() -> None:
    html = render_to_string("base.html", {})
    assert "vendor/htmx/htmx.min.js" in html
    assert "js/app.js" in html
    assert "vendor/alpine/alpine.min.js" in html
    assert "css/app.css" in html
    assert "chart.umd.min.js" not in html
    assert "X-CSRFToken" in html


def test_app_js_loads_before_alpine_in_base_template() -> None:
    html = render_to_string("base.html", {})
    app_pos = html.index("js/app.js")
    alpine_pos = html.index("vendor/alpine/alpine.min.js")
    assert app_pos < alpine_pos


def test_app_js_registers_countdown_card_for_alpine() -> None:
    root = Path(__file__).resolve().parents[2]
    app_js = (root / "static/js/app.js").read_text(encoding="utf-8")
    assert 'Alpine.data("countdownCard"' in app_js
    assert "dataset.scheduledAt" in app_js


def test_app_shell_sets_portal_data_attribute() -> None:
    html = render_to_string(
        "ui/layouts/app_shell.html",
        {"portal": "teacher", "page_title": "Dashboard"},
    )
    assert 'data-portal="teacher"' in html
    assert "<main" in html
    assert "X-CSRFToken" in html
    assert "hx-headers" in html
