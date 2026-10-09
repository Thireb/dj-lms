"""Phone layout fixes (audit H3, H4). Measured once with headless Chromium at
360px and 1280px; these tests pin the markup that makes it work."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from apps.core.roles import Role
from apps.ui.forms.base import INPUT_CLASSES, BaseForm
from django import forms
from django.test import Client
from django.urls import reverse
from tests.conftest import make_user


def _page(user, name: str) -> str:
    client = Client()
    client.force_login(user)
    return client.get(reverse(name)).content.decode()


@pytest.mark.django_db
def test_sidebar_is_hidden_on_phones_with_a_menu_button(institute_a) -> None:
    teacher = make_user(email="t@example.com", role=Role.TEACHER, institute=institute_a)

    page = _page(teacher, "teacher:home")

    classes = re.search(r'id="portal-sidebar" class="([^"]*)"', page).group(1).split()
    assert "hidden" in classes and "md:block" in classes
    assert "max-md:fixed max-md:inset-0" in page  # opened as a full panel
    assert 'aria-controls="portal-sidebar"' in page
    assert 'x-data="{ navOpen: false }"' in page
    assert '@keydown.escape.window="navOpen = false"' in page


@pytest.mark.django_db
def test_admin_menu_groups_are_closed_dropdowns(institute_a) -> None:
    admin = make_user(
        email="a@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )

    page = _page(admin, "admin:home")

    groups = re.findall(r'<button type="button" class="nav-group', page)
    assert len(groups) >= 5  # Basic plan hides the fee and payroll groups
    assert page.count('class="nav-group-items') == len(groups)
    assert re.search(
        r'class="nav-group-items[^"]*md:absolute[^"]*" x-show="open" x-cloak', page
    )
    assert re.search(r'id="top-nav-groups" class="hidden[^"]*md:flex', page)
    assert 'aria-controls="top-nav-groups"' in page


@pytest.mark.django_db
def test_main_column_and_fieldsets_can_shrink(institute_a) -> None:
    admin = make_user(
        email="a@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )

    page = _page(admin, "admin:campus")

    assert '<main class="min-w-0 flex-1' in page
    assert '<section class="section min-w-0' in page


def test_base_form_styles_text_widgets_only() -> None:
    class Demo(BaseForm):
        note = forms.CharField(widget=forms.Textarea)
        name = forms.CharField()
        kind = forms.ChoiceField(choices=[("a", "A")])
        agree = forms.BooleanField(required=False)
        custom = forms.CharField(widget=forms.TextInput(attrs={"class": "own"}))

    fields = Demo().fields

    assert fields["note"].widget.attrs["class"] == INPUT_CLASSES
    assert fields["note"].widget.attrs["rows"] == 3
    assert fields["name"].widget.attrs["class"] == INPUT_CLASSES
    assert fields["kind"].widget.attrs["class"] == INPUT_CLASSES
    assert "class" not in fields["agree"].widget.attrs
    assert fields["custom"].widget.attrs["class"] == "own"
    assert INPUT_CLASSES == "field-control"
    css = (Path(__file__).resolve().parents[2] / "static/css/src/input.css").read_text()
    rule = css[css.index(".field-control {") :].split("}", 1)[0]
    assert "w-full" in rule  # fields fit a 360px screen


@pytest.mark.django_db
def test_bell_is_dark_ink_on_the_white_admin_bar(institute_a) -> None:
    # S18: the bell was a dark icon on the old dark bar. Since R4a the bar is
    # white and the bell is an icon-btn (ink-2 icon on a white tile).
    admin = make_user(
        email="a@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )

    page = _page(admin, "admin:home")

    header = re.search(r'<header class="(top-nav-shell[^"]*)"', page).group(1)
    assert "bg-surface" in header.split()
    assert 'class="notification-bell icon-btn"' in page
