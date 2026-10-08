"""Build small .xlsx files for upload tests. Fake data only."""

from __future__ import annotations

import io

from apps.people.bulk_upload import TEMPLATE_COLUMNS
from openpyxl import Workbook

from tests.conftest import TEST_LOGIN_PASSWORD, TEST_NEW_PASSWORD


def row(**values) -> dict:
    base = {
        "full_name": "Alex Sample",
        "guardian_name": "Sam Sample",
        "guardian_phone": "0300-5555555",
        "batches": "Morning",
        "subjects": "Morning:Math",
        "student_email": "alex@example.com",
        "student_password": TEST_LOGIN_PASSWORD,
        "guardian_email": "parent@example.com",
        "guardian_password": TEST_NEW_PASSWORD,
    }
    base.update(values)
    return base


def xlsx(rows: list[dict], header=TEMPLATE_COLUMNS) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(list(header))
    for values in rows:
        sheet.append([values.get(column) for column in header])
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()
