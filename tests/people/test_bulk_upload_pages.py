"""Bulk upload pages: template, preview and import (roadmap 2.6, SPEC 5)."""

from __future__ import annotations

import html as html_lib
import io
import re

import pytest
from apps.accounts.models import User
from apps.core.roles import Role
from apps.people.models import StudentProfile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from openpyxl import load_workbook

from tests.conftest import make_user
from tests.people.xlsx import row, xlsx

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _admin(institute, email="admin-a@example.com", **client_kw) -> Client:
    client = Client(**client_kw)
    client.force_login(
        make_user(email=email, role=Role.INSTITUTE_ADMIN, institute=institute)
    )
    return client


@pytest.fixture
def admin_client(institute_a) -> Client:
    return _admin(institute_a)


def _upload(client: Client, rows: list[dict], name: str = "students.xlsx"):
    upload = SimpleUploadedFile(name, xlsx(rows), content_type=XLSX)
    return client.post(reverse("admin:student_bulk_upload"), {"file": upload})


def _payload(response) -> str:
    page = response.content.decode()
    match = re.search(r'name="upload" value="([^"]+)"', page)
    return html_lib.unescape(match.group(1))


@pytest.mark.django_db
def test_page_offers_template_and_upload(admin_client) -> None:
    page = admin_client.get(reverse("admin:student_bulk_upload")).content.decode()

    assert 'type="file"' in page
    assert 'accept=".xlsx"' in page
    assert f'href="{reverse("admin:student_bulk_template")}"' in page


@pytest.mark.django_db
def test_template_download(admin_client) -> None:
    response = admin_client.get(reverse("admin:student_bulk_template"))

    assert response["Content-Type"] == XLSX
    assert "attachment;" in response["Content-Disposition"]
    workbook = load_workbook(io.BytesIO(response.content))
    assert workbook["Students"]["A1"].value == "full_name"


@pytest.mark.django_db
def test_preview_shows_each_row_and_saves_nothing(admin_client, school) -> None:
    response = _upload(
        admin_client,
        [row(), row(student_email="bad", guardian_email="x@example.com")],
    )
    page = response.content.decode()

    assert "Rows ready: 1. Rows with errors (skipped): 1." in page
    assert "Student email is not a valid email address." in page
    assert "Import 1 student<" in page
    assert "no-store" in response["Cache-Control"]
    assert not User.objects.filter(email="alex@example.com").exists()


@pytest.mark.django_db
def test_preview_without_good_rows_has_no_import(admin_client, school) -> None:
    page = _upload(admin_client, [row(batches="Night", subjects="Night:Math")])

    assert "Import " not in page.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("name", "message"),
    [("students.csv", "Upload an .xlsx file"), ("students.xlsx", "Missing columns")],
)
def test_bad_file_shows_error(admin_client, school, name, message) -> None:
    upload = SimpleUploadedFile(
        name, xlsx([row()], header=("full_name",)), content_type=XLSX
    )

    page = admin_client.post(reverse("admin:student_bulk_upload"), {"file": upload})

    assert message in page.content.decode()


@pytest.mark.django_db
def test_user_text_is_escaped_in_preview(admin_client, school) -> None:
    page = _upload(admin_client, [row(full_name="<script>alert(1)</script>")])

    assert "<script>alert(1)</script>" not in page.content.decode()
    assert "&lt;script&gt;" in page.content.decode()


@pytest.mark.django_db
def test_import_from_preview_with_csrf(institute_a, school) -> None:
    client = _admin(institute_a, enforce_csrf_checks=True)
    upload_page = client.get(reverse("admin:student_bulk_upload")).content.decode()
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', upload_page)
    upload = SimpleUploadedFile("s.xlsx", xlsx([row()]), content_type=XLSX)
    preview = client.post(
        reverse("admin:student_bulk_upload"),
        {"file": upload, "csrfmiddlewaretoken": token.group(1)},
    )
    form = preview.content.decode()
    form = form[form.index(f'action="{reverse("admin:student_bulk_import")}"') :]
    import_token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', form)

    response = client.post(
        reverse("admin:student_bulk_import"),
        {"upload": _payload(preview), "csrfmiddlewaretoken": import_token.group(1)},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("admin:student_list")
    assert "Imported 1 student: STU-004 to STU-004." in response.content.decode()
    # unscoped: test assertion outside a tenant context.
    assert StudentProfile.unscoped.filter(user__email="alex@example.com").exists()


@pytest.mark.django_db
def test_tampered_payload_imports_nothing(admin_client, school) -> None:
    payload = _payload(_upload(admin_client, [row()]))

    response = admin_client.post(
        reverse("admin:student_bulk_import"), {"upload": payload + "x"}, follow=True
    )

    assert "This upload has expired." in response.content.decode()
    assert not User.objects.filter(email="alex@example.com").exists()


@pytest.mark.django_db
def test_payload_only_works_for_the_admin_who_checked_it(
    admin_client, school, institute_a
) -> None:
    payload = _payload(_upload(admin_client, [row()]))
    other_admin = _admin(institute_a, email="admin-two@example.com")

    response = other_admin.post(
        reverse("admin:student_bulk_import"), {"upload": payload}, follow=True
    )

    assert "This upload has expired." in response.content.decode()
    assert not User.objects.filter(email="alex@example.com").exists()


@pytest.mark.django_db
def test_import_is_post_only(admin_client) -> None:
    assert admin_client.get(reverse("admin:student_bulk_import")).status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize("role", [Role.TEACHER, Role.STUDENT, Role.GUARDIAN])
@pytest.mark.parametrize(
    "name", ["student_bulk_upload", "student_bulk_template", "student_bulk_import"]
)
def test_other_roles_get_403(client, institute_a, role, name) -> None:
    client.force_login(
        make_user(email="x@example.com", role=role, institute=institute_a)
    )

    assert client.post(reverse(f"admin:{name}")).status_code == 403


@pytest.mark.django_db
def test_sub_admin_without_people_menu_gets_403(client, institute_a) -> None:
    client.force_login(
        make_user(email="sub@example.com", role=Role.SUB_ADMIN, institute=institute_a)
    )

    assert client.get(reverse("admin:student_bulk_upload")).status_code == 403
