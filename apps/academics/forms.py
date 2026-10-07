"""Form for the class, batch and subject lists (SPEC 4.3)."""

from __future__ import annotations

from django import forms

from apps.ui.forms.base import BaseForm


class NameRowForm(BaseForm):
    name = forms.CharField(label="Name", max_length=100)

    def __init__(self, *args, save_label: str, cancel_url: str, **kwargs):
        self.save_label = save_label
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)
