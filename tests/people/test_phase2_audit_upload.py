"""Phase 2 audit fixes for the bulk upload (H5, H6, M1, M4, M5, M6)."""

from __future__ import annotations

import io
import time
import zipfile

import pytest
from apps.accounts.models import User
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.people.bulk_upload import (
    MAX_ROWS,
    MAX_SCANNED_ROWS,
    TEMPLATE_COLUMNS,
    UploadError,
    check_rows,
    import_rows,
    read_rows,
)
from apps.people.views import UPLOAD_SESSION_KEY
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from openpyxl import Workbook

from tests.conftest import TEST_LOGIN_PASSWORD, make_user
from tests.people.xlsx import row, xlsx


def _check(school, *rows):
    institute = school.morning.institute
    with tenant_context(institute):
        return check_rows(institute, read_rows(io.BytesIO(xlsx(list(rows)))))


def _workbook_bytes(fill) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(list(TEMPLATE_COLUMNS))
    fill(sheet)
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


# H5: a far-away cell must not make the reader scan a million rows


def test_far_cell_is_refused_quickly() -> None:
    data = _workbook_bytes(lambda sheet: sheet.cell(row=1048576, column=1, value="x"))
    started = time.monotonic()

    with pytest.raises(UploadError) as error:
        read_rows(io.BytesIO(data))

    assert time.monotonic() - started < 2
    assert f"first {MAX_SCANNED_ROWS} rows" in str(error.value)


def test_unpacked_size_is_limited() -> None:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/big.xml", b"0" * (21 * 1024 * 1024))

    with pytest.raises(UploadError) as error:
        read_rows(io.BytesIO(out.getvalue()))

    assert "too large when unpacked" in str(error.value)


# H6: at most 15 rows until Celery


def test_row_limit_is_15() -> None:
    assert MAX_ROWS == 15
    many = [row(student_email=f"s{n}@example.com") for n in range(16)]

    with pytest.raises(UploadError) as error:
        read_rows(io.BytesIO(xlsx(many)))

    assert "at most 15 students" in str(error.value)


# M1: damaged files never crash


def _damaged(name: str, cut) -> bytes:
    source = zipfile.ZipFile(io.BytesIO(xlsx([row()])))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == name:
                data = cut(data)
            target.writestr(info, data)
    return out.getvalue()


@pytest.mark.parametrize(
    "data",
    [
        _damaged("xl/worksheets/sheet1.xml", lambda data: data[: len(data) // 2]),
        _damaged("xl/workbook.xml", lambda data: b"<not xml"),
        _damaged("[Content_Types].xml", lambda data: b""),
        xlsx([row()])[:-200],
    ],
    ids=["cut-sheet", "bad-workbook", "no-types", "cut-zip"],
)
def test_damaged_files_give_a_clean_error(data) -> None:
    with pytest.raises(UploadError) as error:
        read_rows(io.BytesIO(data))

    assert "not a valid .xlsx workbook" in str(error.value)


@pytest.mark.django_db
def test_damaged_file_page_is_not_a_server_error(client, institute_a) -> None:
    client.force_login(
        make_user(
            email="a@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
        )
    )
    data = _damaged("xl/worksheets/sheet1.xml", lambda data: data[:-40])

    response = client.post(
        reverse("admin:student_bulk_upload"),
        {"file": SimpleUploadedFile("s.xlsx", data)},
    )

    assert response.status_code == 200
    assert "not a valid .xlsx workbook" in response.content.decode()


# M4: the check step runs the same field checks as the import


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("values", "column"),
    [
        ({"guardian_phone": "0" * 40}, "guardian_phone"),
        ({"full_name": "Alex " + "x" * 200}, "full_name"),
        ({"city": "c" * 500}, "city"),
        ({"father_name": "f" * 200}, "father_name"),
        ({"guardian_name": "Sam " + "y" * 200}, "guardian_name"),
        ({"phone": "1" * 40}, "phone"),
    ],
)
def test_too_long_values_fail_the_check_and_name_the_column(school, values, column):
    (check,) = _check(school, row(**values))

    assert not check.ok
    assert any(error.startswith(f"{column}: ") for error in check.errors), check.errors


@pytest.mark.django_db
def test_rows_that_pass_the_check_import(school) -> None:
    institute = school.morning.institute
    rows = read_rows(io.BytesIO(xlsx([row(city="c" * 100, father_name="f" * 150)])))

    with tenant_context(institute):
        result = import_rows(institute, rows)

    assert result.codes == ["STU-004"]


# M5: cell values are not changed


@pytest.mark.django_db
def test_password_spaces_are_kept(school) -> None:
    institute = school.morning.institute
    password = f"my  {TEST_LOGIN_PASSWORD} 1"
    rows = read_rows(io.BytesIO(xlsx([row(student_password=password)])))

    with tenant_context(institute):
        import_rows(institute, rows)

    user = User.objects.get(email="alex@example.com")
    assert user.check_password(password)


@pytest.mark.django_db
@pytest.mark.parametrize("column", ["phone", "guardian_phone"])
def test_phone_typed_as_a_number_is_an_error(school, column) -> None:
    (check,) = _check(school, row(**{column: 3001234567}))

    assert any(
        error.startswith(f"{column}: format the cell as Text") for error in check.errors
    ), check.errors


@pytest.mark.django_db
def test_phone_typed_as_text_keeps_the_leading_zero(school) -> None:
    (check,) = _check(school, row(guardian_phone="03001234567"))

    assert check.ok, check.errors
    assert check.details.guardian_phone == "03001234567"


# M6: passwords stay on the server


def _admin(institute) -> Client:
    client = Client()
    client.force_login(
        make_user(email="a@example.com", role=Role.INSTITUTE_ADMIN, institute=institute)
    )
    return client


def _upload(client: Client):
    return client.post(
        reverse("admin:student_bulk_upload"),
        {"file": SimpleUploadedFile("s.xlsx", xlsx([row()]))},
    )


@pytest.mark.django_db
def test_preview_page_has_no_password_or_row_data(school, institute_a) -> None:
    client = _admin(institute_a)

    page = _upload(client).content.decode()

    assert TEST_LOGIN_PASSWORD not in page
    assert 'name="rows"' not in page
    assert 'name="upload"' in page
    assert client.session[UPLOAD_SESSION_KEY]["rows"][0]["number"] == 2


@pytest.mark.django_db
def test_import_forgets_the_rows(school, institute_a) -> None:
    client = _admin(institute_a)
    page = _upload(client).content.decode()
    upload_id = page.split('name="upload" value="')[1].split('"')[0]

    client.post(reverse("admin:student_bulk_import"), {"upload": upload_id})
    again = client.post(
        reverse("admin:student_bulk_import"), {"upload": upload_id}, follow=True
    )

    assert UPLOAD_SESSION_KEY not in client.session
    assert "This upload has expired." in again.content.decode()
    assert User.objects.filter(email="alex@example.com").count() == 1


@pytest.mark.django_db
def test_old_upload_expires(school, institute_a) -> None:
    client = _admin(institute_a)
    page = _upload(client).content.decode()
    upload_id = page.split('name="upload" value="')[1].split('"')[0]
    session = client.session
    session[UPLOAD_SESSION_KEY]["created"] -= 31 * 60
    session.save()

    response = client.post(
        reverse("admin:student_bulk_import"), {"upload": upload_id}, follow=True
    )

    assert "This upload has expired." in response.content.decode()
    assert not User.objects.filter(email="alex@example.com").exists()
