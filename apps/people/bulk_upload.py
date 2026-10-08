"""Service layer for the bulk student upload (roadmap 2.6, SPEC section 5).

Steps: download the template, upload it, check every row, then import the
rows that passed. Each row is imported on its own (all or nothing per row).
Fee plan columns wait for Phase 7.
"""

from __future__ import annotations

import datetime
import io
import time
import zipfile
from dataclasses import dataclass, field
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from openpyxl import Workbook, load_workbook

from apps.academics.models import Batch, ClassLabel, Subject
from apps.accounts.models import User
from apps.core.roles import Role
from apps.core.tenancy import require_tenant_context
from apps.institutes.models import Institute
from apps.people.models import Gender, StudentProfile, cnic_validator
from apps.people.services import StudentDetails, enrol_student, split_full_name

# Each row hashes up to two passwords (about 2 s on a slow server), and the
# import runs in the web request until Celery arrives (3.2, backlog S8).
MAX_ROWS = 15
MAX_FILE_BYTES = 1024 * 1024
MAX_UNZIPPED_BYTES = 20 * 1024 * 1024
MAX_COLUMNS = 40
MAX_SCANNED_ROWS = 1000  # a far-away cell must not make us read a million rows
READ_SECONDS = 5
# Kept exactly as typed: no space clean-up for passwords.
RAW_COLUMNS = ("student_password", "guardian_password")
# Must be text cells in Excel, or a leading 0 is lost.
TEXT_COLUMNS = ("phone", "guardian_phone", "cnic", *RAW_COLUMNS)

REQUIRED_COLUMNS = (
    "full_name",
    "guardian_name",
    "guardian_phone",
    "batches",
    "subjects",
    "student_email",
    "student_password",
    "guardian_email",
)
OPTIONAL_COLUMNS = (
    "father_name",
    "cnic",
    "dob",
    "gender",
    "class_label",
    "phone",
    "address",
    "city",
    "guardian_password",
)
TEMPLATE_COLUMNS = (
    "full_name",
    "father_name",
    "cnic",
    "dob",
    "gender",
    "class_label",
    "phone",
    "guardian_name",
    "guardian_phone",
    "address",
    "city",
    "batches",
    "subjects",
    "student_email",
    "student_password",
    "guardian_email",
    "guardian_password",
)
HELP_ROWS = (
    ("full_name", "Required."),
    ("dob", "Date of birth as YYYY-MM-DD, or an Excel date."),
    ("gender", "Male, Female or Other. Optional."),
    ("class_label", "Name of an active class. Optional."),
    ("batches", "Required. Batch names, separated by commas: Morning, Evening"),
    (
        "subjects",
        "Required. Subjects for each batch: Morning:Math|Physics; Evening:Chemistry",
    ),
    ("guardian_password", "Leave blank when the guardian already has an account."),
)


class UploadError(Exception):
    """The whole file cannot be read; nothing is checked row by row."""


@dataclass
class RowCheck:
    """One data row: its Excel row number, raw values and any errors."""

    number: int
    values: dict[str, str]
    errors: list[str] = field(default_factory=list)
    selections: dict[Batch, list[Subject]] = field(default_factory=dict)
    details: StudentDetails | None = None

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class ImportResult:
    codes: list[str]
    failed: list[RowCheck]


# Template


def build_template() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Students"
    sheet.append(list(TEMPLATE_COLUMNS))
    for column in TEXT_COLUMNS:
        index = TEMPLATE_COLUMNS.index(column) + 1
        for row in range(2, MAX_SCANNED_ROWS + 1):
            sheet.cell(row=row, column=index).number_format = "@"
    notes = workbook.create_sheet("Help")
    notes.append(["column", "how to fill it"])
    for row in HELP_ROWS:
        notes.append(list(row))
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


# Reading


def _cell_text(value: Any, raw: bool = False) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if raw:
        return str(value)
    return " ".join(str(value).split())


UNREADABLE = "This file is not a valid .xlsx workbook."


def read_rows(upload: io.BufferedIOBase | Any) -> list[dict[str, Any]]:
    """Read the first sheet into dicts keyed by column, with Excel row numbers.

    Any damage in the file becomes an UploadError, never a server error.
    """
    data = upload.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise UploadError("The file is larger than 1 MB.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(info.file_size for info in archive.infolist()) > (
                MAX_UNZIPPED_BYTES
            ):
                raise UploadError("The file is too large when unpacked.")
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        try:
            found = _read_sheet(workbook.worksheets[0])
        finally:
            workbook.close()
    except UploadError:
        raise
    except Exception:  # noqa: BLE001 - openpyxl raises many types for bad files
        raise UploadError(UNREADABLE) from None
    if not found:
        raise UploadError("The file has no student rows.")
    return found


