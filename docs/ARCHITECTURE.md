# ARCHITECTURE

How the Django project is organised. Keep it simple: one Django project, many small apps.

## 1. Stack

- Python 3.12+, Django 5.x.
- PostgreSQL database.
- Redis (or Render Key Value) for cache and task queue.
- Celery + Celery Beat for background and scheduled jobs.
- Django templates + Python component classes + django-crispy-forms + Tailwind CSS + HTMX + Alpine.js for UI (see `COMPONENTS.md` and `UI-GUIDELINES.md`).
- WeasyPrint for PDFs (challans, salary receipts, certificates).
- S3-compatible object storage for uploads (Cloudflare R2 or S3).
- WhiteNoise for static files, Gunicorn as the server.
- pytest + pytest-django for tests, ruff for lint and format.

UI rule: components are Python classes in `apps/ui`; domain apps subclass them in their own `ui.py`. Apps import from `apps.ui`, never the other way round.

Decision rule: pure Django templates first. Add a JS framework only if a feature cannot be done with HTMX + Alpine (likely only the live whiteboard).

## 2. Repo layout

```
lms/
  manage.py
  config/            # settings (base, dev, prod), urls, celery, wsgi
  apps/
    core/            # TenantModel, tenant manager (fail closed), tenant_context(), time zone utils, mixins, roles
    ui/              # component classes, base forms, base page views, templates (see COMPONENTS.md)
    accounts/        # User, roles, login, profile
    institutes/      # Institute, Plan, feature flags, campus profile, institute settings
    superadmin/      # institute management, contact requests
    people/          # Student, Teacher, Guardian profiles + links
    academics/       # ClassLabel, Batch, Subject, StudentBatchSubject, TeacherBatchSubject
    lectures/        # Lecture, RecurringSeries, meeting providers
    attendance/      # Attendance records and summaries
    assessments/     # Assignment, Submission, Quiz, Exam, QuestionBank
    planning/        # LessonPlan, Homework, DailyReport (with admin approval)
    documents/       # CourseDocument (file upload, download lock)
    leaves/          # LeaveRequest
    finance/         # FeePlan, StudentFeePlan, Challan, Payment, ReceiptSubmission, reports
    payroll/         # SalaryPlan, PlanAssignment, PayrollRun, SalaryPayment, Advance
    messaging/       # Thread, Message
    notifications/   # Notification, delivery
    analytics/       # report queries and chart data
    certificates/    # Certificate templates and issued certs
    pwa/             # manifest, service worker
    site/            # public marketing pages
  templates/
    base.html
    <app>/           # page templates per app
  static/
  tests/
  docs/              # these markdown files
  render.yaml
  AGENTS.md
```

## 3. Multi-tenancy (one DB, many institutes)

- Every institute-owned model inherits `TenantModel` from `core` (has an `institute` foreign key, `on_delete=PROTECT`).
- **Fail closed.** `Model.objects` (the tenant manager) returns **nothing** unless a current institute is set. It never returns all rows by accident.
- Middleware sets the current institute from the logged-in user. If a logged-in non-super-admin user has no valid, active institute, the request is rejected (403), never run unscoped.
- Anonymous requests have no institute, so tenant models return nothing for them.
- Super Admin is the only role that sees across institutes, through `Model.objects.for_user(user)` or the explicit `Model.unscoped`.
- `Model.unscoped` is a second manager that sees all institutes. Only use it in: Super Admin screens, migrations, management commands, and tests. Every use needs a one-line comment saying why.
- Background jobs (Celery) and shell scripts must run inside `with tenant_context(institute):` or use `unscoped` on purpose. A task that forgets gets empty results, not other institutes' data.
- Never query a tenant model through a plain `Model._default_manager` or raw SQL in a view.
- Unique fields (like student ID) are unique per institute, not globally.
- Tests must prove: no context returns nothing, anonymous returns nothing, institute A cannot see B, a missing institute is rejected.

## 4. Users, roles, and permissions

Decision: one user = one role. A person who needs two roles gets two separate accounts.

- One `User` model (email login) with a single `role` field (`TextChoices`): `super_admin`, `institute_admin`, `sub_admin`, `teacher`, `student`, `guardian`.
- Flag-style properties on `User`: `is_super_admin`, `is_institute_admin`, `is_teacher`, `is_student`, `is_guardian`. They only compare `role`. There are no separate boolean columns.
- Django's `is_staff` / `is_superuser` are for `/django-admin/` (developers) only. Never use them for product roles.
- No database permission tables. No Django `Group` or `Permission` for product logic.
- Profile models in `people`: `StudentProfile`, `TeacherProfile`, `GuardianProfile` (one-to-one with User).
- `GuardianStudentLink` connects a guardian to one or more students.

Three layers of access, always in this order:
1. **Role gate:** `RoleRequiredMixin` with `allowed_roles = [Role.TEACHER]` on every view. Wrong role gets 403.
2. **Scoped data:** `Model.objects.for_user(user)` returns only what that user may see (teacher: own batches; student: own records; guardian: linked students only; admin: own institute). Views never use an unscoped manager.
3. **Plan flags:** `@requires_feature("fees")` for Basic vs Premium features.

