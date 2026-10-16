"""Message forms (roadmap 6.3, SPEC 4.19)."""

from __future__ import annotations

from crispy_forms.layout import Layout
from django import forms

from apps.academics.models import Batch
from apps.messaging.models import MAX_BODY, MAX_SUBJECT, Audience
from apps.ui.forms.base import BaseForm, FormActions, Section


class ReplyForm(BaseForm):
    save_label = "Send reply"

    body = forms.CharField(
        label="Your reply",
        max_length=MAX_BODY,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def __init__(self, *args, cancel_url=None, **kwargs):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)

    def get_layout(self) -> Layout:
        return Layout(
            Section(None, "body"),
            FormActions(self.save_label, self.cancel_url),
        )


class ComposeForm(BaseForm):
    """A new message (SPEC 4.19). The recipient is chosen above the form, by
    search; ``to`` carries it. Send needs a body; Save draft does not."""

    save_label = "Send message"

    to = forms.IntegerField(required=False, widget=forms.HiddenInput)
    subject = forms.CharField(label="Subject", max_length=MAX_SUBJECT, required=False)
    body = forms.CharField(
        label="Message",
        max_length=MAX_BODY,
        required=False,
        widget=forms.Textarea(attrs={"rows": 8}),
    )

    def __init__(self, *args, cancel_url=None, **kwargs):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)

    def get_layout(self) -> Layout:
        return Layout(
            "to",
            Section(None, "subject", "body"),
            FormActions(
                self.save_label,
                self.cancel_url,
                save_name="send",
                second=("Save draft", "save_draft"),
            ),
        )


class BroadcastForm(BaseForm):
    """SPEC 4.19 admin broadcast: pick the audience (all, teachers,
    students, guardians, a batch)."""

    save_label = "Send broadcast"

    audience = forms.ChoiceField(label="Send to", choices=Audience.choices)
    batch = forms.ModelChoiceField(
        label="Batch",
        queryset=Batch.objects.none(),
        required=False,
        help_text='Only for "A batch": its students and their guardians.',
    )
    subject = forms.CharField(label="Subject", max_length=MAX_SUBJECT)
    body = forms.CharField(
        label="Message", max_length=MAX_BODY, widget=forms.Textarea(attrs={"rows": 8})
    )

    def __init__(self, *args, batches, cancel_url=None, **kwargs):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)
        self.fields["batch"].queryset = batches

    def get_layout(self) -> Layout:
        return Layout(
            Section("Who gets it", "audience", "batch", columns=2),
            Section("Message", "subject", "body"),
            FormActions(self.save_label, self.cancel_url),
        )
