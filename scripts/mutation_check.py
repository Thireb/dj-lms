"""Undo each access or validation fix, run pytest, and expect a failure.

Usage: uv run python scripts/mutation_check.py [name-filter]
Prints CAUGHT or MISSED per entry and exits 1 if any entry is MISSED or stale.
Every file is restored with `git checkout` after its run, so start from a
clean working tree for the files listed here.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (name, file, original text, mutated text)
MUTATIONS: list[tuple[str, str, str, str]] = [
    (
        "self_service flag",
        "apps/accounts/views.py",
        "    self_service = True\n",
        "    self_service = False\n",
    ),
    (
        "admin_only menu hiding",
        "apps/ui/menus/registry.py",
        "        if item.admin_only and role != Role.INSTITUTE_ADMIN:",
        "        if False:",
    ),
    (
        "admin_only misconfig raise",
        "apps/core/mixins/access.py",
        "            if configured != [Role.INSTITUTE_ADMIN]:",
        "            if False:",
    ),
    (
        "feature gate",
        "apps/core/mixins/access.py",
        "            if key not in features:",
        "            if False:",
    ),
    (
        "fee_due_day range",
        "apps/institutes/services.py",
        "    if not 1 <= settings.fee_due_day <= 28:",
        "    if False:",
    ),
    (
        "partial < present",
        "apps/institutes/services.py",
        "        settings.attendance_partial_min_percent\n"
        "        >= settings.attendance_present_min_percent",
        "        False",
    ),
    (
        "settings form calls range check",
        "apps/institutes/forms.py",
        "            validate_settings_ranges(candidate)\n",
        "            pass\n",
    ),
    (
        "super pages roles",
        "apps/superadmin/views.py",
        "    allowed_roles = [Role.SUPER_ADMIN]\n",
        "    allowed_roles = [Role.SUPER_ADMIN, Role.TEACHER]\n",
    ),
    (
        "edit loads object after access check",
        "apps/superadmin/views.py",
        "        return get_object_or_404(\n"
        '            Institute.objects.select_related("plan"), pk=self.kwargs["pk"]\n'
        "        )",
        '        return Institute.objects.select_related("plan")'
        '.get(pk=self.kwargs["pk"])',
    ),
    (
        "deactivate",
        "apps/superadmin/services.py",
        "    institute.is_active = is_active\n",
        "",
    ),
    (
        "create atomic",
        "apps/superadmin/services.py",
        "@transaction.atomic\n",
        "",
    ),
    (
        "duplicate email check",
        "apps/superadmin/forms.py",
        "        if User.objects.filter(email__iexact=email).exists():",
        "        if False:",
    ),
    (
        "create time zone check",
        "apps/superadmin/forms.py",
        "    if value not in available_timezones():",
        "    if False:",
    ),
    (
        "unusable admin password",
        "apps/superadmin/services.py",
        "        password=None,\n",
        '        password="fake-known-password",\n',
    ),
    (
        "set-password link not in messages",
        "apps/superadmin/views.py",
        "        context = self.get_context_data()\n",
        "        context = self.get_context_data()\n"
        "        messages.success(self.request, link)\n",
    ),
    (
        "seed DEBUG guard",
        "apps/core/management/commands/seed_demo.py",
        "        if not settings.DEBUG:",
        "        if False:",
    ),
    (
        "seed password from env",
        "apps/core/management/commands/seed_demo.py",
        "        if not password:",
        "        if False:",
    ),
    (
        "basic plan keys",
        "apps/core/features.py",
        "frozenset({MESSAGING, TIME_ZONE_LECTURES})",
        "frozenset({FEES, MESSAGING, TIME_ZONE_LECTURES})",
    ),
    (
        "campus menu_key",
        "apps/institutes/views.py",
        "    menu_key = menu_keys.INSTITUTE\n",
        "    menu_key = menu_keys.DASHBOARDS\n",
    ),
    (
        "campus fresh instance",
        "apps/institutes/views.py",
        "        institute = Institute.objects.get(pk=self.get_institute().pk)\n",
        "        institute = self.get_institute()\n",
    ),
    (
        "super shell sign out",
        "apps/ui/menus/super.py",
        '                    MenuItem("Sign out", "accounts:logout", '
        '"right-from-bracket"),\n',
        "",
    ),
    (
        "F3 validate_password",
        "apps/accounts/forms.py",
        "            validate_password(new_password, user=self.user)\n",
        "            pass\n",
    ),
    (
        "F4 csrf_token on portal forms",
        "apps/ui/templates/ui/components/portal_post_form.html",
        "  {% csrf_token %}\n",
        "",
    ),
    (
        "confirm dialog csrf_token",
        "apps/ui/templates/ui/components/confirm_dialog.html",
        "{% if csrf_token %}{% csrf_token %}{% endif %}",
        "",
    ),
    (
        "F6 profile fresh instance",
        "apps/accounts/views.py",
        "        user = User.objects.get(pk=self.request.user.pk)\n",
        "        user = self.request.user\n",
    ),
    (
        "people own-row scope",
        "apps/people/models.py",
        "            return scoped.filter(user_id=user_id)\n",
        "            return scoped\n",
    ),
    (
        "guardian profiles hidden from teachers",
        "apps/people/models.py",
        "student_links__student__user_id=user_id)\n        return self.none()\n",
        "student_links__student__user_id=user_id)\n        return self\n",
    ),
    (
        "people admins see institute",
        "apps/people/models.py",
        "            return scoped\n",
        "            return scoped.none()\n",
    ),
    (
        "people scoped manager",
        "apps/people/models.py",
        "    unscoped = UnscopedTenantManager.from_queryset(StudentProfileQuerySet)()",
        "    unscoped = UnscopedTenantManager()",
    ),
    (
        "profile role check",
        "apps/people/models.py",
        "        if user.role != self.profile_role:",
        "        if False:",
    ),
    (
        "profile institute check",
        "apps/people/models.py",
        "        if user.institute_id != self.institute_id:",
        "        if False:",
    ),
    (
        "profile save validates",
        "apps/people/models.py",
        "        self.full_clean(validate_unique=False, validate_constraints=False)\n",
        "        pass\n",
    ),
    (
        "student cnic validator",
        "apps/people/models.py",
        "validators=[cnic_validator]",
        "validators=[]",
    ),
    (
        "teacher cnic validator",
        "apps/people/models.py",
        "validators=[cnic_validator]\n"
        "    )\n"
        '    address = models.TextField(blank=True, default="")\n'
        "    joining_date",
        "validators=[]\n"
        "    )\n"
        '    address = models.TextField(blank=True, default="")\n'
        "    joining_date",
    ),
    (
        "code needs tenant context",
        "apps/core/tenancy.py",
        "    if institute is None or current is None or current.pk != institute.pk:",
        "    if False:",
    ),
    (
        "code counter saved",
        "apps/people/services.py",
        '        sequence.save(update_fields=["last_number"])\n',
        "        pass\n",
    ),
    (
        "student create is atomic",
        "apps/people/services.py",
        "@transaction.atomic\ndef create_student_profile",
        "def create_student_profile",
    ),
    (
        "profile admin registered",
        "apps/people/admin.py",
        "developer_admin_site.register(StudentProfile, StudentProfileAdmin)\n",
        "",
    ),
    (
        "profile admin has no add",
        "apps/people/admin.py",
        "    def has_add_permission(self, request):  # noqa: ANN001\n"
        "        return False\n",
        "    def has_add_permission(self, request):  # noqa: ANN001\n"
        "        return super().has_add_permission(request)\n",
    ),
    (
        "guardian sees linked students only",
        "apps/people/models.py",
        "            return self.filter(guardian_links__guardian__user_id=user_id)",
        "            return self.filter(guardian_links__isnull=False)",
    ),
    (
        "student sees linked guardians only",
        "apps/people/models.py",
        "            return self.filter(student_links__student__user_id=user_id)",
        "            return self.filter(student_links__isnull=False)",
    ),
    (
        "link scope guardian",
        "apps/people/models.py",
        "            return scoped.filter(guardian__user_id=user_id)\n",
        "            return scoped\n",
    ),
    (
        "link scope student",
        "apps/people/models.py",
        "            return scoped.filter(student__user_id=user_id)\n",
        "            return scoped\n",
    ),
    (
        "link scope other roles",
        "apps/people/models.py",
        "        return scoped.none()\n",
        "        return scoped\n",
    ),
    (
        "link institute check",
        "apps/people/models.py",
        "            if profile is not None and profile.institute_id"
        " != self.institute_id:",
        "            if False:",
    ),
    (
        "link save validates",
        "apps/people/models.py",
        "        # Same reason as ProfileBase.save: the database enforces uniqueness.\n"
        "        self.full_clean(validate_unique=False, validate_constraints=False)\n",
        "        pass\n",
    ),
    (
        "enrol reuses same-institute guardian only",
        "apps/people/services.py",
        "    return is_guardian and user.institute_id == institute.pk\n",
        "    return is_guardian\n",
    ),
    (
        "enrol reuses guardians only",
        "apps/people/services.py",
        "    return is_guardian and user.institute_id == institute.pk\n",
        "    return user.institute_id == institute.pk\n",
    ),
    (
        "enrol validates password",
        "apps/people/services.py",
        "        validate_password(password, user)\n",
        "        pass\n",
    ),
    (
        "enrol normalises email",
        "apps/people/services.py",
        "    email = email.strip().lower()\n",
        "    email = email\n",
    ),
    (
        "link admin has no add",
        "apps/people/admin.py",
        "developer_admin_site.register("
        "GuardianStudentLink, GuardianStudentLinkAdmin)\n",
        "developer_admin_site.register(GuardianStudentLink)\n",
    ),
    (
        "list scope filters by role",
        "apps/academics/models.py",
        'return scoped.filter(**{lookup: getattr(user, "pk", None)}).distinct()\n',
        "return scoped.distinct()\n",
    ),
    (
        "list scope distinct",
        "apps/academics/models.py",
        'return scoped.filter(**{lookup: getattr(user, "pk", None)}).distinct()\n',
        'return scoped.filter(**{lookup: getattr(user, "pk", None)})\n',
    ),
    (
        "list scope unknown role sees nothing",
        "apps/academics/models.py",
        "        if lookup is None:\n            return scoped.none()\n",
        "        if lookup is None:\n            return scoped\n",
    ),
    (
        "list scope admins see institute",
        "apps/academics/models.py",
        "        if role in INSTITUTE_WIDE_ROLES:\n            return scoped\n",
        "        if role in INSTITUTE_WIDE_ROLES:\n            return scoped.none()\n",
    ),
    (
        "student list lookup",
        "apps/academics/models.py",
        '    Role.STUDENT: "student_links__student__user_id",\n',
        '    Role.STUDENT: "teacher_links__teacher__user_id",\n',
    ),
    (
        "teacher sees students of own batches",
        "apps/people/models.py",
        "batch_subjects__batch__teacher_links__teacher__user_id=user_id\n",
        "batch_subjects__isnull=False\n",
    ),
    (
        "teacher student list distinct",
        "apps/people/models.py",
        "            ).distinct()\n",
        "            )\n",
    ),
    (
        "student sees teachers of own batches",
        "apps/people/models.py",
        'return self.filter(**{f"{students}user_id": user_id}).distinct()\n',
        "return self.distinct()\n",
    ),
    (
        "guardian sees teachers of child batches",
        "apps/people/models.py",
        "            return self.filter(**{lookup: user_id}).distinct()\n",
        "            return self.distinct()\n",
    ),
    (
        "class label institute check",
        "apps/people/models.py",
        "        if label is not None and label.institute_id != self.institute_id:",
        "        if False:",
    ),
    (
        "academics link institute check",
        "apps/academics/models.py",
        "if related is not None and related.institute_id != self.institute_id:",
        "if False:",
    ),
    (
        "academics link save validates",
        "apps/academics/models.py",
        "        self.full_clean(validate_unique=False, validate_constraints=False)\n",
        "        pass\n",
    ),
    (
        "at least one batch",
        "apps/academics/services.py",
        "    if not selections:\n",
        "    if False:\n",
    ),
    (
        "each batch needs a subject",
        "apps/academics/services.py",
        "        if not subjects:\n",
        "        if False:\n",
    ),
    (
        "pairs from this institute",
        "apps/academics/services.py",
        "            if item.institute_id != institute.pk:",
        "            if False:",
    ),
    (
        "new pairs must be active",
        "apps/academics/services.py",
        "        if not item.is_active:",
        "        if False:",
    ),
    (
        "stale pairs removed",
        "apps/academics/services.py",
        "        links.filter(batch_id=batch_id, subject_id=subject_id).delete()\n",
        "        pass\n",
    ),
    (
        "pairs need tenant context",
        "apps/academics/services.py",
        "    require_tenant_context(institute)\n",
        "",
    ),
    (
        "list admin institute read only",
        "apps/academics/admin.py",
        '        return ("institute",) if obj is not None else ()\n',
        "        return ()\n",
    ),
    (
        "link admin no change",
        "apps/academics/admin.py",
        "    def has_change_permission(self, request, obj=None):  # noqa: ANN001\n"
        "        return False\n",
        "    def has_change_permission(self, request, obj=None):  # noqa: ANN001\n"
        "        return True\n",
    ),
]


def run_pytest() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "pytest", "-q", "-x", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def restore(path: str) -> None:
    subprocess.run(["git", "checkout", "--", path], cwd=ROOT, check=True)


def main() -> int:
    name_filter = sys.argv[1] if len(sys.argv) > 1 else ""
    failures = 0
    for name, path, original, mutated in MUTATIONS:
        if name_filter and name_filter not in name:
            continue
        target = ROOT / path
        source = target.read_text()
        if original not in source:
            print(f"STALE:  {name}: text not found in {path}")
            failures += 1
            continue
        target.write_text(source.replace(original, mutated, 1))
        try:
            result = run_pytest()
        finally:
            restore(path)
        summary = (result.stdout.strip().splitlines() or ["no output"])[-1]
        if result.returncode == 0:
            print(f"MISSED: {name}: {summary}")
            failures += 1
        else:
            print(f"CAUGHT: {name}: {summary}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