def _read_sheet(sheet: Any) -> list[dict[str, Any]]:
    if (sheet.max_row or 0) > MAX_SCANNED_ROWS:
        raise UploadError(
            f"Keep the student rows in the first {MAX_SCANNED_ROWS} rows of the "
            "sheet and remove anything below them."
        )
    deadline = time.monotonic() + READ_SECONDS
    rows = sheet.iter_rows(
        max_row=MAX_SCANNED_ROWS, max_col=MAX_COLUMNS, values_only=True
    )
    header = [_cell_text(cell).lower() for cell in next(rows, ())]
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise UploadError(f"Missing columns: {', '.join(missing)}.")
    found: list[dict[str, Any]] = []
    for number, cells in enumerate(rows, start=2):
        if time.monotonic() > deadline:
            raise UploadError("The file took too long to read.")
        values: dict[str, str] = {}
        numbers: list[str] = []
        for name, cell in zip(header, cells, strict=False):
            if name not in TEMPLATE_COLUMNS:
                continue
            values[name] = _cell_text(cell, raw=name in RAW_COLUMNS)
            if name in TEXT_COLUMNS and isinstance(cell, int | float):
                numbers.append(name)
        if not any(value.strip() for value in values.values()):
            continue
        if len(found) == MAX_ROWS:
            raise UploadError(f"Upload at most {MAX_ROWS} students per file.")
        found.append({"number": number, "values": values, "numbers": numbers})
    return found


# Checking


class _Lookups:
    """Active lists of the institute and emails already in use, loaded once."""

    def __init__(self, institute: Institute):
        def by_name(model: type) -> dict[str, Any]:
            rows = model.objects.filter(institute=institute, is_active=True)
            return {row.name.lower(): row for row in rows}

        self.batches = by_name(Batch)
        self.subjects = by_name(Subject)
        self.labels = by_name(ClassLabel)
        self.institute = institute


def _parse_subjects(text: str) -> list[tuple[str, list[str]]]:
    groups = []
    for part in text.split(";"):
        if not part.strip():
            continue
        batch, _, subjects = part.partition(":")
        names = [name.strip() for name in subjects.split("|") if name.strip()]
        groups.append((batch.strip(), names))
    return groups


def _check_lists(row: RowCheck, lookups: _Lookups) -> None:
    values = row.values
    listed = {name.strip().lower() for name in values["batches"].split(",")}
    listed.discard("")
    groups = _parse_subjects(values["subjects"])
    if {batch.lower() for batch, _ in groups} != listed:
        row.errors.append("The batches in subjects must match the batches column.")
    for batch_name, subject_names in groups:
        batch = lookups.batches.get(batch_name.lower())
        if batch is None:
            row.errors.append(f"Unknown or inactive batch: {batch_name}.")
            continue
        if not subject_names:
            row.errors.append(f"Choose at least one subject for {batch.name}.")
        for name in subject_names:
            subject = lookups.subjects.get(name.lower())
            if subject is None:
                row.errors.append(f"Unknown or inactive subject: {name}.")
            else:
                row.selections.setdefault(batch, []).append(subject)


def _check_details(row: RowCheck, lookups: _Lookups) -> None:
    values = row.values
    dob = None
    if values.get("dob"):
        try:
            dob = datetime.date.fromisoformat(values["dob"])
        except ValueError:
            row.errors.append("Date of birth must be YYYY-MM-DD.")
    gender = values.get("gender", "").lower()
    if gender and gender not in Gender.values:
        row.errors.append("Gender must be Male, Female or Other.")
    label = None
    if values.get("class_label"):
        label = lookups.labels.get(values["class_label"].lower())
        if label is None:
            row.errors.append(f"Unknown or inactive class: {values['class_label']}.")
    if values.get("cnic"):
        try:
            cnic_validator(values["cnic"])
        except ValidationError as error:
            row.errors.extend(error.messages)
    row.details = StudentDetails(
        full_name=values["full_name"],
        phone=values.get("phone", ""),
        guardian_phone=values["guardian_phone"],
        father_name=values.get("father_name", ""),
        cnic=values.get("cnic", ""),
        date_of_birth=dob,
        gender=gender,
        class_label=label,
        address=values.get("address", ""),
        city=values.get("city", ""),
    )


PHONE_COLUMNS = ("phone", "guardian_phone")