- **Sub-admin (helper), decided:** role `sub_admin` sees the admin portal, limited to the menus the admin ticks.
  - `SubAdminProfile.allowed_menus`: a list of fixed menu keys defined in code (`core/menus.py`).
  - Grantable keys (group level, same as the admin top menu): `dashboards`, `institute`, `people`, `online_lectures`, `finance`, `teacher_salary`, `academic`, `messages`.
  - Not grantable (admin only): Manage Users, Manage Permissions, Institute settings (rules and currency), Select Currency.
  - The Campus page (Institute group: name, address, phone, email, logo) is under the `institute` key, so a sub-admin granted Institute can open it. Institute settings change how the institute behaves (for example defaulter blocking or attendance thresholds), so they stay admin only and live in the profile menu, not the Institute group. Field split: `SPEC-DETAILS.md` section 1.
  - `MenuRequiredMixin` with `menu_key = "finance"` on every admin view: `institute_admin` always passes, `sub_admin` passes only if the key is in `allowed_menus`, everyone else gets 403.
  - The same list drives the top menu, so hidden menus never render.
  - Data scope for a sub-admin is the same as admin (own institute).
  - Still no permission tables, no `Group`, no `Permission`.
- Other URL prefixes: `/admin/` (institute admin), `/teacher/`, `/student/`, `/guardian/`, `/super/`.
- Keep Django's built-in admin at `/django-admin/`.
- If finer roles are needed later (for example accountant), add a code-defined map `ROLE_CAPABILITIES` and `user.can("fees.edit")`. Do not add permission tables.

## 5. Plans and feature flags

- `Plan` has a code (`basic`, `premium`) and a list of enabled feature keys.
- `Institute.plan` decides what shows in menus and which URLs work.
- Use `@requires_feature("fees")` on views and `{% if feature.fees %}` in templates.
- Feature keys: `fees`, `payroll`, `whiteboard`, `leave`, `homework`, `lesson_plans`, `messaging`, `time_zone_lectures`.

## 6. Key models (short)

Institute structure (important, matches the reference):
- `Institute`: name, logo, time zone, currency, plan, is_active. One campus per institute (campus fields live on `Institute`).
- `ClassLabel`, `Batch`, `Subject`: three independent name-only lists per institute. No foreign keys between them.
- Links are made only on people:
  - `StudentBatchSubject` (student, batch, subject): written by the enrol/edit student form.
  - `TeacherBatchSubject` (teacher, batch, subject): written by the add/edit teacher form.
- `StudentProfile.class_label` is an optional label only. It does not attach batches.
- There is no `Course` model. "Course documents" attach to batch and subject.

Operations:
- `Lecture` (batch, subject(s), teacher, starts_at UTC, duration, status, delivery: manual_link / in_person / zoom later, meeting_url).
- `RecurringSeries` (rule, start, end) generates `Lecture` rows.
- `Attendance` (lecture, student, status: present/partial/late/absent, source: manual or provider).
- `Assignment`, `Submission`, `Quiz`, `Question`, `QuizAttempt`.
- `Homework`, `HomeworkSubmission`, `LessonPlan`, `DailyReport` (each with approval status where the institute requires it).
- `LeaveRequest` (user, from, to, reason, status: pending/approved/rejected) and `LeaveClash` actions (reschedule, reassign, cancel).
- `FeePlan`, `StudentFeePlan` (with discount), `Challan` (student, month, due date, amount, status), `Payment` (method, date, amount), `ReceiptSubmission` (guardian, challan/months, amount, file, status: waiting/approved/rejected, admin message).
- `PortalAccessRule` (student, blocked, exempt) plus an institute setting for automatic defaulter blocking.
- `SalaryPlan` (type: fixed / per_lecture / per_student / hourly / percent / hybrid, rates), `PlanAssignment`, `PayrollRun`, `SalaryPayment`, `Advance`.
- `Thread`, `Message` (folders: inbox, sent, starred, drafts, trash; admin broadcast and monitor).
- `Notification` (user, type, text, link, read_at).
- `CourseDocument` (batch, subject, file, download_locked).
- `Certificate` (student, code, issued_on): rules unknown, build last.

Money: `DecimalField(max_digits=12, decimal_places=2)`. Never float.

## 7. Meeting providers

- `lectures/providers/base.py` defines `MeetingProvider` with: `create_meeting`, `cancel_meeting`, `get_participants`.
- `ManualLinkProvider` is the default (teacher pastes link, no auto attendance).
- `ZoomProvider` comes later and is optional per institute (needs a paid Zoom account).
- Other providers can be added without touching lecture code.

## 8. Background jobs (Celery)

- Generate recurring lectures.
- Bulk challan generation.
- Challan and lecture reminders.
- Monthly payroll run.
- Sync attendance from provider after a lecture ends.
- Send notifications.

## 9. Time zones

- Store all datetimes in UTC.
- Each user has a `timezone` (default: institute time zone).
- Activate the user's time zone in middleware; templates render local time.
- Countdown timers use the UTC timestamp in a `data-` attribute and JS for display.

## 10. Notifications

- Create `Notification` rows in one place (`notifications.services.notify`).
- Show a bell with unread count; HTMX polls or refreshes on navigation.
- Email and WhatsApp/SMS are later options.

## 11. PDFs

- Challan, salary receipt, certificate: HTML template -> WeasyPrint.
- Templates live in `templates/pdf/`.

## 12. Settings

- `config/settings/base.py`, `dev.py`, `prod.py`.
- All secrets from environment variables. Nothing secret in git.
- `.env.example` lists every variable.

## 13. Testing

- Every model with tenant data gets an isolation test.
- Every view gets: allowed role works, other roles get 403.
- Money and payroll code needs unit tests with real numbers.
