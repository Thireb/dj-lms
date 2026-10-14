"""The teacher's attendance form: one mark per student (roadmap 4.1)."""

from __future__ import annotations

from typing import Any

from crispy_forms.layout import Layout
from django import forms

from apps.attendance.models import AttendanceStatus
from apps.attendance.services import RosterEntry
from apps.ui.forms.base import BaseForm, FormActions
from apps.ui.forms.widgets import ChipRadios

PREFIX = "student_"


class AttendanceForm(BaseForm):
    """A student without a mark starts as Present, so the teacher changes
    only the students who were absent, late or partial."""

    save_label = "Save attendance"

    def __init__(self, *args: Any, roster: list[RosterEntry], cancel_url: str, **kw):
        self.cancel_url = cancel_url
        super().__init__(*args, **kw)
        for entry in roster:
            name = str(entry.student)
            self.fields[f"{PREFIX}{entry.student.pk}"] = forms.ChoiceField(
                label=name,
                choices=AttendanceStatus.choices,
                initial=entry.status or AttendanceStatus.PRESENT,
                widget=ChipRadios(group_label=f"Attendance for {name}"),
                help_text=entry.student.student_code,
            )
        self.helper.layout = self.get_layout()

    def get_layout(self) -> Layout:
        return Layout(
            *self.fields.keys(), FormActions(self.save_label, self.cancel_url)
        )

    def marks(self) -> dict[int, str]:
        return {
            int(name.removeprefix(PREFIX)): status
            for name, status in self.cleaned_data.items()
        }