def _check_fields(row: RowCheck) -> None:
    """Run the model field checks (lengths and the like), naming the column."""
    values = row.values
    first, last = split_full_name(values["full_name"])
    guardian_first, guardian_last = split_full_name(values["guardian_name"])
    checks = (
        (
            User(first_name=first, last_name=last, phone=values["phone"]),
            {"first_name": "full_name", "last_name": "full_name", "phone": "phone"},
        ),
        (
            StudentProfile(
                father_name=values["father_name"],
                guardian_phone=values["guardian_phone"],
                address=values["address"],
                city=values["city"],
            ),
            {
                "father_name": "father_name",
                "guardian_phone": "guardian_phone",
                "address": "address",
                "city": "city",
            },
        ),
        (
            User(first_name=guardian_first, last_name=guardian_last),
            {"first_name": "guardian_name", "last_name": "guardian_name"},
        ),
    )
    for instance, columns in checks:
        skip = [f.name for f in instance._meta.fields if f.name not in columns]
        try:
            instance.clean_fields(exclude=skip)
        except ValidationError as error:
            for name, messages in error.message_dict.items():
                for message in messages:
                    text = f"{columns[name]}: {message}"
                    if text not in row.errors:
                        row.errors.append(text)


def _password_errors(password: str, label: str, email: str) -> list[str]:
    try:
        validate_password(password, User(email=email))
    except ValidationError as error:
        return [f"{label}: {message}" for message in error.messages]
    return []


def _check_accounts(
    row: RowCheck,
    institute: Institute,
    student_emails: set[str],
    new_guardians: set[str],
) -> None:
    values = row.values
    email = values["student_email"].lower()
    guardian_email = values["guardian_email"].lower()
    for label, value in (("Student email", email), ("Guardian email", guardian_email)):
        try:
            validate_email(value)
        except ValidationError:
            row.errors.append(f"{label} is not a valid email address.")
    if email == guardian_email:
        row.errors.append("The student and guardian emails must be different.")
    if email in student_emails or email in new_guardians:
        row.errors.append("Student email is used twice in this file.")
    elif User.objects.filter(email__iexact=email).exists():
        row.errors.append("Student email is already used by another account.")
    row.errors += _password_errors(
        values["student_password"], "Student password", email
    )
    if guardian_email in student_emails:
        row.errors.append("Guardian email is a student email in this file.")
        return
    existing = User.objects.filter(email__iexact=guardian_email).first()
    if existing is not None:
        if existing.role != Role.GUARDIAN or existing.institute_id != institute.pk:
            row.errors.append("Guardian email is already used by another account.")
    elif guardian_email not in new_guardians:
        if not values.get("guardian_password"):
            row.errors.append("Enter a password for the new guardian.")
        else:
            row.errors += _password_errors(
                values["guardian_password"], "Guardian password", guardian_email
            )


def check_rows(institute: Institute, rows: list[dict[str, Any]]) -> list[RowCheck]:
    """Check every row against SPEC section 5; rows do not change the database."""
    require_tenant_context(institute)
    lookups = _Lookups(institute)
    student_emails: set[str] = set()
    new_guardians: set[str] = set()
    checks = []
    for raw in rows:
        row = RowCheck(number=raw["number"], values=dict(raw["values"]))
        for column in TEMPLATE_COLUMNS:
            row.values.setdefault(column, "")
        missing = [column for column in REQUIRED_COLUMNS if not row.values[column]]
        if missing:
            row.errors.append(f"Missing: {', '.join(missing)}.")
        else:
            for column in PHONE_COLUMNS:
                if column in raw.get("numbers", ()):
                    row.errors.append(
                        f"{column}: format the cell as Text so a leading 0 is "
                        "kept, then type the number again."
                    )
            _check_lists(row, lookups)
            _check_details(row, lookups)
            _check_fields(row)
            _check_accounts(row, institute, student_emails, new_guardians)
        if row.ok:
            student_emails.add(row.values["student_email"].lower())
            new_guardians.add(row.values["guardian_email"].lower())
        checks.append(row)
    return checks


# Import


def import_rows(institute: Institute, rows: list[dict[str, Any]]) -> ImportResult:
    """Check the rows again (data may have changed), then enrol the good ones."""
    require_tenant_context(institute)
    codes: list[str] = []
    failed: list[RowCheck] = []
    for row in check_rows(institute, rows):
        if not row.ok:
            failed.append(row)
            continue
        values = row.values
        try:
            student = enrol_student(
                institute,
                row.details,
                email=values["student_email"],
                password=values["student_password"],
                selections=row.selections,
                guardian_name=values["guardian_name"],
                guardian_email=values["guardian_email"],
                guardian_password=values["guardian_password"],
            )
        except ValidationError as error:
            row.errors.extend(error.messages)
            failed.append(row)
            continue
        codes.append(student.student_code)
    return ImportResult(codes=codes, failed=failed)
