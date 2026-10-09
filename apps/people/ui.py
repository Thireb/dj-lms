"""Teacher and student list tables (SPEC section 3)."""

from __future__ import annotations

from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import format as format_date

from apps.people.models import (
    PortalAccessRule,
    ProfileStatus,
    StudentProfile,
    TeacherProfile,
)
from apps.ui.components.actions import ConfirmDialog, IconButton
from apps.ui.components.block_stack import BlockStack, ButtonRow
from apps.ui.components.data import Badge, Column, DataTable, PersonCell

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


def _code(profile: Profile) -> str:
    return getattr(profile, "student_code", "") or getattr(profile, "teacher_code", "")


def person(profile: Profile) -> PersonCell:
    """Avatar, name and the student or teacher code, for every people table."""
    return PersonCell(str(profile), detail=_code(profile))


def _actions(profile: Profile) -> ButtonRow:
    prefix = _url_prefix(profile)
    edit_url = reverse(f"admin:{prefix}_edit", kwargs={"pk": profile.pk})
    return ButtonRow(
        items=[
            IconButton("square-pen", f"Edit {profile}", url=edit_url),
            profile_status_dialog(profile),
        ]
    )


class TeacherTable(DataTable):
    columns = [
        Column("name", "Teacher", person),
        Column("batches", "Batches", _batches),
        Column("subjects", "Subjects", _subjects),
        Column("phone", "Phone", lambda teacher: teacher.user.phone),
        Column("status", "Status", profile_status_badge),
        Column("actions", "", _actions),
    ]
    empty_title = "No teachers match these filters."


class StudentTable(DataTable):
    columns = [
        Column("name", "Student", person),
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


def _added_on(profile: Profile) -> str:
    return format_date(timezone.localtime(profile.created_at), "j M Y")


class RecentStudentTable(DataTable):
    columns = [
        Column("name", "Student", person),
        Column("batches", "Batches", _batches),
        Column("status", "Status", profile_status_badge),
        Column("added", "Enrolled", _added_on),
    ]
    empty_title = "No students yet."


class RecentTeacherTable(DataTable):
    columns = [
        Column("name", "Teacher", person),
        Column("subjects", "Subjects", _subjects),
        Column("status", "Status", profile_status_badge),
        Column("added", "Added", _added_on),
    ]
    empty_title = "No teachers yet."


def _access(student: StudentProfile) -> tuple[bool, bool]:
    try:
        rule = student.access_rule
    except PortalAccessRule.DoesNotExist:
        return False, False
    return rule.blocked, rule.exempt


def _yes_no(value: bool, yes_tone: str) -> Badge:
    return Badge("Yes", tone=yes_tone) if value else Badge("No", tone="neutral")


def _access_dialog(student: StudentProfile, action: str, message: str, label: str):
    url = reverse("admin:portal_access_action", kwargs={"pk": student.pk})
    variant = "danger" if action == "block" else "primary"
    return ConfirmDialog(
        message, label, url=url, variant=variant, fields=[("action", action)]
    )


def _access_actions(student: StudentProfile) -> ButtonRow:
    blocked, exempt = _access(student)
    name = str(student)
    if blocked:
        block = _access_dialog(
            student, "unblock", f"Unblock {name}? The student portal opens.", "Unblock"
        )
    else:
        block = _access_dialog(
            student,
            "block",
            f"Block {name}? The student portal shows Access paused. "
            "The guardian portal stays open.",
            "Block",
        )
    if exempt:
        exemption = _access_dialog(
            student,
            "unexempt",
            f"Remove the exemption for {name}? Automatic blocking can apply again.",
            "Remove exemption",
        )
    else:
        exemption = _access_dialog(
            student,
            "exempt",
            f"Exempt {name}? Automatic blocking will never block this student.",
            "Exempt",
        )
    return ButtonRow(items=[block, exemption])


class PortalAccessTable(DataTable):
    """SPEC 3 Portal Access. Fee due comes with Phase 7."""

    columns = [
        Column("name", "Student", person),
        Column("class_label", "Class", lambda s: s.class_label or ""),
        Column("guardian", "Guardian", _guardians),
        Column("blocked", "Blocked", lambda s: _yes_no(_access(s)[0], "danger")),
        Column("exempt", "Exempt", lambda s: _yes_no(_access(s)[1], "info")),
        Column("actions", "", _access_actions),
    ]
    empty_title = "No students match these filters."
