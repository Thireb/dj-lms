"""Demo people and academics for seed_demo (roadmap 2.8, SPEC 10). Fake data only.

Everything is created through the real services, so the demo follows the
same rules as the app. Running it twice creates nothing new.
"""

from __future__ import annotations

from apps.academics.models import (
    Batch,
    ClassLabel,
    StudentBatchSubject,
    Subject,
    TeacherBatchSubject,
)
from apps.accounts.models import User
from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute
from apps.people.models import (
    CodeSequence,
    GuardianProfile,
    GuardianStudentLink,
    PortalAccessRule,
    StudentProfile,
    TeacherProfile,
)
from apps.people.services import (
    StudentDetails,
    create_teacher,
    enrol_student,
    set_portal_blocked,
    set_portal_exempt,
    set_student_active,
)

CLASS_NAMES = ("Grade 8", "Grade 9", "Grade 10")
BATCH_NAMES = ("Morning", "Afternoon", "Evening", "Weekend")
SUBJECT_NAMES = ("Mathematics", "Physics", "Chemistry", "Biology", "English", "Urdu")
FIRST_NAMES = (
    "Aiza", "Bilal", "Dua", "Faris", "Hiba", "Imran", "Kinza", "Moiz", "Noor",
    "Omer", "Rida", "Saad", "Tania", "Umar", "Warda", "Yasir", "Zoya",
)  # fmt: skip
LAST_NAMES = ("Sample", "Example", "Demo", "Fakeson", "Testwala", "Placeholder")

TEACHER_COUNT = 5
STUDENT_COUNT = 52
ACTIVE_STUDENTS = 30
GUARDIAN_COUNT = 20

DEMO_TEACHER_EMAIL = "demo-teacher@example.com"
DEMO_STUDENT_EMAIL = "demo-student@example.com"
DEMO_GUARDIAN_EMAIL = "demo-guardian@example.com"


def _name(number: int) -> str:
    first = FIRST_NAMES[number % len(FIRST_NAMES)]
    last = LAST_NAMES[number % len(LAST_NAMES)]
    return f"{first} {last}"


def _phone(number: int) -> str:
    return f"0300-{number:07d}"


def teacher_email(number: int) -> str:
    return DEMO_TEACHER_EMAIL if number == 1 else f"demo-teacher-{number}@example.com"


def student_email(number: int) -> str:
    if number == 1:
        return DEMO_STUDENT_EMAIL
    return f"demo-student-{number:02d}@example.com"


def guardian_number(student_number: int) -> int:
    """Guardian 1 has exactly two children (students 1 and 2); 19 share the rest."""
    if student_number <= 2:
        return 1
    return 2 + (student_number - 3) % (GUARDIAN_COUNT - 1)


def guardian_email(number: int) -> str:
    if number == 1:
        return DEMO_GUARDIAN_EMAIL
    return f"demo-guardian-{number:02d}@example.com"


def _lists(institute: Institute, model: type, names: tuple[str, ...]) -> list:
    return [
        model.objects.get_or_create(institute=institute, name=name)[0] for name in names
    ]


def seed_people(institute: Institute, password: str) -> None:
    """Create the SPEC 10 lists and people that do not exist yet."""
    with tenant_context(institute):
        classes = _lists(institute, ClassLabel, CLASS_NAMES)
        batches = _lists(institute, Batch, BATCH_NAMES)
        subjects = _lists(institute, Subject, SUBJECT_NAMES)
        for number in range(1, TEACHER_COUNT + 1):
            _seed_teacher(institute, number, password, batches, subjects)
        for number in range(1, STUDENT_COUNT + 1):
            _seed_student(institute, number, password, classes, batches, subjects)
        _seed_access(institute)


def _existing_profile(model: type, email: str):
    return model.objects.filter(user__email=email).first()


def _take_over_user(email: str) -> None:
    # A Phase 1 demo user without a profile: remove it so the service can
    # create the account again with the profile.
    User.objects.filter(
        email=email,
        teacher_profile__isnull=True,
        student_profile__isnull=True,
        guardian_profile__isnull=True,
    ).delete()


def _seed_teacher(institute, number, password, batches, subjects) -> None:
    email = teacher_email(number)
    if _existing_profile(TeacherProfile, email):
        return
    _take_over_user(email)
    first, second = batches[number % 4], batches[(number + 1) % 4]
    taught = [subjects[number % 6], subjects[(number + 2) % 6]]
    create_teacher(
        institute,
        full_name=_name(number + 100),
        email=email,
        password=password,
        phone=_phone(1000 + number),
        selections={first: taught, second: taught[:1]},
    )


def _seed_student(institute, number, password, classes, batches, subjects) -> None:
    email = student_email(number)
    if _existing_profile(StudentProfile, email):
        return
    _take_over_user(email)
    guardian = guardian_number(number)
    _take_over_user(guardian_email(guardian))
    batch = batches[number % 4]
    studied = [subjects[number % 6], subjects[(number + 1) % 6]]
    student = enrol_student(
        institute,
        StudentDetails(
            full_name=_name(number),
            phone=_phone(2000 + number),
            guardian_phone=_phone(3000 + guardian),
            father_name=_name(guardian + 200),
            class_label=classes[number % 3],
            address=f"House {number}, Street {number % 9 + 1}",
            city="Lahore",
        ),
        email=email,
        password=password,
        selections={batch: studied},
        guardian_name=_name(guardian + 200),
        guardian_email=guardian_email(guardian),
        guardian_password=password,
    )
    if number > ACTIVE_STUDENTS:
        set_student_active(student, is_active=False)


def _seed_access(institute: Institute) -> None:
    # Show 2.7: one blocked student and one exempt student, both active.
    by_email = StudentProfile.objects.filter(institute=institute)
    blocked = by_email.filter(user__email=student_email(5)).first()
    exempt = by_email.filter(user__email=student_email(6)).first()
    if blocked is not None:
        set_portal_blocked(blocked, blocked=True)
    if exempt is not None:
        set_portal_exempt(exempt, exempt=True)


def reset_people(institute: Institute) -> int:
    """Delete the institute's people and lists, children before parents.

    Uses ``unscoped`` on purpose: a management command, one institute.
    """
    deleted = 0
    for model in (
        PortalAccessRule,
        StudentBatchSubject,
        TeacherBatchSubject,
        GuardianStudentLink,
        StudentProfile,
        TeacherProfile,
        GuardianProfile,
        CodeSequence,
        ClassLabel,
        Batch,
        Subject,
    ):
        # unscoped: seed_demo --reset, limited to the demo institute.
        count, _ = model.unscoped.filter(institute=institute).delete()
        deleted += count
    return deleted
