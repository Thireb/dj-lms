# CURSOR-PROMPTS

Copy-paste prompts, one per session. Start a fresh chat for each. Docs go in `docs/`, `AGENTS.md` in the repo root, `.cursor/rules/lms.mdc` in `.cursor/rules/`.

## Before the first prompt
1. Create the repo and copy these files in.
2. Put the docs under `docs/`.
3. Check the rule file loads (Cursor Settings > Rules).

## Session 1: Phase 0.1 and 0.2 (foundation)
```
Read AGENTS.md and docs/. Do roadmap items 0.1 and 0.2 only.
First list every file you will create. Wait for my OK.
Then: Django 5 project with config/settings (base, dev, prod), .env.example,
ruff, pytest-django, the core app with TenantModel, tenant manager with
for_user(user), tenant middleware, time zone middleware, and tests for
tenant isolation. No UI yet.
```

## Session 2: Phase 0.3 to 0.4c (UI system)
```
Read AGENTS.md and docs/COMPONENTS.md and docs/UI-GUIDELINES.md.
Do roadmap items 0.3, 0.4, 0.4b, 0.4c. List files first.
Build apps/ui: Component base class, every component class in the table,
templates, per-portal CSS variables (admin, teacher, student, guardian),
BaseForm/TenantModelForm/HtmxModalForm, crispy layout objects, base page
classes, TopNavShell and SidebarShell, and a /dev/components/ demo page.
Add a render test per component.
```

## Session 3: Phase 1 (accounts, institutes, roles)
```
Read AGENTS.md and docs/ARCHITECTURE.md section 4 and 5. Do roadmap 1.1 to 1.4.
User with a single role field and is_* properties (incl. sub_admin),
email login, password reset by admin only, first-time set password link,
Institute + Plan + feature flags, Super Admin screens, RoleRequiredMixin,
MenuRequiredMixin with core/menus.py, SubAdminProfile.allowed_menus.
Tests: 403 for every other role, sub_admin passes only with the menu key.
```

## Session 4: Phase 2 (people and academics)
```
Read docs/SPEC-DETAILS.md sections 3.1, 4.1 to 4.4, 5, 6.2. Do roadmap 2.1 to 2.7.
ClassLabel/Batch/Subject as independent lists, StudentBatchSubject and
TeacherBatchSubject written by the enrol/add-teacher forms, auto IDs,
guardian accounts at enrolment, lists with columns from SPEC-DETAILS,
Excel bulk upload with row errors, Portal Access with blocked page.
```

## Later sessions
Use the same pattern: "Read AGENTS.md and docs/SPEC-DETAILS.md sections X. Do roadmap items N. List files first."

| Session | Roadmap | SPEC-DETAILS sections |
|---|---|---|
| 5 | Phase 3 Lectures | 4.5, 4.6, 6.4 |
| 6 | Phase 4 Attendance | 6.3 |
| 7 | Phase 5 Assessments | 4.16, 6.8 |
| 8 | Phase 6 Notifications and messages | 4.19, 6.5, 7 |
| 9 | Phase 7 Fees | 4.7 to 4.9, 4.17, 6.1, 9.1, 9.3 |
| 10 | Phase 8 Payroll | 4.10 to 4.12, 6.6, 9.2 |
| 11 | Phase 9 Planning and leave | 4.13 to 4.15, 4.18, 6.7, 6.9 |
| 12 | Phase 10 to 11 | 8, 9.4, 9.5 |

## Good habits
- One session = one phase. Don't let the agent "continue ahead".
- Ask for a diff review at the end: "Review this diff against AGENTS.md and list violations."
- When a doc is unclear, change the doc first, then the code.
