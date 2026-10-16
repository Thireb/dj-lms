"""Undo each access or validation fix, run pytest, and expect a failure.

Usage: uv run python scripts/mutation_check.py [name-filter] [--jobs N]
       [--changed [BASE]]

--changed runs only the entries whose file this branch changed since BASE
(default origin/main): use it while building, and the full run at handover.

Prints CAUGHT, MISSED or STALE per entry and exits 1 if any entry is MISSED
or STALE. Commit first: the entries run against HEAD, one worker per core
minus 2, each in its own git worktree with its own test database, so the
working tree is never touched.

To be fast without changing the result, each entry runs in up to 3 stages and
stops at the first failure: the test that caught it last time (cached in
mutation_cache.json in the shared .git folder), then the tests of the app
that owns the file, then the full suite. An entry is MISSED only when the
full suite passes.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
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
        'MenuItem("Sign out", "accounts:logout", "log-out"),\n',
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
        "    require_tenant_context(institute)\n    links = ",
        "    links = ",
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
    (
        "table cells get request",
        "apps/ui/components/data.py",
        "[render_child(cell, request) for cell in row]",
        "[cell for cell in row]",
    ),
    (
        "list body passes request",
        "apps/ui/components/page_layouts.py",
        "ctx[key] = render_child(ctx.get(key), request)",
        "ctx[key] = render_child(ctx.get(key))",
    ),
    (
        "block stack passes request",
        "apps/ui/components/block_stack.py",
        '"html": render_child(block, request),',
        '"html": render_child(block),',
    ),
    (
        "top nav shell shows toasts",
        "apps/ui/templates/ui/components/top_nav_shell.html",
        "{% for toast in toasts %}",
        "{% for toast in no_toasts %}",
    ),
    (
        "sidebar shell shows toasts",
        "apps/ui/templates/ui/components/sidebar_shell.html",
        "{% for toast in toasts %}",
        "{% for toast in no_toasts %}",
    ),
    (
        "toast tone colors",
        "apps/ui/templates/ui/components/toast.html",
        "{% if tone == 'error' %}border-danger",
        "{% if False %}border-danger",
    ),
    (
        "create row needs tenant context",
        "apps/academics/services.py",
        "    require_tenant_context(institute)\n    name = ",
        "    name = ",
    ),
    (
        "rename row needs tenant context",
        "apps/academics/services.py",
        "    require_tenant_context(row.institute)\n    row.name = ",
        "    row.name = ",
    ),
    (
        "row status needs tenant context",
        "apps/academics/services.py",
        "    require_tenant_context(row.institute)\n    row.is_active = ",
        "    row.is_active = ",
    ),
    (
        "duplicate name check",
        "apps/academics/services.py",
        "    if taken.exists():",
        "    if False:",
    ),
    (
        "rename may keep own name",
        "apps/academics/services.py",
        "        taken = taken.exclude(pk=exclude_pk)\n",
        "        pass\n",
    ),
    (
        "name spaces collapsed",
        "apps/academics/services.py",
        '    name = " ".join(name.split())\n',
        "    name = name.strip()\n",
    ),
    (
        "list rows scoped",
        "apps/academics/services.py",
        "    rows = model.objects.for_user(user)\n",
        "    rows = model.unscoped.all()\n",
    ),
    (
        "student count distinct",
        "apps/academics/services.py",
        "student_count=Count(relation, distinct=True)",
        "student_count=Count(relation)",
    ),
    (
        "row object scoped",
        "apps/academics/views.py",
        "        rows = self.model.objects.for_user(self.request.user)\n",
        "        rows = self.model.unscoped.all()\n",
    ),
    (
        "row status action checked",
        "apps/academics/views.py",
        '        if action not in {"activate", "deactivate"}:',
        "        if False:",
    ),
    (
        "list pages roles",
        "apps/academics/views.py",
        "    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]\n",
        "    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN, Role.TEACHER]\n",
    ),
    (
        "list pages menu key",
        "apps/academics/views.py",
        "    menu_key = menu_keys.INSTITUTE\n",
        "    menu_key = menu_keys.DASHBOARDS\n",
    ),
    (
        "profile status changes sign-in",
        "apps/people/services.py",
        "    profile.user.is_active = is_active\n",
        "    pass\n",
    ),
    (
        "profile status changes profile",
        "apps/people/services.py",
        "    profile.status = ProfileStatus.ACTIVE if is_active"
        " else ProfileStatus.INACTIVE\n",
        "    pass\n",
    ),
    (
        "teacher email must be free",
        "apps/people/services.py",
        '    email = _check_email_free(email, "email")\n',
        "    email = email.strip().lower()\n",
    ),
    (
        "teacher may keep own email",
        "apps/people/services.py",
        "        taken = taken.exclude(pk=user.pk)\n",
        "        pass\n",
    ),
    (
        "teacher password validated",
        "apps/people/services.py",
        "        validate_password(password, user)\n"
        "    except ValidationError as error:\n"
        '        raise ValidationError({"password"',
        "        pass\n"
        "    except ValidationError as error:\n"
        '        raise ValidationError({"password"',
    ),
    (
        "teacher create atomic",
        "apps/people/services.py",
        "@transaction.atomic\ndef create_teacher(",
        "def create_teacher(",
    ),
    (
        "teacher pair errors on field",
        "apps/people/services.py",
        '        raise ValidationError({"batch_subjects": error.messages}) from error',
        "        raise",
    ),
    (
        "teacher list scoped",
        "apps/people/services.py",
        "TeacherProfile.objects.for_user(user).select_related",
        "TeacherProfile.unscoped.select_related",
    ),
    (
        "teacher batch filter",
        "apps/people/services.py",
        "teachers = teachers.filter(batch_subjects__batch_id=batch_id).distinct()",
        "teachers = teachers",
    ),
    (
        "teacher status filter checked",
        "apps/people/services.py",
        "    if status in ProfileStatus.values:",
        "    if status:",
    ),
    (
        "profile object scoped",
        "apps/people/views.py",
        "        profiles = self.model.objects.for_user(self.request.user)\n",
        "        profiles = self.model.unscoped.all()\n",
    ),
    (
        "teacher status action checked",
        "apps/people/views.py",
        '        if action not in {"activate", "deactivate"}:',
        "        if False:",
    ),
    (
        "teacher pages roles",
        "apps/people/views.py",
        "    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]\n",
        "    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN, Role.TEACHER]\n",
    ),
    (
        "teacher pages menu key",
        "apps/people/views.py",
        "    menu_key = menu_keys.PEOPLE\n",
        "    menu_key = menu_keys.DASHBOARDS\n",
    ),
    (
        "pair field offers active only",
        "apps/academics/forms.py",
        "                    if (batch.is_active and subject.is_active)",
        "                    if True",
    ),
    (
        "pair field keeps linked pairs",
        "apps/academics/forms.py",
        "                    or (batch.pk, subject.pk) in kept",
        "                    or False",
    ),
    (
        "filter bar selects",
        "apps/ui/templates/ui/components/filter_bar.html",
        "{% elif f.options %}",
        "{% elif False %}",
    ),
    (
        "student list scoped",
        "apps/people/services.py",
        "StudentProfile.objects.for_user(user).select_related(",
        "StudentProfile.unscoped.select_related(",
    ),
    (
        "student class filter",
        "apps/people/services.py",
        "        students = students.filter(class_label_id=class_label_id)\n",
        "        pass\n",
    ),
    (
        "student search guardian phone",
        "apps/people/services.py",
        "            | Q(guardian_phone__icontains=term)\n",
        "",
    ),
    (
        "student and guardian emails differ",
        "apps/people/services.py",
        "    if email.strip().lower() == guardian_email.strip().lower():",
        "    if False:",
    ),
    (
        "new guardian needs password",
        "apps/people/services.py",
        '    if not password:\n        raise ValidationError({"guardian_password"',
        '    if False:\n        raise ValidationError({"guardian_password"',
    ),
    (
        "enrol student atomic",
        "apps/people/services.py",
        "@transaction.atomic\ndef enrol_student(",
        "def enrol_student(",
    ),
    (
        "student status sync",
        "apps/people/services.py",
        "    _set_active(student, is_active=is_active)\n",
        "    pass\n",
    ),
    (
        "class options scoped",
        "apps/people/forms.py",
        "labels = ClassLabel.objects.for_user(user).filter(is_active=True)",
        "labels = ClassLabel.unscoped.filter(is_active=True)",
    ),
    (
        "class options active only",
        "apps/people/forms.py",
        "labels = ClassLabel.objects.for_user(user).filter(is_active=True)",
        "labels = ClassLabel.objects.for_user(user)",
    ),
    (
        "edit keeps current class",
        "apps/people/forms.py",
        "        if current_label is not None:",
        "        if False:",
    ),
    (
        "upload file size limit",
        "apps/people/bulk_upload.py",
        "    if len(data) > MAX_FILE_BYTES:",
        "    if False:",
    ),
    (
        "upload row limit",
        "apps/people/bulk_upload.py",
        "        if len(found) == MAX_ROWS:",
        "        if False:",
    ),
    (
        "upload required columns",
        "apps/people/bulk_upload.py",
        "    if missing:\n        raise UploadError",
        "    if False:\n        raise UploadError",
    ),
    (
        "upload batches match subjects",
        "apps/people/bulk_upload.py",
        "    if {batch.lower() for batch, _ in groups} != listed:",
        "    if False:",
    ),
    (
        "upload lists are institute only",
        "apps/people/bulk_upload.py",
        "rows = model.objects.filter(institute=institute, is_active=True)",
        "rows = model.unscoped.filter(is_active=True)",
    ),
    (
        "upload duplicate student email",
        "apps/people/bulk_upload.py",
        "    if email in student_emails or email in new_guardians:",
        "    if False:",
    ),
    (
        "upload guardian of same institute only",
        "apps/people/bulk_upload.py",
        "if existing.role != Role.GUARDIAN or existing.institute_id != institute.pk:",
        "if existing.role != Role.GUARDIAN:",
    ),
    (
        "upload new guardian needs password",
        "apps/people/bulk_upload.py",
        '        if not values.get("guardian_password"):',
        "        if False:",
    ),
    (
        "upload sibling shares new guardian",
        "apps/people/bulk_upload.py",
        '            new_guardians.add(row.values["guardian_email"].lower())\n',
        "",
    ),
    (
        "upload checks again on import",
        "apps/people/bulk_upload.py",
        "        if not row.ok:\n"
        "            failed.append(row)\n"
        "            continue\n",
        "",
    ),
    (
        "upload check needs tenant context",
        "apps/people/bulk_upload.py",
        "    require_tenant_context(institute)\n    lookups = ",
        "    lookups = ",
    ),
    (
        "upload preview not cached",
        "apps/people/views.py",
        "        patch_cache_control(response, no_store=True, private=True)\n",
        "",
    ),
    (
        "upload xlsx extension",
        "apps/people/forms.py",
        '        if not upload.name.lower().endswith(".xlsx"):',
        "        if False:",
    ),
    (
        "detail body passes request",
        "apps/ui/components/page_layouts.py",
        "ctx[key] = [render_child(card, request) for card in ctx[key]]",
        "ctx[key] = [render_child(card) for card in ctx[key]]",
    ),
    (
        "dashboard counts scoped",
        "apps/people/dashboard.py",
        "    totals = model.objects.for_user(user).aggregate(",
        "    totals = model.unscoped.aggregate(",
    ),
    (
        "dashboard active count filter",
        "apps/people/dashboard.py",
        'active=Count("pk", filter=Q(status=ProfileStatus.ACTIVE))',
        'active=Count("pk")',
    ),
    (
        "running batches need active students",
        "apps/people/dashboard.py",
        "        student_links__student__status=ProfileStatus.ACTIVE",
        "        student_links__isnull=False",
    ),
    (
        "running batches distinct",
        "apps/people/dashboard.py",
        "    ).distinct()\n",
        "    )\n",
    ),
    (
        "dashboard batches scoped",
        "apps/people/dashboard.py",
        "    batches = Batch.objects.for_user(user)\n",
        "    batches = Batch.unscoped.all()\n",
    ),
    (
        "quick actions follow menus",
        "apps/people/views.py",
        "            if self.can_open(key)\n",
        "",
    ),
    (
        "menu helper sub-admin keys",
        "apps/core/menus.py",
        '        return key in (getattr(user, "allowed_menus", None) or [])',
        "        return True",
    ),
    (
        "dashboard roles",
        "apps/people/views.py",
        "    menu_key = menu_keys.DASHBOARDS\n",
        "    menu_key = menu_keys.PEOPLE\n",
    ),
    (
        "dashboard hero slot",
        "apps/ui/templates/ui/layouts/pages/dashboard.html",
        "  {% if hero %}{{ hero }}{% endif %}\n",
        "",
    ),
    (
        "badge tone colors",
        "apps/ui/templates/ui/components/badge.html",
        "{% if tone == 'success' %}bg-success-50 text-success",
        "{% if False %}bg-success-50 text-success",
    ),
    (
        "blocked student sees access paused",
        "apps/people/middleware.py",
        "            and student_portal_blocked(user)\n",
        "            and False\n",
    ),
    (
        "block only the student portal",
        "apps/people/middleware.py",
        "return resolve(request.path_info).namespace == STUDENT_NAMESPACE",
        "return True",
    ),
    (
        "access middleware installed",
        "config/settings/base.py",
        '    "apps.people.middleware.StudentPortalAccessMiddleware",\n',
        "",
    ),
    (
        "access rule own student only",
        "apps/people/models.py",
        'return scoped.filter(student__user_id=getattr(user, "pk", None))\n'
        "        return scoped.none()\n",
        "return scoped\n        return scoped.none()\n",
    ),
    (
        "access rule other roles none",
        "apps/people/models.py",
        'return scoped.filter(student__user_id=getattr(user, "pk", None))\n'
        "        return scoped.none()\n",
        'return scoped.filter(student__user_id=getattr(user, "pk", None))\n'
        "        return scoped\n",
    ),
    (
        "access rule institute check",
        "apps/people/models.py",
        "if student is not None and student.institute_id != self.institute_id:",
        "if False:",
    ),
    (
        "access list yes filter",
        "apps/people/services.py",
        'students = students.filter(**{f"access_rule__{name}": True})',
        "students = students",
    ),
    (
        "access no rule counts as no",
        "apps/people/services.py",
        'Q(access_rule__isnull=True) | Q(**{f"access_rule__{name}": False})',
        'Q(**{f"access_rule__{name}": False})',
    ),
    (
        "access services need context",
        "apps/people/services.py",
        "    require_tenant_context(student.institute)\n    rule, _ = ",
        "    rule, _ = ",
    ),
    (
        "access action checked",
        "apps/people/views.py",
        "        if action is None:\n",
        "        if False:\n",
    ),
    (
        "seed guardian has two children",
        "apps/people/demo.py",
        "    if student_number <= 2:\n",
        "    if student_number <= 1:\n",
    ),
    (
        "seed inactive students",
        "apps/people/demo.py",
        "    if number > ACTIVE_STUDENTS:\n",
        "    if False:\n",
    ),
    (
        "seed skips existing students",
        "apps/people/demo.py",
        "    if _existing_profile(StudentProfile, email):\n        return\n",
        "",
    ),
    (
        "seed takes over phase 1 users",
        "apps/people/demo.py",
        "    _take_over_user(email)\n    guardian = ",
        "    guardian = ",
    ),
    (
        "seed reset deletes children first",
        "apps/people/demo.py",
        "        PortalAccessRule,\n        StudentBatchSubject,\n",
        "        StudentBatchSubject,\n",
    ),
    (
        "seed_demo seeds people",
        "apps/core/management/commands/seed_demo.py",
        "        seed_people(institute, password)\n",
        "",
    ),
    (
        "login refuses when locked",
        "apps/accounts/views.py",
        "        if throttle.is_locked(throttle.LOGIN, email, ip):",
        "        if False:",
    ),
    (
        "login records failures",
        "apps/accounts/views.py",
        "            throttle.record_failure(throttle.LOGIN, email, ip)\n",
        "",
    ),
    (
        "login resets on success",
        "apps/accounts/views.py",
        "        throttle.reset(throttle.LOGIN, email, ip)\n        user = auth.user\n",
        "        user = auth.user\n",
    ),
    (
        "admin login refuses when locked",
        "config/developer_admin_site.py",
        "        if throttle.is_locked(throttle.LOGIN, email, ip):",
        "        if False:",
    ),
    (
        "admin login records failures",
        "config/developer_admin_site.py",
        "            throttle.record_failure(throttle.LOGIN, email, ip)\n            raise",
        "            raise",
    ),
    (
        "set-password refuses when locked",
        "apps/accounts/views.py",
        '        if throttle.is_locked(throttle.SET_PASSWORD, "", ip):',
        "        if False:",
    ),
    (
        "set-password records failures",
        "apps/accounts/views.py",
        '        throttle.record_failure(throttle.SET_PASSWORD, "", ip)\n        return self.render_page(form)',
        "        return self.render_page(form)",
    ),
    (
        "bad link counts as failure",
        "apps/accounts/views.py",
        '            if request.method == "POST":',
        "            if False:",
    ),
    (
        "proxy header only when trusted",
        "apps/accounts/throttle.py",
        '    header = getattr(settings, "TRUSTED_PROXY_IP_HEADER", "")',
        '    header = "HTTP_X_REAL_IP"',
    ),
    (
        "throttle key ignores case",
        "apps/accounts/throttle.py",
        "{identity.strip().lower()}",
        "{identity.strip()}",
    ),
    (
        "throttle limit is five",
        "apps/accounts/throttle.py",
        "    return cache.get(_key(scope, identity, ip), 0) >= FAILURE_LIMIT",
        "    return cache.get(_key(scope, identity, ip), 0) > FAILURE_LIMIT",
    ),
    (
        "email lowered on save",
        "apps/accounts/models.py",
        '        self.email = (self.email or "").strip().lower()\n',
        "",
    ),
    (
        "sign-in email ignores case",
        "apps/accounts/models.py",
        "        return self.get(email__iexact=username.strip())",
        "        return self.get(email=username)",
    ),
    (
        "inactive institute page has sign out",
        "apps/core/middleware/tenant.py",
        "                    return blocked_account_response(request, INSTITUTE_INACTIVE)",
        '                    return HttpResponse("Institute inactive.", status=403)',
    ),
    (
        "remember me lasts 14 days",
        "apps/accounts/services.py",
        "        request.session.set_expiry(settings.REMEMBER_ME_SECONDS)",
        "        request.session.set_expiry(settings.SESSION_COOKIE_AGE)",
    ),
    (
        "server session 12 hours",
        "config/settings/base.py",
        "SESSION_COOKIE_AGE = 60 * 60 * 12\n",
        "SESSION_COOKIE_AGE = 60 * 60 * 24 * 14\n",
    ),
    (
        "login password keeps spaces",
        "apps/accounts/forms.py",
        "widget=PasswordInput(), strip=False)",
        "widget=PasswordInput())",
    ),
    (
        "super admin gets is_staff",
        "apps/accounts/models.py",
        '        extra_fields.setdefault("is_staff", is_super)',
        '        extra_fields.setdefault("is_staff", False)',
    ),
    (
        "token used once",
        "apps/accounts/services.py",
        "    if not locked.is_valid():\n        return None\n",
        "",
    ),
    (
        "set-password checks the email",
        "apps/accounts/forms.py",
        "                validate_password(password, self.user)",
        "                validate_password(password)",
    ),
    (
        "forms show non-field errors",
        "apps/ui/templates/ui/forms/whole_uni_form.html",
        "  {% if form.non_field_errors %}",
        "  {% if False %}",
    ),
    (
        "sidebar hidden on phones",
        "apps/ui/templates/ui/components/sidebar_shell.html",
        'class="sidebar-wrap hidden md:sticky',
        'class="sidebar-wrap md:sticky',
    ),
    (
        "menu groups start closed",
        "apps/ui/templates/ui/components/top_nav.html",
        ' x-show="open" x-cloak>',
        ">",
    ),
    (
        "main column can shrink",
        "apps/ui/templates/ui/layouts/app_shell.html",
        '<main class="min-w-0 flex-1',
        '<main class="flex-1',
    ),
    (
        "fieldsets can shrink",
        "apps/ui/templates/ui/forms/layout/section.html",
        'class="section min-w-0 ',
        'class="section ',
    ),
    (
        "form widgets full width",
        "apps/ui/forms/base.py",
        '        widget.attrs["class"] = INPUT_CLASSES\n',
        "",
    ),
    (
        "upload refuses far rows",
        "apps/people/bulk_upload.py",
        "    if (sheet.max_row or 0) > MAX_SCANNED_ROWS:",
        "    if False:",
    ),
    (
        "upload unpacked size limit",
        "apps/people/bulk_upload.py",
        '                raise UploadError("The file is too large when unpacked.")',
        "                pass",
    ),
    (
        "upload row cap is 15",
        "apps/people/bulk_upload.py",
        "MAX_ROWS = 15\n",
        "MAX_ROWS = 50\n",
    ),
    (
        "upload catches every read error",
        "apps/people/bulk_upload.py",
        "    except Exception:  # noqa: BLE001",
        "    except ValueError:  # noqa: BLE001",
    ),
    (
        "upload checks model fields",
        "apps/people/bulk_upload.py",
        "            _check_fields(row)\n",
        "",
    ),
    (
        "upload keeps password spaces",
        "apps/people/bulk_upload.py",
        "_cell_text(cell, raw=name in RAW_COLUMNS)",
        "_cell_text(cell)",
    ),
    (
        "upload phone must be text",
        "apps/people/bulk_upload.py",
        '                if column in raw.get("numbers", ()):',
        "                if False:",
    ),
    (
        "template text cells",
        "apps/people/bulk_upload.py",
        '            sheet.cell(row=row, column=index).number_format = "@"\n',
        "            pass\n",
    ),
    (
        "upload id must match",
        "apps/people/views.py",
        '    if not secrets.compare_digest(str(kept.get("id", "")), upload_id):\n        return None\n',
        "",
    ),
    (
        "upload expires",
        "apps/people/views.py",
        '    if time.time() - kept.get("created", 0) > UPLOAD_MAX_AGE:\n        return None\n',
        "",
    ),
    (
        "new link cancels old links",
        "apps/accounts/services.py",
        "    SetPasswordToken.objects.filter(user=user, used_at__isnull=True).update(\n        used_at=timezone.now()\n    )\n",
        "",
    ),
    (
        "link command refuses inactive",
        "apps/accounts/management/commands/make_set_password_link.py",
        "        if not user.is_active:",
        "        if False:",
    ),
    (
        "id param ascii digits",
        "apps/core/query.py",
        "value.isascii() and value.isdigit()",
        "value.isdigit()",
    ),
    (
        "id param length",
        "apps/core/query.py",
        "    if 0 < len(value) <= MAX_ID_DIGITS and",
        "    if 0 < len(value) and",
    ),
    (
        "search drops NUL",
        "apps/core/query.py",
        '(value or "").replace("\\x00", "")',
        '(value or "")',
    ),
    (
        "people filters cleaned",
        "apps/people/views.py",
        "key: search_param(self.request.GET.get(key)) for key in self.filter_keys",
        "key: self.request.GET.get(key, '') for key in self.filter_keys",
    ),
    (
        "create institute not cached",
        "apps/superadmin/views.py",
        "        # The one-time link must not stay in a browser or proxy cache (M8).\n        patch_cache_control(response, no_store=True, private=True)\n",
        "",
    ),
    (
        "new link page not cached",
        "apps/superadmin/views.py",
        "        response = self.render_to_response(self.get_context_data())\n        patch_cache_control(response, no_store=True, private=True)\n",
        "        response = self.render_to_response(self.get_context_data())\n",
    ),
    (
        "safe_url refuses //host",
        "apps/ui/safe_url.py",
        '    if cleaned.startswith("//"):\n        return ""\n',
        "",
    ),
    (
        "safe_url refuses inner spaces",
        "apps/ui/safe_url.py",
        "    if not cleaned or _INNER_BAD.search(cleaned):",
        "    if not cleaned:",
    ),
    (
        "profile status read-only",
        "apps/people/admin.py",
        'readonly_fields = ("student_code", "institute", "user", "status")',
        'readonly_fields = ("student_code", "institute", "user")',
    ),
    (
        "root sends users to portal",
        "apps/accounts/views.py",
        "    if request.user.is_authenticated:\n        return redirect(post_login_redirect_url(request.user))",
        "    if False:\n        return redirect(post_login_redirect_url(request.user))",
    ),
    (
        "unknown icons render nothing",
        "apps/ui/components/icon.py",
        'ctx["href"] = f"{static(ICON_SPRITE)}#{name}" if name in ICON_NAMES else ""',
        'ctx["href"] = f"{static(ICON_SPRITE)}#{name}"',
    ),
    (
        "portal pages show the clock",
        "apps/ui/views/pages.py",
        "            clock=True,\n",
        "            clock=False,\n",
    ),
    (
        "sign-in band panel",
        "apps/ui/templates/ui/layouts/public.html",
        '<aside class="band hidden',
        '<aside class="hidden',
    ),
    (
        "notice pages are the band",
        "apps/ui/templates/ui/layouts/public.html",
        '<main class="band grid',
        '<main class="grid',
    ),
    (
        "public forms have no box",
        "apps/ui/templates/ui/layouts/public.html",
        "[&_.section]:border-0 ",
        "",
    ),
    (
        "sign-in submit full width",
        "apps/accounts/forms.py",
        'cancel_label="Forgot password?",\n                stacked=True,',
        'cancel_label="Forgot password?",',
    ),
    (
        "access paused uses notice",
        "apps/people/views.py",
        '        variant="notice",\n        icon="circle-pause",',
        '        icon="circle-pause",',
    ),
    (
        "refusal uses notice",
        "apps/core/responses.py",
        '        variant="notice",\n',
        "\n",
    ),
    (
        "teacher dashboard link",
        "apps/ui/menus/teacher.py",
        '"teacher:home"',
        '"teacher:dashboard"',
    ),
    (
        "initials use email local part",
        "apps/ui/brand.py",
        '    local = name.split("@", 1)[0]\n',
        "    local = name\n",
    ),
    (
        "dialog is a modal",
        "apps/ui/templates/ui/components/confirm_dialog.html",
        'role="alertdialog" aria-modal="true"',
        'role="alertdialog"',
    ),
    (
        "font preloaded",
        "templates/base.html",
        "familjen-grotesk-latin.woff2",
        "missing-font.woff2",
    ),
    (
        "role shown in user chip",
        "apps/ui/templates/ui/components/profile_menu.html",
        '{% if badge.role %}<span class="block text-xs text-muted">{{ badge.role }}</span>{% endif %}',
        "",
    ),
    (
        "table cells carry column label",
        "apps/ui/templates/ui/components/data_table.html",
        ' data-label="{{ label }}"',
        "",
    ),
    (
        "phone table rules outside layer",
        "static/css/src/input.css",
        "/* Tables become cards on phones",
        "/* Cards on phones",
    ),
    (
        "people tables show person cell",
        "apps/people/ui.py",
        '        Column("name", "Student", person),\n        Column("class_label", "Class", lambda s: s.class_label or ""),\n        Column("batches", "Batches", _batches),',
        '        Column("name", "Student", str),\n        Column("class_label", "Class", lambda s: s.class_label or ""),\n        Column("batches", "Batches", _batches),',
    ),
    (
        "icon button has aria label",
        "apps/ui/templates/ui/components/icon_button.html",
        '{% endif %} class="icon-btn h-9 w-9" aria-label="{{ label }}"',
        '{% endif %} class="icon-btn h-9 w-9"',
    ),
    (
        "filter bar clear only when active",
        "apps/ui/templates/ui/components/filter_bar.html",
        '{% if active %}<a href="?{{ clear_query }}"',
        '{% if True %}<a href="?{{ clear_query }}"',
    ),
    (
        "filter value read from objects",
        "apps/ui/components/nav.py",
        "    return getattr(field, key, default)",
        "    return getattr(field, key)",
    ),
    (
        "pagination shows page numbers",
        "apps/ui/components/nav.py",
        "paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1)",
        "[page.number]",
    ),
    (
        "section fieldset labelled by title",
        "apps/ui/templates/ui/forms/layout/section.html",
        '{% if legend %}aria-labelledby="{{ section_id }}"{% endif %}',
        "",
    ),
    (
        "section two columns",
        "apps/ui/templates/ui/forms/layout/section.html",
        "{% if columns == 2 %}",
        "{% if columns == 3 %}",
    ),
    (
        "portal form framed",
        "apps/ui/templates/ui/components/portal_post_form.html",
        "{% if framed %}overflow-hidden",
        "{% if not framed %}overflow-hidden",
    ),
    (
        "avatar uses tone tokens",
        "apps/ui/templates/ui/components/avatar.html",
        "bg-tone-clay-50 text-tone-clay",
        "bg-[#fcebe3] text-tone-clay",
    ),
    (
        "bell is an icon button",
        "apps/ui/templates/ui/components/notification_bell.html",
        'class="notification-bell icon-btn"',
        'class="notification-bell text-surface"',
    ),
    (
        "dashboard names need people menu",
        "apps/people/views.py",
        "        show_names = self.can_open(menu_keys.PEOPLE)",
        "        show_names = True",
    ),
    (
        "first hero action is light",
        "apps/people/views.py",
        'variant="light" if index == 0 else "glass"',
        'variant="glass"',
    ),
    (
        "ring dash follows the value",
        "apps/ui/components/data.py",
        "circumference * ctx['value'] / 100",
        "circumference",
    ),
    (
        "greeting noon boundary",
        "apps/people/home.py",
        "    if now.hour < 12:",
        "    if now.hour <= 12:",
    ),
    (
        "teacher counts active students",
        "apps/people/home.py",
        ".filter(status=ProfileStatus.ACTIVE)",
        "",
    ),
    (
        "up next before stat cards",
        "apps/ui/templates/ui/layouts/pages/dashboard.html",
        "  {% if feature %}{{ feature }}{% endif %}\n",
        "",
    ),
    (
        "empty state frame optional",
        "apps/ui/templates/ui/components/empty_state.html",
        "{% if framed %}",
        "{% if True %}",
    ),
    (
        "hero stat notes optional",
        "apps/ui/templates/ui/components/hero_banner.html",
        "{% if note %}<dd",
        "{% if True %}<dd",
    ),
    (
        "top menu groups never wrap",
        "apps/ui/templates/ui/components/top_nav.html",
        "items-center whitespace-nowrap",
        "items-center",
    ),
    (
        "access mixins use the styled 403",
        "apps/core/mixins/access.py",
        "        if role not in self.allowed_roles:\n            return forbidden_response(request)",
        '        if role not in self.allowed_roles:\n            return HttpResponse("Forbidden.", status=403)',
    ),
    (
        "404 handler wired",
        "config/urls_test.py",
        'handler404 = "apps.core.responses.handle_404"',
        "",
    ),
    (
        "menu list closes on escape",
        "apps/ui/templates/ui/components/top_nav.html",
        ' @keydown.escape="menuOpen = false" @click.outside="menuOpen = false"',
        "",
    ),
    (
        "view all tap target",
        "apps/ui/templates/ui/components/section_card.html",
        "inline-flex min-h-8 items-center",
        "inline-flex items-center",
    ),
    (
        "checkbox row is one label",
        "apps/ui/templates/ui/forms/field.html",
        "flex min-h-10 cursor-pointer",
        "flex cursor-pointer",
    ),
    (
        "logo link has no mismatched label",
        "apps/ui/templates/ui/components/top_nav_shell.html",
        '<a href="/" class="flex-none">',
        '<a href="/" class="flex-none" aria-label="{{ brand_name }} home">',
    ),
    (
        "sign-in copy promises only what exists",
        "apps/ui/templates/ui/layouts/public.html",
        "Coming to the portal step by step",
        "Join live classes from any device",
    ),
    (
        "dashboard queries stay flat",
        "apps/people/home.py",
        '        .prefetch_related("batch_subjects__batch")\n',
        "",
    ),
    (
        "lecture teacher scope",
        "apps/lectures/models.py",
        "            return scoped.filter(teacher__user_id=user_id)\n",
        "            return scoped\n",
    ),
    (
        "lecture enrolment on one row",
        "apps/lectures/models.py",
        '            **{lookup: user_id, f"{_ENROLMENT}batch_id": F("batch_id")}\n',
        "            **{lookup: user_id}\n",
    ),
    (
        "lecture unknown role sees none",
        "apps/lectures/models.py",
        "        if lookup is None:\n            return scoped.none()\n",
        "        if lookup is None:\n            return scoped\n",
    ),
    (
        "lecture teacher link check",
        "apps/lectures/services.py",
        "        if subject.pk not in taught:\n",
        "        if False:\n",
    ),
    (
        "lecture other institute rows",
        "apps/lectures/services.py",
        "        if row.institute_id != institute.pk:\n",
        "        if False:\n",
    ),
    (
        "lecture inactive teacher",
        "apps/lectures/services.py",
        "    if teacher.status != ProfileStatus.ACTIVE and teacher.pk != old_teacher:\n",
        "    if False:\n",
    ),
    (
        "lecture inactive teacher may stay",
        "apps/lectures/services.py",
        "    if teacher.status != ProfileStatus.ACTIVE and teacher.pk != old_teacher:\n",
        "    if teacher.status != ProfileStatus.ACTIVE:\n",
    ),
    (
        "lecture duration range",
        "apps/lectures/services.py",
        "    if not MIN_DURATION <= details.duration_minutes <= MAX_DURATION:\n",
        "    if False:\n",
    ),
    (
        "lecture start in future",
        "apps/lectures/services.py",
        "    if moved and details.starts_at <= timezone.now():\n",
        "    if False:\n",
    ),
    (
        "lecture unmoved start may be past",
        "apps/lectures/services.py",
        "    moved = old is None or old.starts_at != details.starts_at\n",
        "    moved = True\n",
    ),
    (
        "lecture link scheme",
        "apps/lectures/services.py",
        "        meeting_url_validator(link)\n",
        "        pass\n",
    ),
    (
        "lecture teacher overlap",
        "apps/lectures/services.py",
        "    clash = _overlapping(others, details.starts_at, ends_at).first()\n",
        "    clash = None\n",
    ),
    (
        "lecture overlap skips cancelled",
        "apps/lectures/services.py",
        "        lectures.exclude(status=LectureStatus.CANCELLED)\n",
        "        lectures\n",
    ),
    (
        "lecture back to back allowed",
        "apps/lectures/services.py",
        "        .filter(starts_at__lt=ends_at, ends_at_db__gt=starts_at)\n",
        "        .filter(starts_at__lte=ends_at, ends_at_db__gte=starts_at)\n",
    ),
    (
        "lecture edit only scheduled",
        "apps/lectures/services.py",
        "    if old is not None and old.status != LectureStatus.SCHEDULED:\n",
        "    if False:\n",
    ),
    (
        "lecture batch clash warning",
        "apps/lectures/services.py",
        "    return SavedLecture(lecture=lecture, batch_clashes=_batch_clashes(lecture))\n",
        "    return SavedLecture(lecture=lecture)\n",
    ),
    (
        "lecture past newest first",
        "apps/lectures/services.py",
        '        return lectures.filter(ends_at_db__lte=now).order_by("-starts_at", "-pk")\n',
        '        return lectures.filter(ends_at_db__lte=now).order_by("starts_at", "pk")\n',
    ),
    (
        "lecture today in viewer zone",
        "apps/lectures/times.py",
        "    today = timezone.localtime(now).date()\n",
        "    today = now.date()\n",
    ),
    (
        "in-person lecture has no link",
        "apps/lectures/providers/manual.py",
        '        return ""\n',
        "        return link\n",
    ),
    (
        "lecture form one batch",
        "apps/lectures/forms.py",
        '        if len({item.split(":")[0] for item in value}) > 1:\n',
        "        if False:\n",
    ),
    (
        "lecture form teacher is fixed",
        "apps/lectures/forms.py",
        '        if teacher is None:\n            self.fields["teacher"] = self.teacher_field()\n',
        '        if True:\n            self.fields["teacher"] = self.teacher_field()\n',
    ),
    (
        "lecture form teacher param scoped",
        "apps/lectures/forms.py",
        '        return self.fields["teacher"].queryset.filter(pk=teacher_id).first()\n',
        "        return TeacherProfile.unscoped.filter(pk=teacher_id).first()\n",
    ),
    (
        "lecture edit uses for_user",
        "apps/lectures/views.py",
        '            Lecture.objects.for_user(self.request.user)\n            .select_related("schedule")\n',
        '            Lecture.unscoped.all()\n            .select_related("schedule")\n',
    ),
    (
        "teacher without profile 403",
        "apps/lectures/views.py",
        '        if self.portal == "teacher" and self.teacher is None:\n',
        "        if False:\n",
    ),
    (
        "lecture unknown tab falls back",
        "apps/lectures/views.py",
        '        filters["show"] = show if show in SHOW_KEYS else SHOW_UPCOMING\n',
        '        filters["show"] = show or SHOW_UPCOMING\n',
    ),
    (
        "lecture edit only when scheduled",
        "apps/lectures/ui.py",
        "        if lecture.status == LectureStatus.SCHEDULED:\n",
        "        if True:\n",
    ),
    (
        "meeting link opens new tab",
        "apps/ui/templates/ui/components/icon_button.html",
        '{% if new_tab %} target="_blank" rel="noopener noreferrer"{% endif %}',
        "",
    ),
    (
        "hidden filter is not clearable",
        "apps/ui/components/nav.py",
        '            if not _get(f, "hidden", False) and not _get(f, "kept", False)\n',
        '            if not _get(f, "kept", False)\n',
    ),
    (
        "lecture form styles added fields",
        "apps/lectures/forms.py",
        "        style_widgets(self)  # the fields added after BaseForm styled the others\n",
        "",
    ),
    (
        "batch warning hides the title",
        "apps/lectures/views.py",
        '                f"{clash.batch.name} also has a lecture on "\n',
        '                f"{clash.batch.name} also has {clash.title} on "\n',
    ),
    (
        "schedule teacher scope",
        "apps/lectures/models.py",
        '            return scoped.filter(teacher__user_id=getattr(user, "pk", None))\n',
        "            return scoped\n",
    ),
    (
        "schedule students see none",
        "apps/lectures/models.py",
        '            return scoped.filter(teacher__user_id=getattr(user, "pk", None))\n        return scoped.none()\n',
        '            return scoped.filter(teacher__user_id=getattr(user, "pk", None))\n        return scoped\n',
    ),
    (
        "schedule weekday filter",
        "apps/lectures/services.py",
        "        if day.weekday() in days:\n",
        "        if True:\n",
    ),
    (
        "schedule wall clock in its zone",
        "apps/lectures/services.py",
        "            result.append(datetime.combine(day, source.start_time, tzinfo=zone))\n",
        '            result.append(datetime.combine(day, source.start_time, tzinfo=ZoneInfo("UTC")))\n',
    ),
    (
        "schedule horizon",
        "apps/lectures/services.py",
        "    last = min(source.end_date, today + timedelta(weeks=horizon_weeks(institute)))\n",
        "    last = source.end_date\n",
    ),
    (
        "schedule skips past times",
        "apps/lectures/services.py",
        "    starts = [start for start in starts if start > now]\n",
        "    starts = list(starts)\n",
    ),
    (
        "schedule skips teacher clash",
        "apps/lectures/services.py",
        "        if item.clash is not None:\n            skipped += 1\n            continue\n",
        "",
    ),
    (
        "schedule no duplicate dates",
        "apps/lectures/services.py",
        "        if item.starts_at.date() in taken:\n",
        "        if False:\n",
    ),
    (
        "schedule stops when teacher no longer fits",
        "apps/lectures/services.py",
        "    if not _still_valid(schedule):\n",
        "    if False:\n",
    ),
    (
        "stopped schedule makes nothing",
        "apps/lectures/services.py",
        "    if schedule.status != ScheduleStatus.ACTIVE:\n        return GenerateResult()\n",
        "    if False:\n        return GenerateResult()\n",
    ),
    (
        "schedule edit keeps lectures edited alone",
        "apps/lectures/services.py",
        "        schedule=schedule,\n        follows_schedule=True,\n",
        "        schedule=schedule,\n",
    ),
    (
        "lecture edit marks edited alone",
        "apps/lectures/services.py",
        "        lecture.follows_schedule = False\n",
        "        lecture.follows_schedule = True\n",
    ),
    (
        "schedule start from today",
        "apps/lectures/services.py",
        "    if moved and details.start_date < schedule_today(details.time_zone, now):\n",
        "    if False:\n",
    ),
    (
        "schedule one year at most",
        "apps/lectures/services.py",
        "    if (details.end_date - details.start_date).days >= MAX_SCHEDULE_DAYS:\n",
        "    if False:\n",
    ),
    (
        "schedule end before start",
        "apps/lectures/services.py",
        "    if details.end_date < details.start_date:\n",
        "    if False:\n",
    ),
    (
        "schedule needs a date on its days",
        "apps/lectures/services.py",
        '    if not starts:\n        errors.add("weekdays"',
        '    if False:\n        errors.add("weekdays"',
    ),
    (
        "extend needs a later date",
        "apps/lectures/services.py",
        "    elif end_date <= schedule.end_date:\n",
        "    elif False:\n",
    ),
    (
        "extend refused when stopped",
        "apps/lectures/services.py",
        '    if schedule.status != ScheduleStatus.ACTIVE:\n        errors.add("__all__", "A stopped schedule cannot be extended.")\n',
        '    if False:\n        errors.add("__all__", "A stopped schedule cannot be extended.")\n',
    ),
    (
        "stop cancels only lectures not started",
        "apps/lectures/services.py",
        "        starts_at__gt=timezone.now(),\n    ).update(status=LectureStatus.CANCELLED)\n",
        "    ).update(status=LectureStatus.CANCELLED)\n",
    ),
    (
        "stopped schedule cannot be edited",
        "apps/lectures/services.py",
        "    if old is not None and old.status != ScheduleStatus.ACTIVE:\n",
        "    if False:\n",
    ),
    (
        "schedule save queues the task",
        "apps/lectures/services.py",
        "    _enqueue(schedule)\n    notices.schedule_saved(schedule, created=True, actor=actor)\n",
        "    notices.schedule_saved(schedule, created=True, actor=actor)\n",
    ),
    (
        "generate task skips inactive institutes",
        "apps/lectures/tasks.py",
        "    institute = Institute.objects.filter(pk=institute_id, is_active=True).first()\n",
        "    institute = Institute.objects.filter(pk=institute_id).first()\n",
    ),
    (
        "schedule preview before save",
        "apps/lectures/views.py",
        "        if not form.is_confirmed():\n",
        "        if False:\n",
    ),
    (
        "schedule fingerprint follows values",
        "apps/lectures/forms.py",
        '        return hashlib.sha256("|".join(values).encode()).hexdigest()[:32]\n',
        '        return "same"\n',
    ),
    (
        "schedule weeks set the end date",
        "apps/lectures/forms.py",
        '            cleaned["end_date"] = start + timedelta(weeks=weeks, days=-1)\n',
        '            cleaned["end_date"] = start + timedelta(weeks=weeks)\n',
    ),
    (
        "schedule pages use for_user",
        "apps/lectures/views.py",
        "        schedules = RecurringSchedule.objects.for_user(self.request.user)\n        schedules = schedules.select_related",
        "        schedules = RecurringSchedule.unscoped.all()\n        schedules = schedules.select_related",
    ),
    (
        "schedule edit keeps its zone",
        "apps/lectures/views.py",
        "        if self.schedule is not None:\n            return self.schedule.time_zone\n",
        "",
    ),
    (
        "stopped schedule has no actions",
        "apps/lectures/ui.py",
        "        if schedule.status != ScheduleStatus.ACTIVE:\n            return ButtonRow(items=[])\n",
        "",
    ),
    (
        "seed reset removes lectures first",
        "apps/core/management/commands/seed_demo.py",
        "            deleted += reset_lectures(institute)\n",
        "",
    ),
    (
        "lecture list student filter needs batch on same row",
        "apps/lectures/services.py",
        '            subjects__student_links__batch_id=F("batch_id"),\n        ).distinct()\n',
        "        ).distinct()\n",
    ),
    (
        "lecture list student filter applies",
        "apps/lectures/services.py",
        "    if student_id is not None:\n        # One filter()",
        "    if False:\n        # One filter()",
    ),
    (
        "lecture list date_to includes the day",
        "apps/lectures/services.py",
        "        day_after = date_to + timedelta(days=1)\n",
        "        day_after = date_to\n",
    ),
    (
        "lecture list date_from applies",
        "apps/lectures/services.py",
        "    if date_from is not None:\n",
        "    if False:\n",
    ),
    (
        "calendar week starts on monday",
        "apps/lectures/services.py",
        "    monday = anchor - timedelta(days=anchor.weekday())\n",
        "    monday = anchor\n",
    ),
    (
        "calendar month shows whole weeks",
        "apps/lectures/services.py",
        "            first=month - timedelta(days=month.weekday()),\n",
        "            first=month,\n",
    ),
    (
        "calendar lectures include the last day",
        "apps/lectures/services.py",
        "    end = combine_local(last + timedelta(days=1), time.min)\n",
        "    end = combine_local(last, time.min)\n",
    ),
    (
        "calendar lectures use for_user",
        "apps/lectures/services.py",
        "        Lecture.objects.for_user(user)\n        .filter(starts_at__gte=start, starts_at__lt=end)\n",
        "        Lecture.objects.all()\n        .filter(starts_at__gte=start, starts_at__lt=end)\n",
    ),
    (
        "calendar days use the viewer date",
        "apps/lectures/ui.py",
        "        day = timezone.localtime(lecture.starts_at).date()\n",
        "        day = lecture.starts_at.date()\n",
    ),
    (
        "calendar refuses edge years",
        "apps/lectures/views.py",
        "    return day if MINYEAR < day.year < MAXYEAR else None\n",
        "    return day\n",
    ),
    (
        "guardian children use for_user",
        "apps/people/services.py",
        '    return list(\n        StudentProfile.objects.for_user(user)\n        .select_related("user")\n',
        '    return list(\n        StudentProfile.objects.all()\n        .select_related("user")\n',
    ),
    (
        "guardian subjects are the child's",
        "apps/lectures/views.py",
        "        return super().subject_rows().filter(student_links__student=self.child)\n",
        "        return super().subject_rows()\n",
    ),
    (
        "guardian one child has no child select",
        "apps/people/views.py",
        "        if len(self.children) < 2:\n",
        "        if False:\n",
    ),
    (
        "lecture list drops bad dates",
        "apps/lectures/views.py",
        '            if key in filters and calendar_day(filters[key]) is None:\n                filters[key] = ""\n',
        "            if key in filters and calendar_day(filters[key]) is None:\n                pass\n",
    ),
    (
        "filter bar kept select does not count",
        "apps/ui/components/nav.py",
        '            if not _get(f, "hidden", False) and not _get(f, "kept", False)\n',
        '            if not _get(f, "hidden", False)\n',
    ),
    (
        "filter bar clear keeps kept values",
        "apps/ui/components/nav.py",
        '            [(_get(f, "name"), _value(f)) for f in ctx["filters"] if _get(f, "kept")]\n',
        '            [(_get(f, "name"), _value(f)) for f in ctx["filters"] if False]\n',
    ),
    (
        "calendar item unsafe url is dropped",
        "apps/ui/components/lectures.py",
        "    items = [replace(item, url=safe_url(item.url) or None) for item in day.items]\n",
        "    items = list(day.items)\n",
    ),
    (
        "calendar phone list keeps month days",
        "apps/ui/components/lectures.py",
        '        ctx["busy_days"] = [day for day in days if day.items and day.in_month]\n',
        '        ctx["busy_days"] = [day for day in days if day.items]\n',
    ),
    (
        "join soon before the window",
        "apps/lectures/services.py",
        "    if now < join_opens_at(lecture, window):\n        return JOIN_SOON\n",
        "    if False:\n        return JOIN_SOON\n",
    ),
    (
        "join opens only when live",
        "apps/lectures/services.py",
        "    if lecture.status == LectureStatus.LIVE:\n        return JOIN_OPEN\n",
        "    if lecture.status == LectureStatus.SCHEDULED:\n        return JOIN_OPEN\n",
    ),
    (
        "join ends with the lecture",
        "apps/lectures/services.py",
        "    if lecture.status in CLOSED_STATUSES or now >= lecture.ends_at:\n",
        "    if lecture.status in CLOSED_STATUSES:\n",
    ),
    (
        "join none for in person",
        "apps/lectures/services.py",
        "        or lecture.delivery_mode != DeliveryMode.MANUAL_LINK\n",
        "        or False\n",
    ),
    (
        "join window from settings",
        "apps/lectures/services.py",
        "    return DEFAULT_JOIN_WINDOW if minutes is None else minutes\n",
        "    return DEFAULT_JOIN_WINDOW\n",
    ),
    (
        "next lecture skips cancelled",
        "apps/lectures/services.py",
        "        .filter(status__in=OPEN_STATUSES)\n",
        "        .filter()\n",
    ),
    (
        "next lecture skips ended",
        "apps/lectures/services.py",
        '        .filter(ends_at_db__gt=now)\n        .select_related("teacher__user", "batch")\n',
        '        .filter()\n        .select_related("teacher__user", "batch")\n',
    ),
    (
        "next lecture uses for_user",
        "apps/lectures/services.py",
        "        Lecture.objects.for_user(user)\n        .filter(status__in=OPEN_STATUSES)\n",
        "        Lecture.objects.all()\n        .filter(status__in=OPEN_STATUSES)\n",
    ),
    (
        "lectures today leaves out cancelled",
        "apps/lectures/services.py",
        "        .exclude(status=LectureStatus.CANCELLED)\n        .count()\n",
        "        .count()\n",
    ),
    (
        "join view checks the state",
        "apps/lectures/views.py",
        "        if state == JOIN_OPEN and lecture.meeting_url:\n",
        "        if lecture.meeting_url:\n",
    ),
    (
        "join view uses for_user",
        "apps/lectures/views.py",
        '        lecture = get_object_or_404(\n            Lecture.objects.for_user(request.user), pk=kwargs["pk"]\n        )\n        window',
        '        lecture = get_object_or_404(Lecture.objects.all(), pk=kwargs["pk"])\n        window',
    ),
    (
        "join view is post only",
        "apps/lectures/views.py",
        '    allowed_roles = [Role.STUDENT]\n    http_method_names = ["post"]\n',
        '    allowed_roles = [Role.STUDENT]\n    http_method_names = ["get", "post"]\n\n    def get(self, request, *args, **kwargs):\n        return self.post(request, *args, **kwargs)\n',
    ),
    (
        "join button only when open",
        "apps/lectures/ui.py",
        '    if state == JOIN_OPEN:\n        url = reverse("student:lecture_join"',
        '    if state != JOIN_NONE:\n        url = reverse("student:lecture_join"',
    ),
    (
        "guardian list has no join",
        "apps/lectures/views.py",
        "        return {}  # guardians see the lectures; the student joins\n",
        "        return super().table_kwargs()\n",
    ),
    (
        "up next card polls",
        "apps/ui/templates/ui/components/countdown_card.html",
        '{% if refresh_url %} hx-get="{{ refresh_url }}"',
        '{% if False %} hx-get="{{ refresh_url }}"',
    ),
    (
        "countdown refresh url is safe",
        "apps/ui/components/lectures.py",
        "            refresh_url=safe_url(refresh_url),\n",
        "            refresh_url=refresh_url,\n",
    ),
    (
        "disabled button is not a link",
        "apps/ui/components/actions.py",
        "            url=safe_url(url) if url is not None and not disabled else None,\n",
        "            url=safe_url(url) if url is not None else None,\n",
    ),
    (
        "post button new tab has no opener",
        "apps/ui/templates/ui/components/post_button.html",
        ' target="_blank" rel="noopener noreferrer"',
        ' target="_blank"',
    ),
    (
        "guardian class row needs batch and subject",
        "apps/ui/views/portal_home.py",
        "            link.batch_id == lecture.batch_id and link.subject_id in subject_ids\n",
        "            link.subject_id in subject_ids\n",
    ),
    (
        "guardian upcoming leaves out cancelled",
        "apps/lectures/services.py",
        "OPEN_STATUSES = (LectureStatus.SCHEDULED, LectureStatus.LIVE)\n",
        "OPEN_STATUSES = tuple(LectureStatus.values)\n",
    ),
    (
        "clock shows the zone",
        "apps/ui/templates/ui/components/page_header.html",
        '{% now "T" %}</span>',
        "</span>",
    ),
    (
        "start opens with the window",
        "apps/lectures/services.py",
        "        and join_opens_at(lecture, window) <= now < lecture.ends_at\n",
        "        and now < lecture.ends_at\n",
    ),
    (
        "start needs scheduled",
        "apps/lectures/services.py",
        "        lecture.status == LectureStatus.SCHEDULED\n        and join_opens_at(lecture, window)",
        "        lecture.status != LectureStatus.CANCELLED\n        and join_opens_at(lecture, window)",
    ),
    (
        "start checks on the locked row",
        "apps/lectures/services.py",
        "        if not can_start(lecture, now=now, window=window):\n",
        "        if False:\n",
    ),
    (
        "start records the time",
        "apps/lectures/services.py",
        "        lecture.started_at = now\n",
        "        pass\n",
    ),
    (
        "end needs live",
        "apps/lectures/services.py",
        '        if lecture.status != LectureStatus.LIVE:\n            raise ValidationError("Only a live lecture can be ended.")\n',
        '        if False:\n            raise ValidationError("Only a live lecture can be ended.")\n',
    ),
    (
        "cancel refused after the end",
        "apps/lectures/services.py",
        "        if lecture.status != LectureStatus.SCHEDULED or now >= lecture.ends_at:\n",
        "        if lecture.status != LectureStatus.SCHEDULED:\n",
    ),
    (
        "cancel refused once started",
        "apps/lectures/services.py",
        "        if lecture.status != LectureStatus.SCHEDULED or now >= lecture.ends_at:\n",
        "        if now >= lecture.ends_at:\n",
    ),
    (
        "cancel leaves the schedule",
        "apps/lectures/services.py",
        '        lecture.follows_schedule = False\n        lecture.save(update_fields=["status", "follows_schedule", "updated_at"])\n',
        '        lecture.save(update_fields=["status", "follows_schedule", "updated_at"])\n',
    ),
    (
        "finish only past the end",
        "apps/lectures/services.py",
        "    ended = Lecture.objects.annotate(ends_at_db=ENDS_AT).filter(ends_at_db__lte=now)\n",
        "    ended = Lecture.objects.annotate(ends_at_db=ENDS_AT)\n",
    ),
    (
        "finish needs the tenant",
        "apps/lectures/services.py",
        '    count of both."""\n    require_tenant_context(institute)\n',
        '    count of both."""\n',
    ),
    (
        "taught minutes from start and end",
        "apps/lectures/services.py",
        "    if lecture.started_at and lecture.ended_at:\n",
        "    if False:\n",
    ),
    (
        "history lists finished only",
        "apps/lectures/services.py",
        '        .filter(status=LectureStatus.FINISHED)\n        .select_related("teacher__user", "batch")\n',
        '        .filter()\n        .select_related("teacher__user", "batch")\n',
    ),
    (
        "history uses for_user",
        "apps/lectures/services.py",
        "        Lecture.objects.for_user(user)\n        .filter(status=LectureStatus.FINISHED)\n",
        "        Lecture.objects.all()\n        .filter(status=LectureStatus.FINISHED)\n",
    ),
    (
        "history newest first",
        "apps/lectures/services.py",
        '    return lectures.order_by("-starts_at", "-pk")\n\n\n# Live lecture monitor',
        '    return lectures.order_by("starts_at", "pk")\n\n\n# Live lecture monitor',
    ),
    (
        "history teacher filter",
        "apps/lectures/services.py",
        '    if teacher_id is not None:\n        lectures = lectures.filter(teacher_id=teacher_id)\n    if batch_id is not None:\n        lectures = lectures.filter(batch_id=batch_id)\n    return lectures.order_by("-starts_at", "-pk")\n',
        '    if batch_id is not None:\n        lectures = lectures.filter(batch_id=batch_id)\n    return lectures.order_by("-starts_at", "-pk")\n',
    ),
    (
        "lecture page uses for_user",
        "apps/lectures/views.py",
        '        lectures = (\n            Lecture.objects.for_user(self.request.user)\n            .select_related("teacher__user", "batch", "schedule")\n',
        '        lectures = (\n            Lecture.objects.all()\n            .select_related("teacher__user", "batch", "schedule")\n',
    ),
    (
        "admin history needs people menu",
        "apps/lectures/views.py",
        "    menu_key = menu_keys.PEOPLE\n    active_item = None\n",
        "    menu_key = None\n    active_item = None\n",
    ),
    (
        "teacher table has no cancel",
        "apps/lectures/ui.py",
        '                    "clipboard-check", f"Attendance for {lecture.title}", url=url\n                )\n            ]\n        return []\n',
        '                    "clipboard-check", f"Attendance for {lecture.title}", url=url\n                )\n            ]\n        return super().state_actions(lecture)\n',
    ),
    (
        "admin list cancel only when cancellable",
        "apps/lectures/ui.py",
        "        return [cancel_dialog(lecture)] if can_cancel(lecture, self.now) else []\n",
        "        return [cancel_dialog(lecture)]\n",
    ),
    (
        "meeting link only while open",
        "apps/lectures/ui.py",
        "        and lecture.status in OPEN_STATUSES\n",
        "        and True\n",
    ),
    (
        "teacher up next offers start",
        "apps/lectures/views.py",
        "        if can_start(lecture, now=timezone.now(), window=window):\n            action = start_button(lecture)\n",
        "        if False:\n            action = start_button(lecture)\n",
    ),
    (
        "teacher page end only when live",
        "apps/lectures/views.py",
        "        if lecture.status == LectureStatus.LIVE:\n            return [end_dialog(lecture)]\n",
        "        if lecture.status != LectureStatus.CANCELLED:\n            return [end_dialog(lecture)]\n",
    ),
    (
        "finish task only active institutes",
        "apps/lectures/tasks.py",
        "    closed = 0\n    for institute in Institute.objects.filter(is_active=True):\n",
        "    closed = 0\n    for institute in Institute.objects.all():\n",
    ),
    (
        "monitor late needs past the start",
        "apps/lectures/services.py",
        "        late=_monitor_list(scheduled.filter(starts_at__lte=now, ends_at_db__gt=now)),\n",
        "        late=_monitor_list(scheduled.filter(ends_at_db__gt=now)),\n",
    ),
    (
        "monitor late leaves at the end",
        "apps/lectures/services.py",
        "        late=_monitor_list(scheduled.filter(starts_at__lte=now, ends_at_db__gt=now)),\n",
        "        late=_monitor_list(scheduled.filter(starts_at__lte=now)),\n",
    ),
    (
        "monitor late only scheduled",
        "apps/lectures/services.py",
        "    scheduled = lectures.filter(status=LectureStatus.SCHEDULED)\n",
        "    scheduled = lectures.exclude(status=LectureStatus.LIVE)\n",
    ),
    (
        "monitor soon is two hours",
        "apps/lectures/services.py",
        "            scheduled.filter(starts_at__gt=now, starts_at__lte=now + SOON_WINDOW)\n",
        "            scheduled.filter(starts_at__gt=now)\n",
    ),
    (
        "monitor uses for_user",
        "apps/lectures/services.py",
        "    lectures = (\n        Lecture.objects.for_user(user)\n        .annotate(ends_at_db=ENDS_AT)\n",
        "    lectures = (\n        Lecture.objects.all()\n        .annotate(ends_at_db=ENDS_AT)\n",
    ),
    (
        "monitor total leaves out cancelled",
        "apps/lectures/services.py",
        "            if status != LectureStatus.CANCELLED\n",
        "            if True\n",
    ),
    (
        "monitor today is today",
        "apps/lectures/services.py",
        '        .filter(starts_at__gte=start, starts_at__lt=end)\n        .values("status")\n',
        '        .filter(starts_at__gte=start)\n        .values("status")\n',
    ),
    (
        "monitor page needs dashboards menu",
        "apps/lectures/views.py",
        '    portal = "admin"\n    menu_key = menu_keys.DASHBOARDS\n    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]\n    title = "Lectures dashboard"\n',
        '    portal = "admin"\n    menu_key = None\n    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]\n    title = "Lectures dashboard"\n',
    ),
    (
        "live region refuses unsafe ids",
        "apps/ui/components/layout.py",
        '        if not re.fullmatch(r"[a-z][a-z0-9-]*", str(region_id)):\n',
        "        if False:\n",
    ),
    (
        "live region url is safe",
        "apps/ui/components/layout.py",
        "            url=safe_url(url),\n            seconds=int(seconds),\n",
        "            url=url,\n            seconds=int(seconds),\n",
    ),
    (
        "live region selects itself",
        "apps/ui/templates/ui/components/live_region.html",
        ' hx-select="#{{ region_id }}"',
        "",
    ),
    (
        "monitor running time from start",
        "apps/lectures/ui.py",
        "            return minutes_text(self.now - (lecture.started_at or lecture.starts_at))\n",
        "            return minutes_text(self.now - lecture.starts_at)\n",
    ),
    (
        "schedule lecture keeps its date",
        "apps/lectures/services.py",
        "        occurrence_date=starts_at.date(),  # starts_at is in the schedule's zone\n",
        "",
    ),
    (
        "taken dates use occurrence date",
        "apps/lectures/services.py",
        "        lecture.occurrence_date or timezone.localtime(lecture.starts_at, zone).date()\n",
        "        timezone.localtime(lecture.starts_at, zone).date()\n",
    ),
    (
        "lecture edit reads the locked row",
        "apps/lectures/services.py",
        "    _lock_teacher(details.teacher)\n    _lock_and_reload(lecture)\n    _check(lecture.institute, details, lecture)\n",
        "    _lock_teacher(details.teacher)\n    _check(lecture.institute, details, lecture)\n",
    ),
    (
        "generate reads the locked schedule",
        "apps/lectures/services.py",
        "    _lock_teacher(schedule.teacher)\n    _lock_and_reload(schedule)\n    if schedule.status != ScheduleStatus.ACTIVE:\n        return GenerateResult()\n",
        "    _lock_teacher(schedule.teacher)\n    if schedule.status != ScheduleStatus.ACTIVE:\n        return GenerateResult()\n",
    ),
    (
        "extend reads the locked schedule",
        "apps/lectures/services.py",
        "    require_tenant_context(schedule.institute)\n    _lock_and_reload(schedule)\n    errors = _Errors()\n",
        "    require_tenant_context(schedule.institute)\n    errors = _Errors()\n",
    ),
    (
        "demo seed uses the student's pair",
        "apps/lectures/demo.py",
        "        if (link.batch_id, link.subject_id) in shared:\n",
        "        if False:\n",
    ),
    (
        "closed lecture edit goes back",
        "apps/lectures/views.py",
        "        if self.lecture.status != LectureStatus.SCHEDULED:\n            # Audit P3-4",
        "        if False:\n            # Audit P3-4",
    ),
    (
        "stopped schedule pages go back",
        "apps/lectures/views.py",
        '        if self.schedule.status == ScheduleStatus.ACTIVE:\n            return None\n        messages.error(self.request, f"A stopped schedule',
        '        if True:\n            return None\n        messages.error(self.request, f"A stopped schedule',
    ),
    (
        "finish job: never started is not held",
        "apps/lectures/services.py",
        "    ).update(status=LectureStatus.NOT_HELD, updated_at=now)\n",
        "    ).update(status=LectureStatus.FINISHED, updated_at=now)\n",
    ),
    (
        "finish job: live becomes finished",
        "apps/lectures/services.py",
        '        pk__in=ended.filter(status=LectureStatus.LIVE).values("pk")\n',
        '        pk__in=ended.filter(status=LectureStatus.SCHEDULED).values("pk")\n',
    ),
    (
        "not held is a closed state for join",
        "apps/lectures/services.py",
        "CLOSED_STATUSES = (LectureStatus.FINISHED, LectureStatus.NOT_HELD)\n",
        "CLOSED_STATUSES = (LectureStatus.FINISHED,)\n",
    ),
    (
        "not held badge is amber",
        "apps/lectures/ui.py",
        '    LectureStatus.NOT_HELD: "warning",\n',
        '    LectureStatus.NOT_HELD: "neutral",\n',
    ),
    (
        "migration: only lectures with no start",
        "apps/lectures/migrations/0008_mark_never_started_not_held.py",
        '    Lecture.objects.filter(status="finished", started_at__isnull=True).update(\n',
        '    Lecture.objects.filter(status="finished").update(\n',
    ),
    (
        "monitor note counts not held",
        "apps/lectures/views.py",
        "        not_held = today.get(LectureStatus.NOT_HELD, 0)\n",
        "        not_held = 0\n",
    ),
    (
        "broker down makes the lectures now",
        "apps/lectures/services.py",
        "    try:\n        generate_schedule_lectures(institute_id, schedule_id)\n    except Exception:\n",
        "    try:\n        pass\n    except Exception:\n",
    ),
    (
        "broker down is caught",
        "apps/lectures/services.py",
        "    except KombuOperationalError:\n",
        "    except ZeroDivisionError:\n",
    ),
    (
        "inline failure is logged not raised",
        "apps/lectures/services.py",
        '    except Exception:\n        logger.exception(\n            "Could not make the lectures',
        '    except ZeroDivisionError:\n        logger.exception(\n            "Could not make the lectures',
    ),
    (
        "nightly goes on after a schedule fails",
        "apps/lectures/tasks.py",
        '                except Exception:\n                    logger.exception(\n                        "Nightly run',
        '                except ZeroDivisionError:\n                    logger.exception(\n                        "Nightly run',
    ),
    (
        "finish goes on after an institute fails",
        "apps/lectures/tasks.py",
        '            except Exception:\n                logger.exception("Finish run',
        '            except ZeroDivisionError:\n                logger.exception("Finish run',
    ),
    (
        "schedule list flags problems",
        "apps/lectures/views.py",
        "        return self.table_class(rows, problems=schedule_problems(rows))\n",
        "        return self.table_class(rows)\n",
    ),
    (
        "problem: inactive teacher",
        "apps/lectures/services.py",
        '    if schedule.teacher.status != ProfileStatus.ACTIVE:\n        return f"{schedule.teacher} is inactive',
        '    if False:\n        return f"{schedule.teacher} is inactive',
    ),
    (
        "problem: only active schedules",
        "apps/lectures/services.py",
        "    active = [row for row in schedules if row.status == ScheduleStatus.ACTIVE]\n",
        "    active = list(schedules)\n",
    ),
    (
        "meeting link button new tab",
        "apps/lectures/ui.py",
        '        "Open meeting link", url=lecture.meeting_url, icon="video", new_tab=True\n',
        '        "Open meeting link", url=lecture.meeting_url, icon="video"\n',
    ),
    (
        "preview save above the dates",
        "apps/lectures/views.py",
        "                blocks=[text, save, schedule_preview_list(preview.planned)]\n",
        "                blocks=[text, schedule_preview_list(preview.planned)]\n",
    ),
    (
        "button submit type",
        "apps/ui/templates/ui/components/button.html",
        "{% if submit %}submit{% else %}button{% endif %}",
        "button",
    ),
    (
        "attendance save needs a finished lecture",
        "apps/attendance/services.py",
        "        if not can_mark(lecture):\n",
        "        if False:\n",
    ),
    (
        "attendance save checks the roster",
        "apps/attendance/services.py",
        "        if not set(marks) <= expected:\n",
        "        if False:\n",
    ),
    (
        "attendance save checks the status",
        "apps/attendance/services.py",
        "        if not set(marks.values()) <= STATUS_KEYS:\n",
        "        if False:\n",
    ),
    (
        "attendance only for finished lectures",
        "apps/attendance/services.py",
        "    return lecture.status == LectureStatus.FINISHED\n",
        "    return True\n",
    ),
    (
        "attendance roster enrolled before the end",
        "apps/attendance/services.py",
        "        and enrolment.enrolled_at < lecture.ends_at\n",
        "        and True\n",
    ),
    (
        "attendance roster needs a lecture subject",
        "apps/attendance/services.py",
        "        and enrolment.subject_id in subject_ids\n",
        "        and True\n",
    ),
    (
        "attendance roster keeps marked students",
        "apps/attendance/services.py",
        "    return enrolled | set(marks)\n",
        "    return enrolled\n",
    ),
    (
        "attendance partial counts as attended",
        "apps/attendance/services.py",
        "ATTENDED = {AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.PARTIAL}\n",
        "ATTENDED = {AttendanceStatus.PRESENT, AttendanceStatus.LATE}\n",
    ),
    (
        "attendance for_user role scope",
        "apps/attendance/models.py",
        "        if role in INSTITUTE_WIDE_ROLES:\n            return scoped\n",
        "        if True:\n            return scoped\n",
    ),
    (
        "attendance for_user guardian link",
        "apps/attendance/models.py",
        '    Role.GUARDIAN: "student__guardian_links__guardian__user_id",\n',
        '    Role.GUARDIAN: "student__guardian_links__guardian__institute_id",\n',
    ),
    (
        "take attendance page refuses open lectures",
        "apps/attendance/views.py",
        "        if can_mark(self.lecture):\n",
        "        if True:\n",
    ),
    (
        "guardian switcher refuses unlinked children",
        "apps/people/views.py",
        "        if any(child.pk == wanted for child in self.children):\n",
        "        if True:\n",
    ),
    (
        "guardian switcher goes back only to guardian pages",
        "apps/people/views.py",
        "        return wanted if wanted.startswith(home) and wanted.isprintable() else home\n",
        "        return wanted or home\n",
    ),
    (
        "guardian switcher refuses control characters",
        "apps/people/views.py",
        "        return wanted if wanted.startswith(home) and wanted.isprintable() else home\n",
        "        return wanted if wanted.startswith(home) else home\n",
    ),
    (
        "guardian chosen child follows the session",
        "apps/people/services.py",
        "    chosen = [child for child in children if child.pk == wanted]\n",
        "    chosen = []\n",
    ),
    (
        "attendance records only expected lectures",
        "apps/attendance/services.py",
        "        if lecture.pk in marks or any(is_expected(lecture, e) for e in enrolments)\n",
        "        if True\n",
    ),
    (
        "attendance records only finished lectures",
        "apps/attendance/services.py",
        "        Lecture.objects.filter(status=LectureStatus.FINISHED)\n        .filter(Q(",
        "        Lecture.objects.filter()\n        .filter(Q(",
    ),
    (
        "attendance percent counts half of partial",
        "apps/attendance/services.py",
        "        attended = self.present + self.late + HALF * self.partial\n",
        "        attended = self.present + self.late + self.partial\n",
    ),
    (
        "admin attendance history scoped students",
        "apps/attendance/views.py",
        "        students = StudentProfile.objects.for_user(self.request.user)\n",
        "        students = StudentProfile.unscoped.all()\n",
    ),
    (
        "attendance subject filter lists own subjects",
        "apps/attendance/views.py",
        "            student_links__student=self.student\n",
        "            pk__gt=0\n",
    ),
    (
        "attendance by subject counts own subjects",
        "apps/attendance/services.py",
        "        for subject in own or subjects:\n",
        "        for subject in subjects:\n",
    ),
    (
        "attendance by month newest first",
        "apps/attendance/services.py",
        "        for month in sorted(groups, reverse=True)\n",
        "        for month in sorted(groups)\n",
    ),
    (
        "attendance summaries only expected lectures",
        "apps/attendance/services.py",
        "                or any(is_expected(lecture, e) for e in enrolments[pk])\n",
        "                or True\n",
    ),
    (
        "attendance leaves out inactive students (audit P4-1)",
        "apps/attendance/services.py",
        "    active = rows.filter(student__status=ProfileStatus.ACTIVE)\n",
        "    active = rows\n",
    ),
    (
        "health check is 503 when the database fails (S13)",
        "apps/core/health.py",
        '        return JsonResponse({"status": "error"}, status=503)\n',
        '        return JsonResponse({"status": "ok"})\n',
    ),
    (
        "proxy ssl header refuses a wrong name (S11)",
        "config/settings/proxy.py",
        "    if not HEADER_NAME.fullmatch(header):\n",
        "    if False:\n",
    ),
    (
        "proxy ssl header empty means no proxy (S11)",
        "config/settings/proxy.py",
        "    if not header:\n        return None\n",
        "    if not header:\n        pass\n",
    ),
    (
        "attendance to take only unmarked lectures (AT2)",
        "apps/attendance/services.py",
        "        .filter(status=LectureStatus.FINISHED, attendance__isnull=True)\n",
        "        .filter(status=LectureStatus.FINISHED)\n",
    ),
    (
        "attendance to take needs an expected student (AT2)",
        "apps/attendance/services.py",
        "    return [lecture for lecture in lectures if counts[lecture.pk].total]\n",
        "    return lectures\n",
    ),
    (
        "lecture form refuses a skipped time (P3-9)",
        "apps/lectures/forms.py",
        "            if wall_time_missing(local):\n",
        "            if False:\n",
    ),
    (
        "schedule refuses a skipped time (P3-9)",
        "apps/lectures/services.py",
        "    if missing is not None:\n",
        "    if False:\n",
    ),
    (
        "monitor lists show the first rows (LC13)",
        "apps/lectures/services.py",
        "    rows = list(lectures[:MONITOR_ROWS])\n",
        "    rows = list(lectures)\n",
    ),
    (
        "sidebar background grows with its items (P4-4)",
        "apps/ui/templates/ui/components/sidebar.html",
        '<aside class="sidebar flex min-h-full w-64',
        '<aside class="sidebar flex h-full w-64',
    ),
    (
        "attendance percent of marked classes (P4-5)",
        "apps/attendance/services.py",
        "        share = attended * 100 / self.marked\n",
        "        share = attended * 100 / self.total\n",
    ),
    (
        "attendance no percent before a mark (P4-5)",
        "apps/attendance/services.py",
        "        if not self.marked:\n",
        "        if not self.total:\n",
    ),
    (
        "attendance waiting badge for students (P4-5)",
        "apps/attendance/ui.py",
        '        return Badge(WAITING if waiting else NOT_MARKED, tone="neutral")\n',
        '        return Badge(NOT_MARKED, tone="neutral")\n',
    ),
    (
        "attendance no marks yet value (P4-5)",
        "apps/attendance/ui.py",
        "    return NO_MARKS if percent is None else percent_text(percent)\n",
        "    return percent_text(percent)\n",
    ),
    (
        "attendance card note counts marked (P4-5)",
        "apps/attendance/ui.py",
        "    if summary.not_marked:\n",
        "    if False:\n",
    ),
    (
        "attendance absent card only absent (P4-5)",
        "apps/attendance/ui.py",
        '            StatCard(summary.absent, "Absent", icon="x"),\n',
        '            StatCard(summary.absent + summary.not_marked, "Absent", icon="x"),\n',
    ),
    (
        "admin history keeps not marked (P4-5)",
        "apps/attendance/views.py",
        "    waiting = False\n",
        "    waiting = True\n",
    ),
    (
        "schedule preview lists the first dates (P4-6)",
        "apps/lectures/ui.py",
        "            for item in planned[:PREVIEW_ROWS]\n",
        "            for item in planned\n",
    ),
    (
        "schedule preview counts hidden skipped dates (P4-6)",
        "apps/lectures/ui.py",
        '    if not skipped:\n        return f"and {len(rest)} more {noun}."\n',
        '    if True:\n        return f"and {len(rest)} more {noun}."\n',
    ),
    (
        "a teacher sees only own assignments (5.1)",
        "apps/assessments/models.py",
        "            return scoped.filter(teacher__user_id=user_id)\n",
        "            return scoped\n",
    ),
    (
        "assignment enrolment is one row: batch and subject (5.1)",
        "apps/assessments/models.py",
        '    enrolled = Q(**{lookup: user_id, f"{_ENROLMENT}batch_id": F("batch_id")})\n',
        "    enrolled = Q(**{lookup: user_id})\n",
    ),
    (
        "assignment rows stay in one institute (5.1)",
        "apps/assessments/models.py",
        "            if related is not None and related.institute_id != self.institute_id:\n",
        "            if False:\n",
    ),
    (
        "marks cannot pass the total marks (5.1)",
        "apps/assessments/models.py",
        "            and self.marks > assignment.total_marks\n",
        "            and False\n",
    ),
    (
        "no answer after the due time is missed (5.1)",
        "apps/assessments/services.py",
        "        return SubmissionStatus.MISSED\n",
        "        return SubmissionStatus.PENDING\n",
    ),
    (
        "assignment needs the teacher's own subject (5.1)",
        "apps/assessments/services.py",
        "        if not linked:\n",
        "        if False:\n",
    ),
    (
        "batch and subject stay after the first answer (5.1)",
        "apps/assessments/services.py",
        "        if old is not None and old.submissions.exists():\n",
        "        if False:\n",
    ),
    (
        "assignment due time must be in the future (5.1)",
        "apps/assessments/services.py",
        "    if (old is None or details.due_at != old.due_at) and details.due_at <= now:\n",
        "    if False:\n",
    ),
    (
        "total marks cannot go below a grade (5.1)",
        "apps/assessments/services.py",
        "        if top is not None and details.total_marks < top:\n",
        "        if False:\n",
    ),
    (
        "assignment roster needs enrolment before the due time (5.1)",
        "apps/assessments/services.py",
        '        created_at__lt=assignment.due_at,\n        student__status=ProfileStatus.ACTIVE,\n    ).values_list("student_id", flat=True)\n',
        '        student__status=ProfileStatus.ACTIVE,\n    ).values_list("student_id", flat=True)\n',
    ),
    (
        "assignment roster leaves out inactive students (5.1)",
        "apps/assessments/services.py",
        '        created_at__lt=assignment.due_at,\n        student__status=ProfileStatus.ACTIVE,\n    ).values_list("student_id", flat=True)\n',
        '        created_at__lt=assignment.due_at,\n    ).values_list("student_id", flat=True)\n',
    ),
    (
        "submitted / total counts enrolment before the due time (5.1)",
        "apps/assessments/services.py",
        "            and created_at < assignment.due_at\n",
        "            and True\n",
    ),
    (
        "submitted / total leaves out inactive students (5.1)",
        "apps/assessments/services.py",
        "        batch_id__in={row.batch_id for row in assignments},\n        student__status=ProfileStatus.ACTIVE,\n",
        "        batch_id__in={row.batch_id for row in assignments},\n",
    ),
    (
        "answers to grade count only ungraded answers (5.1)",
        "apps/assessments/services.py",
        "    answers = Submission.objects.for_user(user).filter(marks__isnull=True).count()\n",
        "    answers = Submission.objects.for_user(user).count()\n",
    ),
    (
        "student list needs the enrolment's subject (5.1)",
        "apps/assessments/services.py",
        "            batch_id=batch_id, subject_id=link_subject_id, due_at__gt=created_at\n",
        "            batch_id=batch_id, due_at__gt=created_at\n",
    ),
    (
        "student list leaves out assignments due before enrolment (5.1)",
        "apps/assessments/services.py",
        "            batch_id=batch_id, subject_id=link_subject_id, due_at__gt=created_at\n",
        "            batch_id=batch_id, subject_id=link_subject_id\n",
    ),
    (
        "no answer after the due time is taken (5.1)",
        "apps/assessments/services.py",
        "        if not is_open(locked, now):\n",
        "        if False:\n",
    ),
    (
        "only expected students answer (5.1)",
        "apps/assessments/services.py",
        "        if not is_expected(locked, student):\n",
        "        if False:\n",
    ),
    (
        "a graded answer cannot change (5.1)",
        "apps/assessments/services.py",
        "        if row is not None and row.is_graded:\n",
        "        if False:\n",
    ),
    (
        "grade is 0 to the total marks (5.1)",
        "apps/assessments/services.py",
        "        if marks < 0 or marks > assignment.total_marks:\n",
        "        if marks < 0:\n",
    ),
    (
        "grade page answer belongs to the assignment (5.1)",
        "apps/assessments/views.py",
        '            rows, pk=self.kwargs["submission_pk"], assignment=self.assignment\n',
        '            rows, pk=self.kwargs["submission_pk"]\n',
    ),
    (
        "student page sends a late-enrolled student back (5.1)",
        "apps/assessments/views.py",
        "        if not is_expected(self.assignment, self.student):\n",
        "        if False:\n",
    ),
    (
        "no answer form after grading (5.1)",
        "apps/assessments/views.py",
        "        return is_open(self.assignment, self.now) and not graded\n",
        "        return is_open(self.assignment, self.now)\n",
    ),
    (
        "text block keeps line breaks (5.1)",
        "apps/ui/templates/ui/components/text_block.html",
        "whitespace-pre-line ",
        "",
    ),
    (
        "a teacher reads only their own question bank (5.2)",
        "apps/assessments/models.py",
        'QUESTION_LOOKUPS = {Role.TEACHER: "teacher__user_id"}\n',
        'QUESTION_LOOKUPS = {Role.TEACHER: "teacher__user_id", Role.STUDENT: "subject__student_links__student__user_id"}\n',
    ),
    (
        "a teacher reads only their own question options (5.2)",
        "apps/assessments/models.py",
        'OPTION_LOOKUPS = {Role.TEACHER: "question__teacher__user_id"}\n',
        'OPTION_LOOKUPS = {Role.TEACHER: "institute__isnull"}\n',
    ),
    (
        "question subject must be the teacher's (5.2)",
        "apps/assessments/services.py",
        "        if not taught:\n",
        "        if False:\n",
    ),
    (
        "short answer question has no options (5.2)",
        "apps/assessments/services.py",
        "        if details.options:\n",
        "        if False:\n",
    ),
    (
        "MCQ has 2 to 6 options (5.2)",
        "apps/assessments/services.py",
        "    if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:\n",
        "    if False:\n",
    ),
    (
        "MCQ option cannot be empty (5.2)",
        "apps/assessments/services.py",
        "    elif any(not option.strip() for option in options):\n",
        "    elif False:\n",
    ),
    (
        "MCQ options are different (5.2)",
        "apps/assessments/services.py",
        "    elif len({option.strip().casefold() for option in options}) < len(options):\n",
        "    elif False:\n",
    ),
    (
        "MCQ correct option is one of the options (5.2)",
        "apps/assessments/services.py",
        "    if details.correct is None or not 0 <= details.correct < len(options):\n",
        "    if details.correct is None:\n",
    ),
    (
        "question edit replaces the options (5.2)",
        "apps/assessments/services.py",
        "        QuestionOption.objects.filter(question=row).delete()\n",
        "",
    ),
    (
        "the chosen option is saved as correct (5.2)",
        "apps/assessments/services.py",
        "                is_correct=position - 1 == details.correct,\n",
        "                is_correct=position == details.correct,\n",
    ),
    (
        "question form short answer drops the option boxes (5.2)",
        "apps/assessments/forms.py",
        '        if cleaned.get("kind") != QuestionKind.MCQ:\n',
        "        if False:\n",
    ),
    (
        "question form refuses an empty correct box (5.2)",
        "apps/assessments/forms.py",
        "        if chosen is not None and chosen not in numbers:\n",
        "        if False:\n",
    ),
    (
        "question form maps the correct box past empty boxes (5.2)",
        "apps/assessments/forms.py",
        '        cleaned["correct_index"] = numbers.index(chosen) if chosen in numbers else None\n',
        '        cleaned["correct_index"] = chosen - 1 if chosen in numbers else None\n',
    ),
    (
        "question delete is POST only (5.2)",
        "apps/assessments/views.py",
        '    http_method_names = ["post"]\n',
        '    http_method_names = ["get", "post"]\n',
    ),
    (
        "students see only published quizzes (5.3)",
        "apps/assessments/models.py",
        "            _enrolled_or_own(lookup, own, user_id), is_published=True\n",
        "            _enrolled_or_own(lookup, own, user_id)\n",
    ),
    (
        "quiz questions are for staff only (5.3)",
        "apps/assessments/models.py",
        'QUIZ_QUESTION_LOOKUPS = {Role.TEACHER: "quiz__teacher__user_id"}\n',
        'QUIZ_QUESTION_LOOKUPS = {Role.TEACHER: "quiz__teacher__user_id", Role.STUDENT: "quiz__subject__student_links__student__user_id"}\n',
    ),
    (
        "quiz closes 10 minutes after the duration (5.3)",
        "apps/assessments/models.py",
        "            minutes=self.duration_minutes + QUIZ_GRACE_MINUTES\n",
        "            minutes=self.duration_minutes\n",
    ),
    (
        "unpublished quiz is a draft (5.3)",
        "apps/assessments/services.py",
        "    if not quiz.is_published:\n",
        "    if False:\n",
    ),
    (
        "published quiz is scheduled before it opens (5.3)",
        "apps/assessments/services.py",
        "    if now < quiz.opens_at:\n",
        "    if False:\n",
    ),
    (
        "only a published quiz has opened (5.3)",
        "apps/assessments/services.py",
        "    return quiz.is_published and (now or timezone.now()) >= quiz.opens_at\n",
        "    return (now or timezone.now()) >= quiz.opens_at\n",
    ),
    (
        "an opened quiz cannot change (5.3)",
        "apps/assessments/services.py",
        "    if has_opened(locked, now):\n",
        "    if False:\n",
    ),
    (
        "publish needs a question (5.3)",
        "apps/assessments/services.py",
        "        if not total:\n",
        "        if False:\n",
    ),
    (
        "publish needs a future opening (5.3)",
        "apps/assessments/services.py",
        "        if locked.opens_at <= now:\n",
        "        if False:\n",
    ),
    (
        "publish needs pass marks within the total (5.3)",
        "apps/assessments/services.py",
        "        if locked.pass_marks is not None and locked.pass_marks > total:\n",
        "        if False:\n",
    ),
    (
        "quiz edit keeps pass marks within the total (5.3)",
        "apps/assessments/services.py",
        "        if total and details.pass_marks > total:\n",
        "        if False:\n",
    ),
    (
        "quiz subject stays while it has questions (5.3)",
        "apps/assessments/services.py",
        "        if QuizQuestion.objects.filter(quiz=old).exists():\n",
        "        if False:\n",
    ),
    (
        "quiz opens in the future (5.3)",
        "apps/assessments/services.py",
        "    if (old is None or details.opens_at != old.opens_at) and details.opens_at <= now:\n",
        "    if False:\n",
    ),
    (
        "exam settings only for an exam (5.3)",
        "apps/assessments/services.py",
        "    exam = details.kind == QuizKind.EXAM  # SPEC 4.16: exam settings only\n",
        "    exam = True\n",
    ),
    (
        "quiz questions share its subject (5.3)",
        "apps/assessments/services.py",
        "                or question.subject_id != locked.subject_id\n",
        "                or False\n",
    ),
    (
        "quiz questions come from the teacher's bank (5.3)",
        "apps/assessments/services.py",
        "                question.teacher_id != locked.teacher_id\n",
        "                False\n",
    ),
    (
        "a question joins a quiz once (5.3)",
        "apps/assessments/services.py",
        "            if question.pk in taken:\n",
        "            if False:\n",
    ),
    (
        "remove takes an item of this quiz (5.3)",
        "apps/assessments/views.py",
        '            QuizQuestion.objects.filter(quiz=quiz), pk=self.kwargs["item_pk"]\n',
        '            QuizQuestion.objects.all(), pk=self.kwargs["item_pk"]\n',
    ),
    (
        "a question in a quiz stays in the bank (AS6)",
        "apps/assessments/services.py",
        "    if QuizQuestion.objects.filter(question=question).exists():\n",
        "    if False:\n",
    ),
    (
        "a question of an opened quiz cannot change (AS6)",
        "apps/assessments/services.py",
        "    if question is not None and question_in_opened_quiz(question):\n",
        "    if False:\n",
    ),
    (
        "a question changes until its quiz opens (AS6)",
        "apps/assessments/services.py",
        "        quiz__opens_at__lte=now or timezone.now(),\n",
        "",
    ),
    (
        "one attempt per student and quiz (5.3)",
        "apps/assessments/services.py",
        "        if existing is not None:\n",
        "        if False:\n",
    ),
    (
        "start only while the quiz is live (5.3)",
        "apps/assessments/services.py",
        "        if quiz_status(locked, now) != QuizStatus.LIVE:\n",
        "        if False:\n",
    ),
    (
        "only the quiz's students start it (5.3)",
        "apps/assessments/services.py",
        "        if not is_quiz_student(locked, student):\n",
        "        if False:\n",
    ),
    (
        "inactive students cannot start a quiz (5.3)",
        "apps/assessments/services.py",
        "        subject_id=quiz.subject_id,\n        student__status=ProfileStatus.ACTIVE,\n",
        "        subject_id=quiz.subject_id,\n",
    ),
    (
        "attempt deadline stops at the quiz close (5.3)",
        "apps/assessments/services.py",
        "                now + timedelta(minutes=locked.duration_minutes), locked.closes_at\n",
        "                now + timedelta(minutes=locked.duration_minutes), now + timedelta(days=1)\n",
    ),
    (
        "an answer option belongs to its question (5.3)",
        "apps/assessments/services.py",
        '            if value not in (None, "") and str(value) not in options:\n',
        "            if False:\n",
    ),
    (
        "MCQ marks need the correct option (5.3)",
        "apps/assessments/services.py",
        "        right = row.option is not None and row.option.is_correct\n",
        "        right = row.option is not None\n",
    ),
    (
        "a short answer leaves the attempt submitted (5.3)",
        "apps/assessments/services.py",
        "    attempt.status = AttemptStatus.SUBMITTED if short else AttemptStatus.GRADED\n",
        "    attempt.status = AttemptStatus.GRADED\n",
    ),
    (
        "submitted time is no later than the deadline (5.3)",
        "apps/assessments/services.py",
        "    attempt.submitted_at = min(now, attempt.deadline)\n",
        "    attempt.submitted_at = now\n",
    ),
    (
        "a submitted attempt cannot change (5.3)",
        "apps/assessments/services.py",
        "        if locked.status != AttemptStatus.IN_PROGRESS:\n",
        "        if False:\n",
    ),
    (
        "answers after the grace minute are late (5.3)",
        "apps/assessments/services.py",
        "        late = now > locked.deadline + ANSWER_GRACE\n",
        "        late = now > locked.deadline + ANSWER_GRACE * 5\n",
    ),
    (
        "late answers are not saved (5.3)",
        "apps/assessments/services.py",
        "        if not late:\n",
        "        if True:\n",
    ),
    (
        "a late save submits the attempt (5.3)",
        "apps/assessments/services.py",
        "        if submit or late:\n",
        "        if submit:\n",
    ),
    (
        "an open attempt past its deadline is submitted (5.3)",
        "apps/assessments/services.py",
        "        or now <= attempt.deadline + ANSWER_GRACE\n",
        "        or True\n",
    ),
    (
        "guardians see no quiz answers (5.3)",
        "apps/assessments/models.py",
        "ANSWER_LOOKUPS = {\n",
        'ANSWER_LOOKUPS = {\n    Role.GUARDIAN: "attempt__student__guardian_links__guardian__user_id",\n',
    ),
    (
        "closed quiz without an attempt is not taken (5.3)",
        "apps/assessments/ui.py",
        '        return Badge(NOT_TAKEN, tone="danger")\n',
        "        return quiz_status_badge(row.status)\n",
    ),
    (
        "timer submit is saved as automatic (5.3)",
        "apps/assessments/views.py",
        '        auto = bool(post.get("auto_submit"))\n',
        "        auto = False\n",
    ),
    (
        "no paper after the attempt is submitted (5.3)",
        "apps/assessments/views.py",
        "        if self.attempt is None or self.attempt.status != AttemptStatus.IN_PROGRESS:\n",
        "        if self.attempt is None:\n",
    ),
    (
        "an open attempt cannot be marked (5.3 2b)",
        "apps/assessments/services.py",
        "        if locked.status == AttemptStatus.IN_PROGRESS:\n            raise ValidationError(MARK_OPEN_MESSAGE)\n",
        "        if False:\n            raise ValidationError(MARK_OPEN_MESSAGE)\n",
    ),
    (
        "marks are 0 to the question's marks (5.3 2b)",
        "apps/assessments/services.py",
        "            if value is None or not 0 <= value <= question.marks:\n",
        "            if value is None:\n",
    ),
    (
        "the score adds the MCQ marks (5.3 2b)",
        "apps/assessments/services.py",
        "            (row.marks for row in saved.values() if row.marks is not None),\n",
        "            (row.marks for row in saved.values() if row.marks is not None and row.option_id is None),\n",
    ),
    (
        "marking grades the attempt (5.3 2b)",
        "apps/assessments/services.py",
        "        locked.status = AttemptStatus.GRADED\n",
        "        locked.status = AttemptStatus.SUBMITTED\n",
    ),
    (
        "results submit expired attempts (5.3 2b)",
        "apps/assessments/services.py",
        "        row.student_id: close_expired(row, now=now)\n",
        "        row.student_id: row\n",
    ),
    (
        "results leave out inactive students (5.3 2b)",
        "apps/assessments/services.py",
        '        subject_id=quiz.subject_id,\n        student__status=ProfileStatus.ACTIVE,\n    ).values_list("student_id", flat=True)\n',
        '        subject_id=quiz.subject_id,\n    ).values_list("student_id", flat=True)\n',
    ),
    (
        "to mark counts submitted attempts only (5.3 2b)",
        "apps/assessments/services.py",
        "            to_mark=sum(status == AttemptStatus.SUBMITTED for status in own.values()),\n",
        "            to_mark=len(own),\n",
    ),
    (
        "the attempt page needs the quiz of the URL (5.3 2b)",
        "apps/assessments/views.py",
        'pk=self.kwargs["attempt_pk"], quiz=self.quiz)\n',
        'pk=self.kwargs["attempt_pk"])\n',
    ),
    (
        "the attempt page submits an expired attempt (5.3 2b)",
        "apps/assessments/views.py",
        "        self.attempt = close_expired(attempt)\n",
        "        self.attempt = attempt\n",
    ),
    (
        "no marks form while the student answers (5.3 2b)",
        "apps/assessments/views.py",
        "        return bool(self.short) and self.attempt.status != AttemptStatus.IN_PROGRESS\n",
        "        return bool(self.short)\n",
    ),
    (
        "results show not taken once closed (5.3 2b)",
        "apps/assessments/ui.py",
        '    if status == QuizStatus.CLOSED:\n        return Badge(NOT_TAKEN, tone="danger")\n    return Badge("Not started"',
        '    if False:\n        return Badge(NOT_TAKEN, tone="danger")\n    return Badge("Not started"',
    ),
    (
        "demo reset deletes attempts first (5.3 2b)",
        "apps/assessments/demo.py",
        "    attempts, _ = QuizAttempt.unscoped.filter(institute=institute).delete()\n",
        "    attempts = 0\n",
    ),
    (
        "only an exam records flags (5.3 2c)",
        "apps/assessments/services.py",
        "    if quiz.kind != QuizKind.EXAM:\n        return set()\n",
        "    if False:\n        return set()\n",
    ),
    (
        "tab flags only when the exam asks (5.3 2c)",
        "apps/assessments/services.py",
        "    if quiz.flag_tab_leaving:\n",
        "    if True:\n",
    ),
    (
        "full screen flags only when the exam asks (5.3 2c)",
        "apps/assessments/services.py",
        "    if quiz.require_full_screen:\n        kinds.add(",
        "    if True:\n        kinds.add(",
    ),
    (
        "no flags after the attempt ends (5.3 2c)",
        "apps/assessments/services.py",
        "            locked.status != AttemptStatus.IN_PROGRESS\n            or now > locked.deadline + ANSWER_GRACE\n",
        "            now > locked.deadline + ANSWER_GRACE\n",
    ),
    (
        "no flags after the deadline (5.3 2c)",
        "apps/assessments/services.py",
        "            or now > locked.deadline + ANSWER_GRACE\n            or kind not in flagged_kinds(locked.quiz)\n",
        "            or kind not in flagged_kinds(locked.quiz)\n",
    ),
    (
        "flags stop at the cap (5.3 2c)",
        "apps/assessments/services.py",
        "            or AttemptEvent.objects.filter(attempt=locked).count() >= MAX_EVENTS\n",
        "",
    ),
    (
        "students do not read flags (5.3 2c)",
        "apps/assessments/models.py",
        'EVENT_LOOKUPS = {Role.TEACHER: "attempt__quiz__teacher__user_id"}\n',
        'EVENT_LOOKUPS = {\n    Role.TEACHER: "attempt__quiz__teacher__user_id",\n    Role.STUDENT: "attempt__student__user_id",\n}\n',
    ),
    (
        "the paper shows the exam guard (5.3 2c)",
        "apps/assessments/views.py",
        "        if kinds:\n            guard.append(\n",
        "        if False:\n            guard.append(\n",
    ),
    (
        "results show the flag counts (5.3 2c)",
        "apps/assessments/views.py",
        "            flags=event_counts(self.quiz) if flagged_kinds(self.quiz) else None,\n",
        "            flags=None,\n",
    ),
    (
        "the event view uses the student's own attempt (5.3 2c)",
        "apps/assessments/views.py",
        "        attempt = QuizAttempt.objects.filter(quiz=quiz, student=self.student).first()\n        if attempt is not None:\n            log_attempt_event(",
        "        attempt = QuizAttempt.objects.filter(quiz=quiz).first()\n        if attempt is not None:\n            log_attempt_event(",
    ),
    (
        "admin quizzes need the academic menu (5.3 2d)",
        "apps/assessments/views.py",
        "    menu_key = menu_keys.ACADEMIC\n",
        "    menu_key = None\n",
    ),
    (
        "admin quiz page has no mark links (5.3 2d)",
        "apps/assessments/views.py",
        "    open_links = False\n",
        "    open_links = True\n",
    ),
    (
        "admin quiz page cannot edit (5.3 2d)",
        "apps/assessments/views.py",
        "    def can_edit(self) -> bool:\n        return False\n",
        "    def can_edit(self) -> bool:\n        return True\n",
    ),
    (
        "admin quiz page shows results only once opened (5.3 2d)",
        "apps/assessments/views.py",
        "        if not has_opened(self.quiz, self.now):\n            return [questions]\n",
        "        if False:\n            return [questions]\n",
    ),
    (
        "results hide the mark buttons when asked (5.3 2d)",
        "apps/assessments/ui.py",
        '            *([Column("actions", "", self.open_button)] if self.open_links else []),\n',
        '            Column("actions", "", self.open_button),\n',
    ),
    (
        "guardian sees a quiz score only once graded (5.4)",
        "apps/assessments/ui.py",
        '    if attempt is None or attempt.status != AttemptStatus.GRADED:\n        return "-"\n',
        '    if attempt is None:\n        return "-"\n',
    ),
    (
        "guardian lists have no open button (5.4)",
        "apps/assessments/ui.py",
        '    return [column for column in columns if column.key != "actions"]\n',
        "    return columns\n",
    ),
    (
        "guardian lists follow the chosen child (5.4)",
        "apps/assessments/views.py",
        "    @property\n    def student(self) -> StudentProfile | None:\n        return self.child\n",
        "    @property\n    def student(self) -> StudentProfile | None:\n        return StudentProfile.objects.first()\n",
    ),
    (
        "student answers wait for the quiz to close (5.4)",
        "apps/assessments/views.py",
        "        closed = self.status == QuizStatus.CLOSED\n",
        "        closed = True\n",
    ),
    (
        "student answers wait for the attempt to end (5.4)",
        "apps/assessments/views.py",
        "        if closed and attempt.status != AttemptStatus.IN_PROGRESS:\n",
        "        if closed:\n",
    ),
    (
        "answers to grade counts quiz attempts (5.4)",
        "apps/assessments/services.py",
        "    return answers + attempts\n",
        "    return answers\n",
    ),
    (
        "answers to grade counts only submitted attempts (5.4)",
        "apps/assessments/services.py",
        "        .filter(status=AttemptStatus.SUBMITTED)\n        .count()\n",
        "        .count()\n",
    ),
    (
        "a student who left keeps their own work (AS12)",
        "apps/assessments/models.py",
        "    return enrolled | Q(**{own: user_id})\n",
        "    return enrolled\n",
    ),
    (
        "the timer flag counts only near the deadline (AS13)",
        "apps/assessments/services.py",
        "        timer = auto and now >= locked.deadline - ANSWER_GRACE\n",
        "        timer = auto\n",
    ),
    (
        "a closed quiz says when it closed (AS15)",
        "apps/assessments/ui.py",
        '        return f"Closed {when(quiz.closes_at)}."\n',
        '        return f"Closed. It closes {when(quiz.closes_at)}."\n',
    ),
    (
        "notify leaves out inactive users (6.1)",
        "apps/notifications/services.py",
        "        if user.pk in seen or not user.is_active or user.institute_id != institute.pk:\n",
        "        if user.pk in seen or user.institute_id != institute.pk:\n",
    ),
    (
        "notify leaves out other institutes (6.1)",
        "apps/notifications/services.py",
        "        if user.pk in seen or not user.is_active or user.institute_id != institute.pk:\n",
        "        if user.pk in seen or not user.is_active:\n",
    ),
    (
        "notify respects the alert switches (6.1)",
        "apps/notifications/services.py",
        "        if switch and not getattr(user, switch):\n",
        "        if False:\n",
    ),
    (
        "notification links stay in the site (6.1)",
        "apps/notifications/services.py",
        '_LINK = re.compile(r"^/(?!/)[^\\s\\\\]*$")\n',
        '_LINK = re.compile(r".*")\n',
    ),
    (
        "a user sees only their own notifications (6.1)",
        "apps/notifications/models.py",
        '        return scoped.filter(user_id=getattr(user, "pk", None))\n',
        "        return scoped\n",
    ),
    (
        "notifications are kept for 90 days (6.1)",
        "apps/notifications/services.py",
        "Notification.objects.filter(created_at__lt=cutoff)",
        "Notification.objects.filter(created_at__lte=cutoff)",
    ),
    (
        "bell parts give a signed-out user 204 (6.1)",
        "apps/notifications/views.py",
        "        if not request.user.is_authenticated:\n            return HttpResponse(status=204)\n",
        "",
    ),
    (
        "the back path refuses a backslash (6.1)",
        "apps/notifications/views.py",
        '    bad = "\\\\" in path or not value.isprintable()',
        "    bad = not value.isprintable()",
    ),
    (
        "the super admin has no bell (6.1)",
        "apps/ui/components/nav.py",
        '        ctx["enabled"] = getattr(self.props["user"], "role", "") in BELL_ROLES\n',
        '        ctx["enabled"] = True\n',
    ),
    (
        "teachers get no fee alert switch (6.1)",
        "apps/accounts/forms.py",
        '        return ["class_alerts"]\n',
        "        return list(ALERT_FIELDS)\n",
    ),
    (
        "profile service changes only the switches (6.1)",
        "apps/accounts/services.py",
        '        if name in ("class_alerts", "fee_alerts"):\n',
        "        if True:\n",
    ),
    (
        "the person who saves gets no notification (6.2)",
        "apps/notifications/audience.py",
        "    return [user for user in users if user.pk != actor_id]\n",
        "    return list(users)\n",
    ),
    (
        "guardians hear about their child's class (6.2)",
        "apps/notifications/audience.py",
        "    if not guardian_url or not students:\n",
        "    if True:\n",
    ),
    (
        "inactive students get no class notification (6.2)",
        "apps/notifications/audience.py",
        "        student__status=ProfileStatus.ACTIVE,\n",
        "",
    ),
    (
        "notification times are the recipient's (6.2)",
        "apps/notifications/services.py",
        "        with timezone.override(zone):\n",
        "        with timezone.override(timezone.get_current_timezone()):\n",
    ),
    (
        "only a new lecture plan is notified (6.2)",
        "apps/lectures/services.py",
        "    if _plan_of(saved.lecture) != before:\n",
        "    if True:\n",
    ),
    (
        "a new lecture time is reminded again (6.2)",
        "apps/lectures/services.py",
        "        lecture.reminded_at = None  # remind again before the new time\n",
        "        pass\n",
    ),
    (
        "reminders cover the next 15 minutes only (6.2)",
        "apps/lectures/services.py",
        "        starts_at__lte=now + REMIND_BEFORE,\n",
        "",
    ),
    (
        "a lecture is reminded once (6.2)",
        "apps/lectures/services.py",
        "        reminded_at__isnull=True,\n",
        "",
    ),
    (
        "the lecture page passes the person who saves (6.2)",
        "apps/lectures/views.py",
        "        return create_lecture(self.get_institute(), details, actor=self.request.user)\n",
        "        return create_lecture(self.get_institute(), details)\n",
    ),
    (
        "only the first answer tells the teacher (6.2)",
        "apps/assessments/services.py",
        "        if first:\n            notices.answer_received(row)\n",
        "        notices.answer_received(row)\n",
    ),
    (
        "an MCQ quiz graded at submit tells the guardian only (6.2)",
        "apps/assessments/services.py",
        "        notices.quiz_graded(attempt, score, to_student=False)\n",
        "        notices.quiz_graded(attempt, score)\n",
    ),
    (
        "guardian-only notices skip the student (6.2)",
        "apps/notifications/audience.py",
        "    if to_students:\n",
        "    if True:\n",
    ),
    (
        "quiz reminders cover the next hour only (6.2)",
        "apps/assessments/services.py",
        "            opens_at__lte=now + QUIZ_REMIND_BEFORE,\n",
        "",
    ),
    (
        "drafts get no quiz reminder (6.2)",
        "apps/assessments/services.py",
        "            is_published=True,\n",
        "",
    ),
    (
        "a quiz is reminded once (6.2)",
        "apps/assessments/services.py",
        "            reminded_at__isnull=True,\n",
        "",
    ),
    (
        "back to draft clears the quiz reminder (6.2)",
        "apps/assessments/services.py",
        "        locked.reminded_at = None\n",
        "",
    ),
    (
        "portal access is told only on a change (6.2)",
        "apps/people/services.py",
        "    if changed:\n",
        "    if True:\n",
    ),
    (
        "students reach only the teachers of their batches (6.3)",
        "apps/messaging/services.py",
        "        admins | Q(role=Role.TEACHER, teacher_profile__in=teachers)\n",
        "        admins | Q(role=Role.TEACHER)\n",
    ),
    (
        "teachers reach the students of their batches (6.3)",
        "apps/messaging/services.py",
        "            | Q(role=Role.STUDENT, student_profile__in=students)\n",
        "            | Q(role=Role.STUDENT)\n",
    ),
    (
        "a message needs a reachable recipient (6.3)",
        "apps/messaging/services.py",
        "    if recipient is None or not can_message(sender, recipient):\n",
        "    if recipient is None:\n",
    ),
    (
        "people see only their own threads (6.3)",
        "apps/messaging/models.py",
        '        return scoped.filter(members__user_id=getattr(user, "pk", None)).distinct()\n',
        "        return scoped\n",
    ),
    (
        "thread state and drafts are the owner's only (6.3)",
        "apps/messaging/models.py",
        '        return scoped.filter(**{self.owner_field: getattr(user, "pk", None)})\n',
        "        return scoped\n",
    ),
    (
        "only a member replies (6.3)",
        "apps/messaging/services.py",
        "    if member is None:\n        raise ValidationError(NOT_A_MEMBER)\n",
        "",
    ),
    (
        "no reply when no one else is active (6.3)",
        "apps/messaging/services.py",
        "    if not others.filter(user__is_active=True).exists():\n",
        "    if False:\n",
    ),
    (
        "delete forever only from the trash (6.3)",
        "apps/messaging/services.py",
        "    if member.trashed_at is None:\n",
        "    if False:\n",
    ),
    (
        "unread means newer than the last read (6.3)",
        "apps/messaging/services.py",
        "            is_unread=Exists(newer),\n",
        "            is_unread=Exists(_from_others(user)),\n",
    ),
    (
        "a reply brings the thread back for the others (6.3)",
        "apps/messaging/services.py",
        "    others.update(trashed_at=None, deleted=False)\n",
        "",
    ),
    (
        "a thread deleted forever stays closed (6.3)",
        "apps/messaging/views.py",
        "        if self.member is None or self.member.deleted:\n",
        "        if self.member is None:\n",
    ),
    (
        "thread actions need a member (6.3)",
        "apps/messaging/views.py",
        "        if member is None or member.deleted:\n",
        "        if False:\n",
    ),
    (
        "the unread badge gives a signed-out user 204 (6.3)",
        "apps/messaging/views.py",
        "        if not request.user.is_authenticated:\n            return HttpResponse(status=204)\n",
        "",
    ),
    (
        "a signed-out user on a feature page goes to sign in (6.3)",
        "apps/core/mixins/access.py",
        '        if key and getattr(user, "is_authenticated", False):\n',
        "        if key:\n",
    ),
    (
        "drafts open only for their owner (6.3)",
        "apps/messaging/views.py",
        'Draft.objects.for_user(user), pk=id_param(params.get("draft"))',
        'Draft.objects.all(), pk=id_param(params.get("draft"))',
    ),
    (
        "only the office sends a broadcast (6.3)",
        "apps/messaging/services.py",
        "    if sender.role not in ADMIN_ROLES:\n",
        "    if False:\n",
    ),
    (
        "a batch broadcast reaches the guardians too (6.3)",
        "apps/messaging/services.py",
        "            | Q(guardian_profile__student_links__student__in=students)\n",
        "",
    ),
    (
        "broadcast threads stay out of Sent (6.3)",
        "apps/messaging/services.py",
        ".exclude(thread__broadcast__sender=user)",
        "",
    ),
    (
        "the monitor role filter keeps that role (6.3)",
        "apps/messaging/services.py",
        "        rows = rows.filter(members__user__role=role)\n",
        "        pass\n",
    ),
    (
        "a broadcast skips its sender (6.3)",
        "apps/messaging/services.py",
        ".exclude(pk=sender.pk)",
        "",
    ),
    (
        "a hidden field shows no label (Phase 6 audit)",
        "apps/ui/templates/ui/forms/field.html",
        "{% if field.is_hidden %}{{ field }}{% elif ",
        "{% if ",
    ),
    (
        "inline BlockStack is one line (Phase 6 audit)",
        "apps/ui/templates/ui/components/block_stack.html",
        '{% if inline %}<div class="flex',
        '{% if False %}<div class="flex',
    ),
    (
        "demo admins have names (Phase 6 audit)",
        "apps/core/management/commands/seed_demo.py",
        '        user.first_name, user.last_name = DEMO_NAMES.get(email, ("", ""))\n',
        "",
    ),
]


