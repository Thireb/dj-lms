"""Fee forms (Phase 7)."""

from __future__ import annotations

from decimal import Decimal

from crispy_forms.layout import Layout
from django import forms

from apps.academics.models import Batch
from apps.finance.models import MAX_AMOUNT, PaymentMethod
from apps.ui.forms.base import BaseForm, FormActions, Section
from apps.ui.forms.widgets import DatePicker, GroupedCheckboxes, MoneyInput


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


class ChallanGenerateForm(BaseForm):
    """SPEC 4.7: Month*, Due date* (default from settings), Students: all
    active or a batch. The preview then lets you untick students."""

    save_label = "Show preview"

    month = forms.DateField(
        label="Month",
        input_formats=["%Y-%m"],
        widget=forms.DateInput(attrs={"type": "month"}, format="%Y-%m"),
    )
    due_date = forms.DateField(
        label="Due date",
        required=False,
        widget=DatePicker(),
        help_text="Empty: the fee due day from the institute settings.",
    )
    scope = forms.ChoiceField(
        label="Students",
        choices=[("all", "All active students"), ("batch", "One batch")],
        initial="all",
    )
    batch = forms.ModelChoiceField(
        label="Batch", queryset=Batch.objects.none(), required=False
    )

    def __init__(self, *args, batches, cancel_url, **kwargs):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)
        self.fields["batch"].queryset = batches

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("scope") == "batch" and not cleaned.get("batch"):
            self.add_error("batch", "Choose the batch.")
        return cleaned

    def get_layout(self) -> Layout:
        return Layout(
            Section(
                "Challans",
                "month",
                "due_date",
                description="The month the challans bill, and when they are due.",
                columns=2,
            ),
            Section(
                "Students",
                "scope",
                "batch",
                description="Students with a challan for the month, or no fee plan, "
                "are skipped and listed.",
                columns=2,
            ),
            FormActions(self.save_label, self.cancel_url),
        )


class ChallanConfirmForm(BaseForm):
    """The preview step: every planned student ticked; untick to leave one
    out. Month and due date ride along from step 1."""

    save_label = "Generate challans"

    month = forms.DateField(input_formats=["%Y-%m-%d"], widget=forms.HiddenInput)
    due_date = forms.DateField(input_formats=["%Y-%m-%d"], widget=forms.HiddenInput)
    students = forms.TypedMultipleChoiceField(
        label="Students",
        coerce=int,
        widget=GroupedCheckboxes(empty_text="No student gets a challan."),
        error_messages={"required": "Tick at least one student."},
    )

    def __init__(self, *args, choices, cancel_url, **kwargs):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)
        self.fields["students"].choices = choices

    def get_layout(self) -> Layout:
        return Layout(
            "month",
            "due_date",
            Section(None, "students"),
            FormActions(self.save_label, self.cancel_url),
        )


class PaymentForm(BaseForm):
    """SPEC 4.8: Amount* (up to the balance), Date*, Method*, Reference,
    Note. The challan comes from the Process payment search."""

    save_label = "Record payment"

    amount = forms.DecimalField(
        label="Amount", min_value=Decimal("0.01"), decimal_places=2, widget=MoneyInput
    )
    paid_on = forms.DateField(label="Paid on", widget=DatePicker())
    method = forms.ChoiceField(label="Method", choices=PaymentMethod.choices)
    reference = forms.CharField(
        label="Reference",
        max_length=100,
        required=False,
        help_text="A bank or transfer reference, if any.",
    )
    note = forms.CharField(label="Note", max_length=300, required=False)

    def __init__(self, *args, cancel_url, **kwargs):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)

    def get_layout(self) -> Layout:
        return Layout(
            Section(
                "Payment",
                "amount",
                "paid_on",
                "method",
                "reference",
                "note",
                description="Partial payments are allowed, up to the balance.",
                columns=2,
            ),
            FormActions(self.save_label, self.cancel_url),
        )


class ReceiptForm(BaseForm):
    """SPEC 4.17 Fee pay: the child's open challans, Amount* (default = their
    balance), Paid on*, Reference, Receipt file*. The child is the one chosen
    in the header."""

    save_label = "Send receipt"

    challans = forms.TypedMultipleChoiceField(
        label="Challans",
        coerce=int,
        widget=GroupedCheckboxes(empty_text="No open challans."),
        error_messages={"required": "Choose at least one challan."},
    )
    amount = forms.DecimalField(
        label="Amount paid",
        min_value=Decimal("0.01"),
        decimal_places=2,
        widget=MoneyInput,
    )
    paid_on = forms.DateField(label="Paid on", widget=DatePicker())
    reference = forms.CharField(
        label="Reference",
        max_length=100,
        required=False,
        help_text="The bank or transfer reference, if any.",
    )
    file = forms.FileField(
        label="Receipt file",
        help_text="A photo or scan: JPG, PNG, WEBP or PDF, up to 5 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": ".jpg,.jpeg,.png,.webp,.pdf"}),
    )

    def __init__(self, *args, choices, cancel_url, **kwargs):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)
        self.fields["challans"].choices = choices

    def get_layout(self) -> Layout:
        return Layout(
            Section(
                "What you paid for",
                "challans",
                description="Tick the challans this payment covers.",
            ),
            Section(
                "Payment",
                "amount",
                "paid_on",
                "reference",
                "file",
                description="The office checks it and marks the challans paid.",
                columns=2,
            ),
            FormActions(self.save_label, self.cancel_url),
        )


class RejectReceiptForm(BaseForm):
    """SPEC 4.9: Reason* (short text, shown to the guardian)."""

    save_label = "Reject receipt"

    reason = forms.CharField(label="Reason", max_length=200)

    def __init__(self, *args, cancel_url=None, **kwargs):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)

    def get_layout(self) -> Layout:
        return Layout(
            Section(None, "reason"),
            FormActions(self.save_label, self.cancel_url),
        )
