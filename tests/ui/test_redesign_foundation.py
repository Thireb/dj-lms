"""Redesign R4a: Lexicon tokens, font, Lucide icons, shells and public pages."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from apps.core.roles import Role
from apps.ui.brand import avatar_tone, initials, user_badge
from apps.ui.components import Icon
from apps.ui.components.actions import ConfirmDialog
from apps.ui.icons import ICON_NAMES
from apps.ui.menus.admin import AdminMenu
from apps.ui.menus.guardian import GuardianMenu
from apps.ui.menus.profile import ADMIN_PROFILE_ITEMS
from apps.ui.menus.student import StudentMenu
from apps.ui.menus.super import SuperMenu
from apps.ui.menus.teacher import TeacherMenu
from django.test import Client
from django.urls import reverse
from tests.conftest import FakeUser, make_user

ROOT = Path(__file__).resolve().parents[2]
SPRITE = ROOT / "static/vendor/lucide/icons.svg"


# Icons


def _menu_icons() -> set[str]:
    icons = {item.icon for item in ADMIN_PROFILE_ITEMS}
    for menu in (AdminMenu, TeacherMenu, StudentMenu, GuardianMenu, SuperMenu):
        for group in menu.groups():
            icons |= {item.icon for item in group.items}
    return icons


def test_every_menu_icon_is_in_the_sprite_list() -> None:
    assert _menu_icons() - ICON_NAMES == set()


def test_every_listed_icon_is_a_symbol_in_the_sprite() -> None:
    symbols = set(re.findall(r'<symbol id="([a-z0-9-]+)"', SPRITE.read_text()))

    assert symbols == ICON_NAMES


def test_icons_in_code_exist() -> None:
    used = set()
    for path in (ROOT / "apps").rglob("*"):
        if path.suffix in {".py", ".html"}:
            text = path.read_text()
            used |= set(re.findall(r'\{% icon "([a-z0-9-]+)"', text))
            used |= set(re.findall(r'icon="([a-z0-9-]+)"', text))
    assert used - ICON_NAMES == set()


def test_icon_renders_the_sprite_and_skips_unknown_names() -> None:
    html = str(Icon("bell", "h-5 w-5"))

    assert '<use href="/static/vendor/lucide/icons.svg#bell">' in html
    assert 'aria-hidden="true"' in html
    assert str(Icon("not-an-icon")).strip() == ""
    assert str(Icon('bell"><script>')).strip() == ""


def test_font_awesome_is_gone_and_the_font_is_preloaded() -> None:
    base = (ROOT / "templates/base.html").read_text()

    assert "fontawesome" not in base
    assert "familjen-grotesk-latin.woff2" in base
    assert not (ROOT / "static/vendor/fontawesome").exists()
    assert (ROOT / "static/vendor/familjen-grotesk/OFL.txt").exists()
    assert (ROOT / "static/vendor/lucide/LICENSE").exists()


# Brand helpers


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Hiba Rauf", "HR"),
        ("Sam A. Sample", "SA"),
        ("sam@example.com", "SA"),
        ("", "?"),
    ],
)
def test_initials(name, expected) -> None:
    assert initials(name) == expected


def test_avatar_tone_is_stable_per_name() -> None:
    assert avatar_tone("Hiba Rauf") == avatar_tone("Hiba Rauf")


def test_user_badge_shows_role_label() -> None:
    badge = user_badge(FakeUser(role=Role.SUB_ADMIN))

    assert badge["role"] == "Sub admin"


# Pages


@pytest.mark.django_db
def test_sign_in_is_a_split_page_with_the_band() -> None:
    page = Client().get(reverse("accounts:login")).content.decode()

    assert "Welcome back" in page
    assert 'aside class="band' in page
    assert 'class="band-waves"' in page
    assert ">LEX<" in page and ">LEXICON<" in page
    assert re.search(
        r'href="/accounts/forgot-password/"[^>]*class="[^"]*text-primary', page
    ) or ('class="-mt-' in page and "Forgot password?" in page)
    assert "btn btn-primary btn-lg w-full" in page
    assert "section-card" not in page  # no box around the form


@pytest.mark.django_db
def test_portal_pages_show_the_clock_public_pages_do_not(institute_a) -> None:
    client = Client()
    client.force_login(
        make_user(email="t@example.com", role=Role.TEACHER, institute=institute_a)
    )

    portal = client.get(reverse("teacher:home")).content.decode()
    public = Client().get(reverse("accounts:login")).content.decode()

    assert 'class="clock' in portal
    assert 'class="clock' not in public


@pytest.mark.django_db
def test_shells_show_brand_role_and_current_page(institute_a) -> None:
    admin = Client()
    admin.force_login(
        make_user(
            email="a@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
        )
    )
    teacher = Client()
    teacher.force_login(
        make_user(email="t@example.com", role=Role.TEACHER, institute=institute_a)
    )

    admin_page = admin.get(reverse("admin:home")).content.decode()
    teacher_page = teacher.get(reverse("teacher:home")).content.decode()

    assert ">Institute admin<" in admin_page and ">LEXICON<" in admin_page
    assert ">Teacher<" in teacher_page
    assert 'aria-current="page"' in teacher_page


def test_confirm_dialog_is_a_modal() -> None:
    html = str(ConfirmDialog("Deactivate Hiba?", "Deactivate", url="/admin/x/"))

    assert 'role="alertdialog" aria-modal="true"' in html
    assert ">Cancel<" in html
    assert "fixed inset-0" in html


@pytest.mark.django_db
def test_notice_pages_are_full_band_pages(school, institute_a) -> None:
    from apps.core.tenancy import tenant_context
    from apps.people.services import set_portal_blocked

    with tenant_context(institute_a):
        set_portal_blocked(school.student_1, blocked=True)
    student = Client()
    student.force_login(school.student_1.user)
    teacher = Client()
    teacher.force_login(school.teacher_1.user)
    paused = student.get(reverse("student:home")).content.decode()
    institute_a.is_active = False
    institute_a.save()
    refused = teacher.get(reverse("teacher:home")).content.decode()

    assert "Access paused." in paused
    assert "Your institute is not active." in refused

    for page in (paused, refused):
        assert '<main class="band' in page
        assert 'class="band-waves"' in page
        assert "btn btn-light" in page  # Sign out on the band
