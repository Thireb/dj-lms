"""Fee forms (Phase 7)."""

from __future__ import annotations

from decimal import Decimal

from crispy_forms.layout import Layout
from django import forms

from apps.finance.models import MAX_AMOUNT
from apps.ui.forms.base import BaseForm, FormActions, Section
from apps.ui.forms.widgets import MoneyInput


class FeePlanForm(BaseForm):
    """SPEC 4.4: Name*, Amount* (more than 0). Status is the Activate or
    Deactivate action on the edit page."""

    name = forms.CharField(label="Name", max_length=100)
    amount = forms.DecimalField(
        label="Monthly amount",
        min_value=Decimal("0.01"),
        max_value=MAX_AMOUNT,
        decimal_places=2,
        widget=MoneyInput,
    )

    def __init__(self, *args, save_label: str, cancel_url: str, **kwargs):
        self.save_label = save_label
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)

    def get_layout(self) -> Layout:
        return Layout(
            Section(
                "Fee plan",
                "name",
                "amount",
                description="A monthly fee that students can have, such as Tuition.",
                columns=2,
            ),
            FormActions(self.save_label, self.cancel_url),
        )
