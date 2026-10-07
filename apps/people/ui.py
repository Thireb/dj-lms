"""Teacher list table (SPEC section 3: All Teachers)."""

from __future__ import annotations

from django.urls import reverse

from apps.people.models import ProfileStatus, TeacherProfile
from apps.ui.components.actions import Button, ConfirmDialog
from apps.ui.components.block_stack import BlockStack
from apps.ui.components.data import Badge, Column, DataTable


def profile_status_badge(profile: TeacherProfile) -> Badge:
    if profile.status == ProfileStatus.ACTIVE:
        return Badge("Active", tone="success")
    return Badge("Inactive", tone="danger")


def teacher_status_dialog(teacher: TeacherProfile) -> ConfirmDialog:
    url = reverse("admin:teacher_status", kwargs={"pk": teacher.pk})
    name = str(teacher)
    if teacher.status == ProfileStatus.ACTIVE:
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


def _pairs(teacher: TeacherProfile) -> list:
    return list(teacher.batch_subjects.all())


def _batches(teacher: TeacherProfile) -> str:
    return ", ".join(sorted({link.batch.name for link in _pairs(teacher)}))


def _subjects(teacher: TeacherProfile) -> str:
    return ", ".join(sorted({link.subject.name for link in _pairs(teacher)}))


def _actions(teacher: TeacherProfile) -> BlockStack:
    edit_url = reverse("admin:teacher_edit", kwargs={"pk": teacher.pk})
    return BlockStack(
        blocks=[
            Button("Edit", url=edit_url, variant="secondary"),
            teacher_status_dialog(teacher),
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
