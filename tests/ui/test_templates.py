"""Smoke tests for base layout templates (roadmap 0.3)."""

from __future__ import annotations

from django.template.loader import render_to_string


def test_base_template_loads_static_paths() -> None:
    html = render_to_string("base.html", {})
    assert "vendor/htmx/htmx.min.js" in html
    assert "vendor/alpine/alpine.min.js" in html
    assert "css/app.css" in html
    assert "chart.umd.min.js" not in html
    assert "X-CSRFToken" in html


def test_app_shell_sets_portal_data_attribute() -> None:
    html = render_to_string(
        "ui/layouts/app_shell.html",
        {"portal": "teacher", "page_title": "Dashboard"},
    )
    assert 'data-portal="teacher"' in html
    assert "<main" in html
    assert "X-CSRFToken" in html
    assert "hx-headers" in html