def _git_dir() -> Path:
    """The repository's shared .git folder, the same for every worktree."""
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return (ROOT / common).resolve()


# In the shared .git folder, so every worktree uses one cache.
CACHE = _git_dir() / "mutation_cache.json"
OLD_CACHE = ROOT / ".mutation_cache.json"  # before worktrees; read once
# pytest exit codes that say nothing about the mutation: 4 = a cached test no
# longer exists, 5 = no tests collected. Move on to the next stage.
NO_VERDICT = {4, 5}
FAILED_LINE = re.compile(r"^FAILED (\S+?)(?: - |$)", re.M)


class Worker:
    """A detached worktree at HEAD with its own test database."""

    def __init__(self, number: int, base: Path) -> None:
        self.path = base / f"w{number}"
        subprocess.run(
            ["git", "worktree", "add", "--detach", "-q", str(self.path), "HEAD"],
            cwd=ROOT,
            check=True,
        )
        css = ROOT / "static/css/app.css"  # built file, not in git
        if css.exists():
            (self.path / "static/css/app.css").write_bytes(css.read_bytes())
        self.env = {**os.environ, "TEST_DB_NAME": f"lms_test_mut{number}"}
        self.fresh = True

    def pytest(self, targets: list[str]) -> subprocess.CompletedProcess[str]:
        # The first run builds this worker's database; later runs reuse it.
        db_flag = "--create-db" if self.fresh else "--reuse-db"
        self.fresh = False
        return subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-x", db_flag]
            + ["-p", "no:cacheprovider", *targets],
            cwd=self.path,
            env=self.env,
            capture_output=True,
            text=True,
        )

    def restore(self, path: str) -> None:
        subprocess.run(["git", "checkout", "--", path], cwd=self.path, check=True)

    def remove(self) -> None:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(self.path)],
            cwd=ROOT,
            check=False,
        )


