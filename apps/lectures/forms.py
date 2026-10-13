"""Add and edit lecture form (SPEC 4.5)."""

from __future__ import annotations

from typing import Any

from crispy_forms.layout import Layout
from django import forms
from django.db.models import Q

from apps.academics.models import Batch, Subject, TeacherBatchSubject
from apps.core.query import id_param
from apps.lectures.models import (
    MAX_DURATION,
    MIN_DURATION,
    DeliveryMode,
    Lecture,
    meeting_url_validator,
)
from apps.people.models import ProfileStatus, TeacherProfile
from apps.ui.forms.base import BaseForm
from apps.ui.forms.layout import FormActions, Section
from apps.ui.forms.widgets import DatePicker, GroupedCheckboxes, TimePicker

PAIRS_ID = "id_batch_subjects"


class LectureSubjectsField(forms.MultipleChoiceField):
    """The teacher's subjects, grouped by batch; values are "batch:subject".

    Offers active pairs the teacher is linked to, plus the lecture's own
    pairs on edit. A lecture has one batch, so all choices must share it.
    """

    widget = GroupedCheckboxes(empty_text="Choose a teacher to see their batches.")
    default_error_messages = {
        **forms.MultipleChoiceField.default_error_messages,
        "required": "Choose at least one subject.",
    }

    def __init__(self, *args, links: list[TeacherBatchSubject], kept: set, **kwargs):
        super().__init__(*args, **kwargs)
        self._batches: dict[int, Batch] = {}
        self._subjects: dict[int, Subject] = {}
        groups: dict[Batch, list[tuple[str, str]]] = {}
        for link in links:
            batch, subject = link.batch, link.subject
            pair = (batch.pk, subject.pk)
            if not (batch.is_active and subject.is_active) and pair not in kept:
                continue
            self._batches[batch.pk] = batch
            self._subjects[subject.pk] = subject
            groups.setdefault(batch, []).append((f"{pair[0]}:{pair[1]}", subject.name))
        self.choices = [(batch.name, options) for batch, options in groups.items()]

    def validate(self, value: list[str]) -> None:
        super().validate(value)
        if len({item.split(":")[0] for item in value}) > 1:
            raise forms.ValidationError("Choose subjects from one batch only.")

    def selection(self, values: list[str]) -> tuple[Batch, list[Subject]]:
        pairs = [tuple(int(part) for part in value.split(":")) for value in values]
        batch = self._batches[pairs[0][0]]
        return batch, [self._subjects[subject_id] for _, subject_id in pairs]


