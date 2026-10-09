"""Teacher (SPEC 4.2) and student (SPEC 4.1) forms."""

from __future__ import annotations

from crispy_forms.layout import Layout
from django import forms

from apps.academics.forms import BatchSubjectField
from apps.academics.models import ClassLabel
from apps.academics.services import Selections
from apps.people.models import Gender, cnic_validator
from apps.ui.forms.base import BaseForm
from apps.ui.forms.layout import FormActions, Section
from apps.ui.forms.widgets import DatePicker, PasswordInput


def _cnic_field() -> forms.CharField:
    return forms.CharField(
        label="CNIC",
        max_length=13,
        required=False,
        validators=[cnic_validator],
        help_text="13 digits, no dashes.",
    )


def _password_field(label: str, required: bool = True, help_text: str = ""):
    return forms.CharField(
        label=label,
        required=required,
        help_text=help_text,
        widget=PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
    )


class PersonForm(BaseForm):
    """Adds the batch-subject picker, scoped to the signed-in admin."""

    save_label = "Save changes"

    def __init__(
        self,
        *args,
        user: object,
        cancel_url: str,
        current: Selections | None = None,
        **kwargs,
    ):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)
        self.fields["batch_subjects"] = BatchSubjectField(
            label="Batches and subjects", user=user, current=current
        )

    def selections(self) -> Selections:
        field = self.fields["batch_subjects"]
        return field.selections(self.cleaned_data["batch_subjects"])


class TeacherForm(PersonForm):
    """Edit form; the create form adds the password."""

    full_name = forms.CharField(label="Full name", max_length=300)
    phone = forms.CharField(label="Phone", max_length=32)
    email = forms.EmailField(label="Email (sign-in)")
    cnic = _cnic_field()
    address = forms.CharField(label="Address", required=False, widget=forms.Textarea)
    joining_date = forms.DateField(
        label="Joining date", required=False, widget=DatePicker()
    )

    def personal_fields(self) -> list[str]:
        return ["full_name", "phone", "email", "cnic", "address", "joining_date"]

    def get_layout(self):
        return Layout(
            Section(
                "Personal and sign-in",
                *self.personal_fields(),
                description="The email is the sign-in name for the teacher portal.",
                columns=2,
            ),
            Section(
                "Teaching",
                "batch_subjects",
                description="The batches and subjects this teacher takes.",
            ),
            FormActions(self.save_label, self.cancel_url),
        )


class TeacherCreateForm(TeacherForm):
    save_label = "Add teacher"

    password = _password_field("Password")

    def personal_fields(self) -> list[str]:
        return [*super().personal_fields(), "password"]


class StudentForm(PersonForm):
    """Edit form; the enrol form adds the passwords and the guardian."""

    full_name = forms.CharField(label="Full name", max_length=300)
    father_name = forms.CharField(label="Father name", max_length=150, required=False)
    cnic = _cnic_field()
    date_of_birth = forms.DateField(
        label="Date of birth", required=False, widget=DatePicker()
    )
    gender = forms.ChoiceField(
        label="Gender", required=False, choices=[("", "---------"), *Gender.choices]
    )
    class_label = forms.ModelChoiceField(
        label="Class", required=False, queryset=ClassLabel.objects.none()
    )
    phone = forms.CharField(label="Student phone", max_length=32, required=False)
    guardian_phone = forms.CharField(label="Guardian phone", max_length=32)
    address = forms.CharField(label="Address", required=False, widget=forms.Textarea)
    city = forms.CharField(label="City", max_length=100, required=False)
    email = forms.EmailField(label="Student email (sign-in)")

    def __init__(self, *args, current_label: ClassLabel | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        user = kwargs["user"]
        labels = ClassLabel.objects.for_user(user).filter(is_active=True)
        if current_label is not None:
            labels = labels | ClassLabel.objects.for_user(user).filter(
                pk=current_label.pk
            )
        self.fields["class_label"].queryset = labels.order_by("name")

    def login_fields(self) -> list[str]:
        return ["email"]

    def get_layout(self):
        return Layout(
            Section(
                "Personal",
                "full_name",
                "father_name",
                "cnic",
                "date_of_birth",
                "gender",
                "class_label",
                description="As written on official documents.",
                columns=2,
            ),
            Section(
                "Contact",
                "phone",
                "guardian_phone",
                "address",
                "city",
                description="How the institute reaches the student and family.",
                columns=2,
            ),
            Section(
                "Academic",
                "batch_subjects",
                description="The batches and subjects this student studies.",
            ),
            Section(
                "Sign-in",
                *self.login_fields(),
                description="Portal sign-in for the student and the guardian.",
            ),
            FormActions(self.save_label, self.cancel_url),
        )


class StudentEnrolForm(StudentForm):
    save_label = "Enrol student"

    password = _password_field("Student password")
    guardian_name = forms.CharField(label="Guardian name", max_length=300)
    guardian_email = forms.EmailField(label="Guardian email (sign-in)")
    guardian_password = _password_field(
        "Guardian password",
        required=False,
        help_text="Leave blank if this guardian already has an account.",
    )

    def login_fields(self) -> list[str]:
        return [
            "email",
            "password",
            "guardian_name",
            "guardian_email",
            "guardian_password",
        ]


class StudentUploadForm(BaseForm):
    """Bulk upload step 1 (SPEC 5). The service reads and checks the rows."""

    save_label = "Check file"

    file = forms.FileField(
        label="Excel file (.xlsx)",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}),
    )

    def __init__(self, *args, cancel_url: str, **kwargs):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not upload.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Upload an .xlsx file made from the template.")
        return upload