def stages(name: str, path: str, cache: dict[str, str]) -> list[list[str]]:
    """Cheapest likely-failing tests first; the full suite always last."""
    found: list[list[str]] = []
    if name in cache:
        found.append([cache[name]])
    parts = Path(path).parts
    if parts[0] == "apps" and (ROOT / "tests" / parts[1]).is_dir():
        found.append([f"tests/{parts[1]}"])
    found.append([])
    return found


def check(entry, worker: Worker, cache: dict[str, str]) -> tuple[str, str, str]:
    name, path, original, mutated = entry
    target = worker.path / path
    source = target.read_text()
    if original not in source:
        return "STALE", f"text not found in {path}", ""
    target.write_text(source.replace(original, mutated, 1))
    summary = "no tests ran"
    try:
        for targets in stages(name, path, cache):
            result = worker.pytest(targets)
            if result.returncode in NO_VERDICT:
                continue
            summary = (result.stdout.strip().splitlines() or ["no output"])[-1]
            if result.returncode != 0:
                failed = FAILED_LINE.search(result.stdout)
                return "CAUGHT", summary, failed.group(1) if failed else ""
        return "MISSED", summary, ""
    finally:
        worker.restore(path)


def changed(base: str) -> set[str]:
    """The files this branch changed since it left ``base``."""
    names = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return set(names.split())


