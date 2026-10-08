"""Profiles, ID codes (STU-001, TCH-001), guardian links and teacher accounts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q, QuerySet

from apps.academics.models import ClassLabel, StudentBatchSubject, TeacherBatchSubject
from apps.academics.services import (
    Selections,
    set_student_batch_subjects,
    set_teacher_batch_subjects,
)
from apps.accounts.models import User
from apps.core.roles import Role
from apps.core.tenancy import require_tenant_context
from apps.institutes.models import Institute
from apps.people.models import (
    CodeSequence,
    GuardianProfile,
    GuardianStudentLink,
    ProfileStatus,
    StudentProfile,
    TeacherProfile,
)

STUDENT_CODE_PREFIX = "STU"
TEACHER_CODE_PREFIX = "TCH"


def next_code(institute: Institute, prefix: str) -> str:
    """Return the next code for the prefix. Numbers are never reused."""
    require_tenant_context(institute)
    with transaction.atomic():
        sequence, _ = CodeSequence.objects.select_for_update().get_or_create(
            institute=institute, prefix=prefix
        )
        sequence.last_number += 1
        sequence.save(update_fields=["last_number"])
    return f"{prefix}-{sequence.last_number:03d}"


@transaction.atomic
def create_student_profile(user: User, **fields: Any) -> StudentProfile:
    institute = user.institute
    code = next_code(institute, STUDENT_CODE_PREFIX)
    return StudentProfile.objects.create(
        institute=institute, user=user, student_code=code, **fields
    )


@transaction.atomic
def create_teacher_profile(user: User, **fields: Any) -> TeacherProfile:
    institute = user.institute
    code = next_code(institute, TEACHER_CODE_PREFIX)
    return TeacherProfile.objects.create(
        institute=institute, user=user, teacher_code=code, **fields
    )


def create_guardian_profile(user: User) -> GuardianProfile:
    require_tenant_context(user.institute)
    return GuardianProfile.objects.create(institute=user.institute, user=user)


EMAIL_TAKEN = "This email is already used by another account."
NEW_GUARDIAN_PASSWORD = "Enter a password for the new guardian."
SAME_EMAILS = "The student and guardian emails must be different."


@dataclass(frozen=True)
class GuardianEnrolment:
    guardian: GuardianProfile
    created: bool


@transaction.atomic
def enrol_guardian(
    student: StudentProfile,
    *,
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    phone: str = "",
) -> GuardianEnrolment:
    """Link the student to the guardian with this email, creating them if new.

    An existing guardian of the same institute is reused as is: the password,
    name and phone given here are ignored. Any other account with the email
    is an error that does not say which role or institute owns it.
    """
    institute = student.institute
    require_tenant_context(institute)
    email = email.strip().lower()
    existing = User.objects.filter(email__iexact=email).first()
    if existing is None:
        guardian = _create_guardian(
            institute,
            email=email,
            password=password,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            phone=phone.strip(),
        )
        created = True
    elif _is_guardian_of(existing, institute):
        guardian = GuardianProfile.objects.filter(
            user=existing
        ).first() or create_guardian_profile(existing)
        created = False
    else:
        raise ValidationError({"guardian_email": EMAIL_TAKEN})
    GuardianStudentLink.objects.get_or_create(
        institute=institute, guardian=guardian, student=student
    )
    return GuardianEnrolment(guardian=guardian, created=created)


def _is_guardian_of(user: User, institute: Institute) -> bool:
    is_guardian = user.role == Role.GUARDIAN
    return is_guardian and user.institute_id == institute.pk


def _create_guardian(
    institute: Institute, *, email: str, password: str, **fields: str
) -> GuardianProfile:
    if not password:
        raise ValidationError({"guardian_password": NEW_GUARDIAN_PASSWORD})
    user = User(email=email, role=Role.GUARDIAN, institute=institute, **fields)
    try:
        validate_password(password, user)
    except ValidationError as error:
        raise ValidationError({"guardian_password": error.messages}) from error
    user = User.objects.create_user(
        email=email,
        password=password,
        role=Role.GUARDIAN,
        institute=institute,
        **fields,
    )
    return create_guardian_profile(user)


# Teachers (roadmap 2.5a, SPEC 4.2)


def list_teachers(
    user: object,
    *,
    search: str = "",
    batch_id: int | None = None,
    status: str = "",
) -> QuerySet[TeacherProfile]:
    """The user's teachers, newest first, with links prefetched for the table."""
    teachers = TeacherProfile.objects.for_user(user).select_related("user")
    for term in search.split():
        teachers = teachers.filter(
            Q(user__first_name__icontains=term)
            | Q(user__last_name__icontains=term)
            | Q(user__email__icontains=term)
            | Q(user__phone__icontains=term)
            | Q(teacher_code__icontains=term)
        )
    if batch_id is not None:
        teachers = teachers.filter(batch_subjects__batch_id=batch_id).distinct()
    if status in ProfileStatus.values:
        teachers = teachers.filter(status=status)
    links = TeacherBatchSubject.objects.select_related("batch", "subject")
    return teachers.prefetch_related(
        Prefetch("batch_subjects", queryset=links)
    ).order_by("-created_at", "-pk")


