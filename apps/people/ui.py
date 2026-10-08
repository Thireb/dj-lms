"""Teacher and student list tables (SPEC section 3)."""

from __future__ import annotations

from django.urls import reverse

from apps.people.models import ProfileStatus, StudentProfile, TeacherProfile
from apps.ui.components.actions import Button, ConfirmDialog
from apps.ui.components.block_stack import BlockStack
from apps.ui.components.data import Badge, Column, DataTable

Profile = StudentProfile | TeacherProfile


def _url_prefix(profile: Profile) -> str:
    return "student" if isinstance(profile, StudentProfile) else "teacher"


def profile_status_badge(profile: Profile) -> Badge:
    if profile.status == ProfileStatus.ACTIVE:
        return Badge("Active", tone="success")
    return Badge("Inactive", tone="danger")


def profile_status_dialog(profile: Profile) -> ConfirmDialog:
    url = reverse(f"admin:{_url_prefix(profile)}_status", kwargs={"pk": profile.pk})
    name = str(profile)
    if profile.status == ProfileStatus.ACTIVE:
        return ConfirmDialog(
            f"Deactivate {name}? They will not be able to sign in.",
            "Deactivate",
            url=url,
            fields=[("action", "deactivate")],
        )
    return ConfirmDialog(
        f"Activate {name}? They can sign in again.",
        "Activate",
        url=url,
        variant="primary",
        fields=[("action", "activate")],
    )


def _batches(profile: Profile) -> str:
    return ", ".join(sorted({link.batch.name for link in profile.batch_subjects.all()}))


def _subjects(profile: Profile) -> str:
    names = {link.subject.name for link in profile.batch_subjects.all()}
    return ", ".join(sorted(names))


def _guardians(student: StudentProfile) -> str:
    return ", ".join(str(link.guardian) for link in student.guardian_links.all())


def _actions(profile: Profile) -> BlockStack:
    prefix = _url_prefix(profile)
    edit_url = reverse(f"admin:{prefix}_edit", kwargs={"pk": profile.pk})
    return BlockStack(
        blocks=[
            Button("Edit", url=edit_url, variant="secondary"),
            profile_status_dialog(profile),
        ]
    )


class TeacherTable(DataTable):
    columns = [
        Column("teacher_code", "ID"),
        Column("name", "Name", str),
        Column("batches", "Batches", _batches),
        Column("subjects", "Subjects", _subjects),
        Column("phone", "Phone", lambda teacher: teacher.user.phone),
        Column("status", "Status", profile_status_badge),
        Column("actions", "", _actions),
    ]
    empty_title = "No teachers match these filters."


class StudentTable(DataTable):
    columns = [
        Column("student_code", "ID"),
        Column("name", "Name", str),
        Column("class_label", "Class", lambda s: s.class_label or ""),
        Column("batches", "Batches", _batches),
        Column("guardian", "Guardian", _guardians),
        Column("phone", "Phone", lambda student: student.user.phone),
        Column("status", "Status", profile_status_badge),
        Column("actions", "", _actions),
    ]
    empty_title = "No students match these filters."


def _row_result(row) -> BlockStack:
    if row.ok:
        return BlockStack(blocks=[Badge("Ready", tone="success")])
    return BlockStack(blocks=[Badge("Has errors", tone="danger"), *row.errors])


class BulkPreviewTable(DataTable):
    """One line per uploaded row: what will be imported, or why not."""

    columns = [
        Column("number", "Row"),
        Column("name", "Name", lambda row: row.values["full_name"]),
        Column("email", "Student email", lambda row: row.values["student_email"]),
        Column("guardian", "Guardian email", lambda row: row.values["guardian_email"]),
        Column("batches", "Batches", lambda row: row.values["batches"]),
        Column("result", "Result", _row_result),
    ]
    empty_title = "No rows."
