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
        "{% if f.options %}",
        "{% if False %}",
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
        "dashboard hides people without menu",
        "apps/people/views.py",
        "        if not people_link:",
        "        if False:",
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
        '<a href="{{ url }}" class="icon-btn h-9 w-9" aria-label="{{ label }}"',
        '<a href="{{ url }}" class="icon-btn h-9 w-9"',
    ),
    (
        "filter bar clear only when active",
        "apps/ui/templates/ui/components/filter_bar.html",
        '{% if active %}<a href="?"',
        '{% if True %}<a href="?"',
    ),
    (
        "filter value read from objects",
        "apps/ui/components/nav.py",
        '    return getattr(field, "value", "")',
        "    return field.value",
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