def split_full_name(full_name: str) -> tuple[str, str]:
    """ "Sam A. Sample" -> ("Sam", "A. Sample"); the profile page edits both."""
    parts = " ".join(full_name.split()).split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def _check_email_free(email: str, field: str, user: User | None = None) -> str:
    email = email.strip().lower()
    taken = User.objects.filter(email__iexact=email)
    if user is not None:
        taken = taken.exclude(pk=user.pk)
    if taken.exists():
        raise ValidationError({field: EMAIL_TAKEN})
    return email


def _new_user(
    institute: Institute,
    role: str,
    *,
    email: str,
    password: str,
    full_name: str,
    phone: str,
) -> User:
    """A new account with a free email and a password that passes the rules."""
    email = _check_email_free(email, "email")
    first_name, last_name = split_full_name(full_name)
    user = User(
        email=email,
        role=role,
        institute=institute,
        first_name=first_name,
        last_name=last_name,
        phone=phone.strip(),
    )
    try:
        validate_password(password, user)
    except ValidationError as error:
        raise ValidationError({"password": error.messages}) from error
    user.set_password(password)
    user.save()
    return user


def _set_pairs(
    profile: StudentProfile | TeacherProfile, selections: Selections
) -> None:
    setter = (
        set_student_batch_subjects
        if isinstance(profile, StudentProfile)
        else set_teacher_batch_subjects
    )
    try:
        setter(profile, selections)
    except ValidationError as error:
        raise ValidationError({"batch_subjects": error.messages}) from error


def _set_active(profile: StudentProfile | TeacherProfile, *, is_active: bool) -> None:
    """Status and sign-in change together: an inactive person cannot sign in."""
    require_tenant_context(profile.institute)
    profile.status = ProfileStatus.ACTIVE if is_active else ProfileStatus.INACTIVE
    profile.save(update_fields=["status"])
    profile.user.is_active = is_active
    profile.user.save(update_fields=["is_active"])


@transaction.atomic
def create_teacher(
    institute: Institute,
    *,
    full_name: str,
    email: str,
    password: str,
    phone: str,
    selections: Selections,
    cnic: str = "",
    address: str = "",
    joining_date: date | None = None,
) -> TeacherProfile:
    require_tenant_context(institute)
    user = _new_user(
        institute,
        Role.TEACHER,
        email=email,
        password=password,
        full_name=full_name,
        phone=phone,
    )
    teacher = create_teacher_profile(
        user, cnic=cnic.strip(), address=address.strip(), joining_date=joining_date
    )
    _set_pairs(teacher, selections)
    return teacher


@transaction.atomic
def update_teacher(
    teacher: TeacherProfile,
    *,
    full_name: str,
    email: str,
    phone: str,
    selections: Selections,
    cnic: str = "",
    address: str = "",
    joining_date: date | None = None,
) -> TeacherProfile:
    require_tenant_context(teacher.institute)
    user = teacher.user
    user.email = _check_email_free(email, "email", user=user)
    user.first_name, user.last_name = split_full_name(full_name)
    user.phone = phone.strip()
    user.save()
    teacher.cnic = cnic.strip()
    teacher.address = address.strip()
    teacher.joining_date = joining_date
    teacher.save()
    _set_pairs(teacher, selections)
    return teacher