def load_cache() -> dict[str, str]:
    for path in (CACHE, OLD_CACHE):
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            continue
    return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name_filter", nargs="?", default="")
    # Leave 2 cores for the rest of the machine.
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    parser.add_argument("--changed", nargs="?", const="origin/main", metavar="BASE")
    args = parser.parse_args()
    entries = [entry for entry in MUTATIONS if args.name_filter in entry[0]]
    if args.changed:
        entries = [entry for entry in entries if entry[1] in changed(args.changed)]
        if not entries:
            print(f"No entries for the files changed since {args.changed}.")
            return 0
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout
    if dirty:
        print("Note: uncommitted changes are not checked; entries run on HEAD.")
    cache = load_cache()
    started = time.monotonic()
    counts = {"CAUGHT": 0, "MISSED": 0, "STALE": 0}
    with tempfile.TemporaryDirectory(prefix="mutation-") as base:
        workers = [Worker(n, Path(base)) for n in range(min(args.jobs, len(entries)))]
        free: queue.Queue[Worker] = queue.Queue()
        for worker in workers:
            free.put(worker)

        def run(entry):
            worker = free.get()
            try:
                return entry, check(entry, worker, cache)
            finally:
                free.put(worker)

        try:
            with ThreadPoolExecutor(max_workers=len(workers)) as pool:
                for entry, (status, summary, failed) in pool.map(run, entries):
                    counts[status] += 1
                    if failed:
                        cache[entry[0]] = failed
                    print(f"{status + ':':7} {entry[0]}: {summary}", flush=True)
        finally:
            for worker in workers:
                worker.remove()
    CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")
    minutes = (time.monotonic() - started) / 60
    print(
        f"{counts['CAUGHT']} caught, {counts['MISSED']} missed, "
        f"{counts['STALE']} stale in {minutes:.1f} min"
    )
    return 1 if counts["MISSED"] or counts["STALE"] else 0


if __name__ == "__main__":
    sys.exit(main())
