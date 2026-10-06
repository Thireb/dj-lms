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