@transaction.atomic
def set_teacher_active(teacher: TeacherProfile, *, is_active: bool) -> TeacherProfile:
    _set_active(teacher, is_active=is_active)
    return teacher


# Students (roadmap 2.5b, SPEC 4.1). Fee plans wait for Phase 7.


@dataclass(frozen=True)
class StudentDetails:
    """Profile fields shared by enrol and edit (SPEC 4.1 personal and contact)."""

    full_name: str
    phone: str
    guardian_phone: str
    father_name: str = ""
    cnic: str = ""
    date_of_birth: date | None = None
    gender: str = ""
    class_label: ClassLabel | None = None
    address: str = ""
    city: str = ""


def list_students(
    user: object,
    *,
    search: str = "",
    batch_id: int | None = None,
    class_label_id: int | None = None,
    status: str = "",
) -> QuerySet[StudentProfile]:
    """The user's students, newest first, with links prefetched for the table."""
    students = StudentProfile.objects.for_user(user).select_related(
        "user", "class_label"
    )
    for term in search.split():
        students = students.filter(
            Q(user__first_name__icontains=term)
            | Q(user__last_name__icontains=term)
            | Q(user__email__icontains=term)
            | Q(user__phone__icontains=term)
            | Q(guardian_phone__icontains=term)
            | Q(student_code__icontains=term)
        )
    if batch_id is not None:
        students = students.filter(batch_subjects__batch_id=batch_id).distinct()
    if class_label_id is not None:
        students = students.filter(class_label_id=class_label_id)
    if status in ProfileStatus.values:
        students = students.filter(status=status)
    links = StudentBatchSubject.objects.select_related("batch", "subject")
    guardians = GuardianStudentLink.objects.select_related("guardian__user")
    return students.prefetch_related(
        Prefetch("batch_subjects", queryset=links),
        Prefetch("guardian_links", queryset=guardians),
    ).order_by("-created_at", "-pk")


def _apply_details(student: StudentProfile, details: StudentDetails) -> None:
    # StudentProfile.clean() rejects a class label of another institute.
    student.father_name = details.father_name.strip()
    student.cnic = details.cnic.strip()
    student.date_of_birth = details.date_of_birth
    student.gender = details.gender
    student.class_label = details.class_label
    student.guardian_phone = details.guardian_phone.strip()
    student.address = details.address.strip()
    student.city = details.city.strip()


@transaction.atomic
def enrol_student(
    institute: Institute,
    details: StudentDetails,
    *,
    email: str,
    password: str,
    selections: Selections,
    guardian_name: str,
    guardian_email: str,
    guardian_password: str,
) -> StudentProfile:
    """Create the student account, profile, links and guardian in one step.

    The guardian follows ``enrol_guardian``: an existing guardian of this
    institute is linked, a new one is created with the name and password.
    """
    require_tenant_context(institute)
    if email.strip().lower() == guardian_email.strip().lower():
        raise ValidationError({"guardian_email": SAME_EMAILS})
    user = _new_user(
        institute,
        Role.STUDENT,
        email=email,
        password=password,
        full_name=details.full_name,
        phone=details.phone,
    )
    student = StudentProfile(institute=institute, user=user)
    _apply_details(student, details)
    student.student_code = next_code(institute, STUDENT_CODE_PREFIX)
    student.save()
    _set_pairs(student, selections)
    first_name, last_name = split_full_name(guardian_name)
    enrol_guardian(
        student,
        email=guardian_email,
        password=guardian_password,
        first_name=first_name,
        last_name=last_name,
        phone=details.guardian_phone,
    )
    return student


@transaction.atomic
def update_student(
    student: StudentProfile,
    details: StudentDetails,
    *,
    email: str,
    selections: Selections,
) -> StudentProfile:
    """Edit details, sign-in email and batches. The guardian link stays."""
    require_tenant_context(student.institute)
    user = student.user
    user.email = _check_email_free(email, "email", user=user)
    user.first_name, user.last_name = split_full_name(details.full_name)
    user.phone = details.phone.strip()
    user.save()
    _apply_details(student, details)
    student.save()
    _set_pairs(student, selections)
    return student


@transaction.atomic
def set_student_active(student: StudentProfile, *, is_active: bool) -> StudentProfile:
    """The guardian account is not changed: it may have other children."""
    _set_active(student, is_active=is_active)
    return student
