"""Redesign audit fixes RA1-RA6 (RA8 is tests/people/test_dashboard_queries.py)."""

from __future__ import annotations

import re

import pytest
from apps.core.responses import handle_500
from apps.core.roles import Role
from django.test import Client, RequestFactory
from django.urls import reverse
from tests.conftest import make_user

TEMPLATES = "apps/ui/templates/ui"


def _read(path: str) -> str:
    with open(path) as handle:
        return handle.read()


@pytest.mark.django_db
def test_missing_page_is_the_styled_404(client) -> None:
    response = client.get("/no-such-page/")
    page = response.content.decode()

    assert response.status_code == 404
    assert ">Page not found</h1>" in page
    assert '<main class="band' in page
    assert 'href="/"' in page and "Go to my home page" in page


@pytest.mark.django_db
def test_wrong_role_gets_the_styled_403(institute_a) -> None:
    client = Client()
    client.force_login(
        make_user(email="t@example.com", role=Role.TEACHER, institute=institute_a)
    )

    response = client.get(reverse("admin:home"))

    assert response.status_code == 403
    assert ">No access to this page</h1>" in response.content.decode()


@pytest.mark.django_db
def test_sub_admin_without_menu_gets_the_styled_403(institute_a) -> None:
    client = Client()
    client.force_login(
        make_user(email="s@example.com", role=Role.SUB_ADMIN, institute=institute_a)
    )

    response = client.get(reverse("admin:teacher_list"))

    assert response.status_code == 403
    assert "Ask your institute admin" in response.content.decode()


def test_server_error_page_renders_without_a_signed_in_user() -> None:
    response = handle_500(RequestFactory().get("/"))

    assert response.status_code == 500
    assert ">Something went wrong</h1>" in response.content.decode()


def test_error_handlers_are_wired_in_both_url_files() -> None:
    from config import urls, urls_test

    for module in (urls, urls_test):
        assert module.handler403 == "apps.core.responses.handle_403"
        assert module.handler404 == "apps.core.responses.handle_404"
        assert module.handler500 == "apps.core.responses.handle_500"


def test_menu_list_closes_on_escape_and_outside_click() -> None:
    nav = _read(f"{TEMPLATES}/components/top_nav.html")
    opening = re.search(r'<nav class="top-nav[^>]*>', nav).group(0)

    assert '@keydown.escape="menuOpen = false"' in opening
    assert '@click.outside="menuOpen = false"' in opening


def test_view_all_link_is_at_least_32px_tall() -> None:
    from apps.ui.components.layout import SectionCard

    html = str(SectionCard("Students", "body", link_url="/admin/students/"))
    link = re.search(r'<a href="/admin/students/" class="([^"]*)"', html).group(1)

    assert "min-h-8" in link.split() and "px-2" in link.split()


@pytest.mark.django_db
def test_checkbox_row_is_one_40px_label(institute_a) -> None:
    from apps.institutes.forms import InstituteSettingsForm
    from crispy_forms.utils import render_crispy_form

    html = render_crispy_form(InstituteSettingsForm(institute=institute_a))
    row = re.search(
        r'<label for="id_auto_block_defaulters" class="([^"]*)">\s*<input', html
    )

    assert row and "min-h-10" in row.group(1).split()


@pytest.mark.django_db
def test_logo_link_name_starts_with_its_visible_text(institute_a) -> None:
    client = Client()
    client.force_login(
        make_user(
            email="a@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
        )
    )
    page = client.get(reverse("admin:home")).content.decode()

    assert 'aria-label="LEXICON home"' not in page
    assert re.search(
        r'LEXICON</span></span>\s*<span class="sr-only"> home</span></a>', page
    )


@pytest.mark.django_db
def test_sign_in_panel_promises_only_what_exists(client) -> None:
    page = client.get(reverse("accounts:login")).content.decode()

    assert "Join live classes" not in page
    assert "upload receipts" not in page
    assert "Coming to the portal step by step" in page