class LectureForm(BaseForm):
    title = forms.CharField(label="Title", max_length=200)
    date = forms.DateField(label="Date", widget=DatePicker())
    start_time = forms.TimeField(label="Start time", widget=TimePicker())
    duration_minutes = forms.IntegerField(
        label="Duration (minutes)",
        min_value=MIN_DURATION,
        max_value=MAX_DURATION,
        initial=60,
    )
    delivery_mode = forms.ChoiceField(
        label="Delivery mode",
        choices=DeliveryMode.choices,
        initial=DeliveryMode.MANUAL_LINK,
    )
    meeting_url = forms.URLField(
        label="Meeting link",
        required=False,
        max_length=500,
        assume_scheme="https",
        validators=[meeting_url_validator],
        help_text="Needed for an online lecture. Paste the full link.",
    )
    description = forms.CharField(
        label="Description", required=False, widget=forms.Textarea
    )

    def __init__(
        self,
        *args: Any,
        user: Any,
        cancel_url: str,
        save_label: str,
        lecture: Lecture | None = None,
        teacher: TeacherProfile | None = None,
        teacher_param: str | None = None,
        refresh_url: str = "",
        **kwargs: Any,
    ):
        """``teacher`` fixes the teacher (teacher portal); without it the
        form has a teacher choice (admin portal). Changing the teacher
        reloads the subject choices from ``refresh_url`` (this page)."""
        self.user = user
        self.cancel_url = cancel_url
        self.save_label = save_label
        self.fixed_teacher = teacher
        self.lecture = lecture
        self.refresh_url = refresh_url
        super().__init__(*args, **kwargs)
        if teacher is None:
            self.fields["teacher"] = self.teacher_field()
        self.fields["batch_subjects"] = LectureSubjectsField(
            label="Batch and subjects",
            links=self.teacher_links(self.chosen_teacher(teacher_param)),
            kept=self.lecture_pairs(),
            help_text="Pick one or more subjects from one batch.",
        )

    def teacher_field(self) -> forms.ModelChoiceField:
        offered = Q(status=ProfileStatus.ACTIVE)
        if self.lecture is not None:
            offered |= Q(pk=self.lecture.teacher_id)  # may stay if inactive
        teachers = (
            TeacherProfile.objects.for_user(self.user)
            .filter(offered)
            .select_related("user")
            .order_by("user__first_name", "user__last_name", "pk")
        )
        field = forms.ModelChoiceField(label="Teacher", queryset=teachers)
        field.widget.attrs.update(
            {
                "hx-get": self.refresh_url,
                "hx-trigger": "change",
                "hx-include": "this",
                "hx-select": f"#{PAIRS_ID}",
                "hx-target": f"#{PAIRS_ID}",
                "hx-swap": "outerHTML",
            }
        )
        return field

    def chosen_teacher(self, teacher_param: str | None) -> TeacherProfile | None:
        if self.fixed_teacher is not None:
            return self.fixed_teacher
        if self.is_bound:
            teacher_id = id_param(self.data.get("teacher"))
        elif teacher_param is not None:
            teacher_id = id_param(teacher_param)
        else:
            teacher_id = self.lecture.teacher_id if self.lecture else None
        if teacher_id is None:
            return None
        return self.fields["teacher"].queryset.filter(pk=teacher_id).first()

    def teacher_links(self, teacher: TeacherProfile | None) -> list[Any]:
        if teacher is None:
            return []
        return list(
            TeacherBatchSubject.objects.for_user(self.user)
            .filter(teacher=teacher)
            .select_related("batch", "subject")
            .order_by("batch__name", "subject__name")
        )

    def lecture_pairs(self) -> set[tuple[int, int]]:
        if self.lecture is None:
            return set()
        return {
            (self.lecture.batch_id, subject.pk)
            for subject in self.lecture.subjects.all()
        }

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()
        mode = cleaned.get("delivery_mode")
        if mode == DeliveryMode.MANUAL_LINK and not cleaned.get("meeting_url"):
            self.add_error(
                "meeting_url", "Paste the meeting link for an online lecture."
            )
        if mode == DeliveryMode.IN_PERSON:
            cleaned["meeting_url"] = ""
        return cleaned

    def teacher(self) -> TeacherProfile:
        return self.fixed_teacher or self.cleaned_data["teacher"]

    def selection(self) -> tuple[Batch, list[Subject]]:
        field = self.fields["batch_subjects"]
        return field.selection(self.cleaned_data["batch_subjects"])

    def get_layout(self) -> Layout:
        who = [] if self.fixed_teacher else ["teacher"]
        return Layout(
            Section(
                "Lecture",
                "title",
                "description",
                description="What students see in their lecture list.",
            ),
            Section(
                "Teaching",
                *who,
                "batch_subjects",
                description="Only the batches and subjects the teacher is "
                "assigned to are offered.",
            ),
            Section(
                "Date and time",
                "date",
                "start_time",
                "duration_minutes",
                description="In your time zone. Students see it in theirs.",
                columns=2,
            ),
            Section(
                "Delivery",
                "delivery_mode",
                "meeting_url",
                description="Online lectures need a meeting link from any "
                "service, for example Google Meet or Jitsi.",
            ),
            FormActions(self.save_label, self.cancel_url),
        )
