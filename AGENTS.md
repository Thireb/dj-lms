# AGENTS.md

Rules for AI agents (Cursor, Claude Code, others) working on this repo. Put this file at the repo root.
Cursor users: also copy the key rules (sections 2 to 6) into `.cursor/rules/` so they load automatically.

## 1. Read first

- Before any task, read `docs/FEATURES.md`, `docs/ARCHITECTURE.md`, `docs/UI-GUIDELINES.md`, `docs/COMPONENTS.md`, and `docs/SPEC-DETAILS.md`.
- If a request conflicts with these docs, stop and ask. Do not guess.
- If the docs are missing something, propose the doc change first.

## 2. What we are building

- A multi-institute LMS in Django: Admin, Teacher, Student, Guardian portals plus Super Admin.
- We copy features only. Never copy the reference product's name, logo, text, images, or manuals.
- Zoom is out of scope for now. Use the manual meeting link provider.

## 3. Stack rules

- Django 5.x, Python 3.12+, PostgreSQL, Celery + Redis.
- Templates + Tailwind + HTMX + Alpine.js. No React/Vue unless a human approves.
- Do not add a new dependency without asking. If you must, say why and list the license.
- Do not change the stack, settings layout, or folder layout without asking.

## 4. Code rules

- One Django app per module listed in `ARCHITECTURE.md`. Do not create new apps without asking.
- Business logic goes in `services.py`, not in views or templates.
- Views stay thin: check access, call a service, render.
- Class-based views for CRUD, function views for small actions.
- Every tenant model inherits `TenantModel`. Every query goes through the tenant manager and exposes `for_user(user)`.
- Every view uses role and tenant mixins. No open views except the public site.
- One user has one role (`user.role`). Check roles with `user.is_teacher`, `user.is_institute_admin`, etc. Never add extra boolean role columns.
- Every view declares `allowed_roles`. Do not write `if user.is_x or user.is_y` chains inside views.
- Fetch data with `.for_user(request.user)`. Never use an unscoped manager in a view.
- Do not use Django `Group`/`Permission` or database permission tables. Do not use `is_staff`/`is_superuser` for product roles.
- Admin views also set `menu_key` and use `MenuRequiredMixin`. Sub-admin access comes only from `SubAdminProfile.allowed_menus` (fixed keys in `core/menus.py`). Never hard-code sub-admin checks in views.
- Need a new permission rule? Ask first. The plan is a code-defined `ROLE_CAPABILITIES` map.
- Money uses `Decimal`. Datetimes are UTC and time zone aware.
- Use type hints on services and utilities.
- Format and lint with `ruff` before finishing.
- Keep functions short. Prefer clear names over comments.
- No secrets in code. Read from environment variables and update `.env.example`.

## 5. UI rules

- Build UI with the Python component classes in `COMPONENTS.md`. If one is missing, add the class, template, test, and table row first.
- Reuse by subclassing. Do not copy a component or paste HTML into a page template.
- Forms are crispy-forms classes inheriting `BaseForm` / `TenantModelForm`. Layout goes in `get_layout()`.
- Pages inherit `DashboardPage`, `ListPage`, `DetailPage`, or `FormPage`.
- Domain-specific components (for example `StudentTable`) live in that app's `ui.py` and subclass generic ones from `apps.ui`.
- Use Tailwind theme tokens, never raw hex.
- Follow the page patterns (list, detail, form, dashboard).
- Sentence case text. Buttons say what they do.
- Every page works at 360px width.

## 6. Data and safety

- Never write code that reads another institute's data.
- Never log passwords, tokens, or personal data.
- Use fake data only in seeds and tests. Never real student names or numbers.
- Migrations: one logical change per migration, never edit an applied migration.
- Destructive actions need a confirm dialog and a permission check.
- Validate all input on the server, even if the form validates it too.

## 7. Tests (required)

- New model: test creation and tenant isolation.
- New admin view: test `institute_admin` passes, `sub_admin` passes only with the menu key, and without it gets 403.
- New view: test allowed role passes, every other role gets 403, other institute gets 404.
- New `for_user` scope: test that a user cannot see another user's records (teacher vs teacher, guardian vs unlinked student).
- Money, payroll, challan, and attendance logic: unit tests with real numbers.
- Run `pytest` and `ruff check` before saying a task is done.

## 8. Workflow

- Work on one feature at a time, following `ROADMAP.md` order.
- Small changes. One feature per branch and per commit group.
- Commit messages: `feat(app): short text`, `fix(app): short text`, `docs: short text`.
- Before editing, list the files you plan to change. After editing, list what changed.
- If a task is bigger than about 10 files, split it and ask which part to do first.
- Do not refactor unrelated code.
- When unsure, ask one clear question instead of guessing.

## 9. Definition of done

- Feature works for every role listed in `FEATURES.md`.
- Tests pass, lint passes.
- UI follows `UI-GUIDELINES.md`.
- `FEATURES.md` checkbox updated.
- No new warnings, no leftover debug code, no TODOs without an owner.

## 10. Rules for AI features (later, optional)

The reference product's "AI" is marketing only. Any AI we add is our own and optional.

- AI is off by default and can be switched off per institute.
- AI never changes grades, fees, or attendance on its own. A human confirms.
- Do not send student personal data to an AI service without a documented reason and consent.
- Mark every AI-made text or score in the UI with a small "AI-generated" badge.
- Keep prompts in one file per feature (`apps/<app>/ai/prompts.py`), with tests.
- Candidate features: quiz generation from notes, short-answer grading help, lecture summaries, at-risk student alerts.

## 11. Handy prompts for the human

- "Read docs/ and implement roadmap item 3.2. List files first."
- "Add the `CountdownCard` component class exactly as in COMPONENTS.md."
- "Create `StudentListPage` by subclassing `ListPage`, with `StudentTable` and `StudentFilterBar`."
- "Write tests for tenant isolation on `finance.Challan`."
- "Review this diff against AGENTS.md and list violations."
