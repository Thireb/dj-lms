"""Forms for the academics lists (SPEC 4.3) and the batch-subject picker."""

from __future__ import annotations

from django import forms

from apps.academics.models import Batch, Subject
from apps.academics.services import Selections
from apps.ui.forms.base import BaseForm
from apps.ui.forms.widgets import GroupedCheckboxes


class NameRowForm(BaseForm):
    name = forms.CharField(label="Name", max_length=100)

    def __init__(self, *args, save_label: str, cancel_url: str, **kwargs):
        self.save_label = save_label
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)


class BatchSubjectField(forms.MultipleChoiceField):
    """(batch, subject) checkboxes grouped by batch; values are "batch:subject".

    Offers active batches and subjects the user may see, plus any pair the
    person already has (so an inactive pair can stay on edit).
    """

    widget = GroupedCheckboxes(empty_text="Add batches and subjects first.")
    default_error_messages = {
        **forms.MultipleChoiceField.default_error_messages,
        "required": "Choose at least one batch.",
    }

    def __init__(self, *args, user: object, current: Selections | None = None, **kw):
        super().__init__(*args, **kw)
        current = current or {}
        batches = list(Batch.objects.for_user(user).order_by("name"))
        subjects = list(Subject.objects.for_user(user).order_by("name"))
        self._batches = {batch.pk: batch for batch in batches}
        self._subjects = {subject.pk: subject for subject in subjects}
        kept = {
            (batch.pk, subject.pk)
            for batch, chosen in current.items()
            for subject in chosen
        }
        self.choices = [
            (
                batch.name,
                [
                    (f"{batch.pk}:{subject.pk}", subject.name)
                    for subject in subjects
                    if (batch.is_active and subject.is_active)
                    or (batch.pk, subject.pk) in kept
                ],
            )
            for batch in batches
        ]
        self.choices = [group for group in self.choices if group[1]]
        self.initial = sorted(f"{b}:{s}" for b, s in kept)

    def selections(self, values: list[str]) -> dict[Batch, list[Subject]]:
        """Turn validated "batch:subject" values into a mapping for services."""
        chosen: dict[Batch, list[Subject]] = {}
        for value in values:
            batch_id, subject_id = (int(part) for part in value.split(":"))
            batch = self._batches[batch_id]
            chosen.setdefault(batch, []).append(self._subjects[subject_id])
        return chosen
