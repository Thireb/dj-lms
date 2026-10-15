"""Assignment form (SPEC 4.16), the student's answer form and the
teacher's grade form (roadmap 5.1)."""

from __future__ import annotations

from datetime import time
from decimal import Decimal
from typing import Any

from crispy_forms.layout import Layout
from django import forms

from apps.academics.models import Batch, Subject, TeacherBatchSubject
from apps.assessments.models import MAX_TOTAL_MARKS, Assignment
from apps.lectures.times import combine_local, missing_time_message, wall_time_missing
from apps.people.models import TeacherProfile
from apps.ui.forms.base import BaseForm, FormActions, Section
from apps.ui.forms.widgets import DatePicker, TimePicker

DEFAULT_DUE_TIME = time(23, 59)


class BatchSubjectField(forms.ChoiceField):
    """One of the teacher's subjects, grouped by batch; values are
    "batch:subject". Offers the active pairs the teacher is linked to, plus
    the assignment's own pair on edit."""

    def __init__(
        self,
        *args: Any,
        links: list[TeacherBatchSubject],
        kept: tuple | None,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._pairs: dict[str, tuple[Batch, Subject]] = {}
        groups: dict[str, list[tuple[str, str]]] = {}
        for link in links:
            batch, subject = link.batch, link.subject
            pair = (batch.pk, subject.pk)
            if not (batch.is_active and subject.is_active) and pair != kept:
                continue
            value = f"{batch.pk}:{subject.pk}"
            self._pairs[value] = (batch, subject)
            groups.setdefault(batch.name, []).append((value, subject.name))
        self.choices = [("", "Choose a subject")] + list(groups.items())

    def selection(self, value: str) -> tuple[Batch, Subject]:
        return self._pairs[value]


class AssignmentForm(BaseForm):
    title = forms.CharField(label="Title", max_length=200)
    instructions = forms.CharField(
        label="Instructions", widget=forms.Textarea(attrs={"rows": 6})
    )
    total_marks = forms.IntegerField(
        label="Total marks", min_value=1, max_value=MAX_TOTAL_MARKS, initial=10
    )
    due_date = forms.DateField(label="Due date", widget=DatePicker())
    due_time = forms.TimeField(
        label="Due time",
        widget=TimePicker(),
        initial=DEFAULT_DUE_TIME,
        help_text="Answers are taken until this time.",
    )

    def __init__(
        self,
        *args: Any,
        user: Any,
        teacher: TeacherProfile,
        cancel_url: str,
        save_label: str,
        assignment: Assignment | None = None,
        **kwargs: Any,
    ):
        self.cancel_url = cancel_url
        self.save_label = save_label
        super().__init__(*args, **kwargs)
        links = (
            TeacherBatchSubject.objects.for_user(user)
            .filter(teacher=teacher)
            .select_related("batch", "subject")
            .order_by("batch__name", "subject__name")
        )
        kept = (assignment.batch_id, assignment.subject_id) if assignment else None
        self.fields["batch_subject"] = BatchSubjectField(
            label="Batch and subject",
            links=list(links),
            kept=kept,
            help_text="Students of this batch who take this subject get it.",
        )
        self.fields["batch_subject"].widget.attrs["class"] = "field-control"
        self.helper.layout = self.get_layout()

    def get_layout(self) -> Layout:
        return Layout(
            Section("Assignment", "title", "instructions"),
            Section("Class", "batch_subject"),
            Section(
                "Marks and due time",
                "total_marks",
                "due_date",
                "due_time",
                description="Times are in your time zone.",
            ),
            FormActions(self.save_label, self.cancel_url),
        )

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()
        day, at = cleaned.get("due_date"), cleaned.get("due_time")
        if day is not None and at is not None:
            local = combine_local(day, at)
            if wall_time_missing(local):
                self.add_error("due_time", missing_time_message(local))
            else:
                cleaned["due_at"] = local
        return cleaned

    def selection(self) -> tuple[Batch, Subject]:
        field = self.fields["batch_subject"]
        return field.selection(self.cleaned_data["batch_subject"])


class AnswerForm(BaseForm):
    answer = forms.CharField(
        label="Your answer", widget=forms.Textarea(attrs={"rows": 8})
    )

    def __init__(self, *args: Any, save_label: str, cancel_url: str, **kwargs: Any):
        self.save_label = save_label
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)

    def get_layout(self) -> Layout:
        return Layout(
            Section(
                "",
                "answer",
                description="You can change it until the due time.",
            ),
            FormActions(self.save_label, self.cancel_url),
        )


class GradeForm(BaseForm):
    save_label = "Save grade"
    feedback = forms.CharField(
        label="Feedback",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="The student sees it with the marks.",
    )

    def __init__(self, *args: Any, total_marks: int, cancel_url: str, **kwargs: Any):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)
        self.fields["marks"] = forms.DecimalField(
            label=f"Marks (out of {total_marks})",
            min_value=Decimal(0),
            max_value=Decimal(total_marks),
            max_digits=5,
            decimal_places=1,
            widget=forms.NumberInput(attrs={"step": "0.5", "class": "field-control"}),
        )
        self.order_fields(["marks", "feedback"])
        self.helper.layout = self.get_layout()

    def get_layout(self) -> Layout:
        return Layout(
            Section("", "marks", "feedback"),
            FormActions(self.save_label, self.cancel_url),
        )
