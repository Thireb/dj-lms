from django import forms


class DatePicker(forms.DateInput):
    template_name = "ui/forms/widgets/date_picker.html"
    input_type = "date"

    def __init__(self, attrs=None):
        default_attrs = {
            "class": (
                "mt-1 block w-full rounded-lg border border-border "
                "px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-primary"
            ),
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class TimePicker(forms.TimeInput):
    template_name = "ui/forms/widgets/time_picker.html"
    input_type = "time"

    def __init__(self, attrs=None):
        default_attrs = {
            "class": (
                "mt-1 block w-full rounded-lg border border-border "
                "px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-primary"
            ),
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class PasswordInput(forms.PasswordInput):
    template_name = "ui/forms/widgets/password_input.html"

    def __init__(self, attrs=None):
        default_attrs = {
            "class": (
                "mt-1 block w-full rounded-lg border border-border "
                "px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-primary"
            ),
            "autocomplete": "current-password",
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class MoneyInput(forms.NumberInput):
    template_name = "ui/forms/widgets/money_input.html"

    def __init__(self, attrs=None):
        default_attrs = {
            "class": (
                "mt-1 block w-full rounded-lg border border-border "
                "px-3 py-2 text-right font-mono text-sm "
                "focus-visible:ring-2 focus-visible:ring-primary"
            ),
            "step": "0.01",
            "min": "0",
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class GroupedCheckboxes(forms.CheckboxSelectMultiple):
    """Checkboxes in one fieldset per choice group (for example one per batch)."""

    template_name = "ui/forms/widgets/grouped_checkboxes.html"

    def __init__(self, attrs=None, empty_text: str = "Nothing to choose yet."):
        super().__init__(attrs=attrs)
        self.empty_text = empty_text

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["empty_text"] = self.empty_text
        return context
