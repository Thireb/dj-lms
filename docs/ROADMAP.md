# ROADMAP

Open review follow-ups are tracked in `BACKLOG.md`. Fix each one in the first PR that touches its area.

Build order. Finish each phase before the next. Tick boxes as you go.

## Phase 0: Foundation

- [ ] 0.1 Repo, Django project, settings split, `.env.example`, ruff, pytest.
- [ ] 0.2 `core` app: `TenantModel`, tenant manager, tenant middleware, time zone middleware.
- [x] 0.2b Hardening of 0.2: fail-closed tenant manager, `unscoped` manager, `tenant_context()`, reject users without a valid institute, `on_delete=PROTECT`, `config/settings/test.py`, one institute lookup per request, roles in `apps/core/roles.py`, `ruff format --check` clean.
- [x] 0.3 Tailwind, HTMX, Alpine, Font Awesome Free set up (self-hosted, no CDN). `base.html` and `app_shell.html`.
- [x] 0.4 `apps/ui`: `Component` base class, all component classes from `COMPONENTS.md`, `/dev/components/` demo page.
- [x] 0.4b crispy-forms setup: `BaseForm`, `TenantModelForm`, `HtmxModalForm`, layout objects `Section`, `Row`, `FormActions`.
- [x] 0.4c Base page classes: `PortalPageView`, `DashboardPage`, `ListPage`, `DetailPage`, `FormPage`; menu classes per portal.
- [x] 0.5 Local run script and CI; Docker moves to Phase 12.
- [x] 0.5b UI hardening from backlog (B8, B9, B16, C5, C6, C10).

## Phase 1: Accounts and institutes

- [x] 1.0 Tenancy follow-ups from the PR #2 review: test that PROTECT blocks deleting an institute with data; test an anonymous user with an institute id still gets nothing from `for_user`; let authenticated users without an institute reach logout; a base `TenantAdmin` that uses `unscoped` (the default manager is fail-closed, so Django admin shows nothing for tenant models otherwise); rename role helpers to public names; `Institute.is_active` and middleware 403 for inactive institutes. (`createsuperuser` → 1.1.)
- [ ] 1.1 `accounts`: User with one `role` field, `is_*` properties, email login, password reset, profile. `createsuperuser` creates `role=super_admin`.
- [ ] 1.2 `institutes`: Plan, feature flags, campus profile (Institute group), institute settings (rules and currency, admin only).
- [ ] 1.3 `superadmin`: create institutes, set plans, activate/deactivate.
- [ ] 1.4 `RoleRequiredMixin`, `MenuRequiredMixin` (admin menu keys), `for_user` scoped managers, portal URL prefixes, 403 and data-scope tests for every role.

## Phase 2: People and academics

- [ ] 2.1 `people`: Student, Teacher, Guardian profiles; auto IDs (`STU-`, `TCH-`).
- [ ] 2.2 Guardian links to students; guardian account created on enrolment.
- [ ] 2.3 `academics`: ClassLabel, Batch, Subject (independent lists), StudentBatchSubject, TeacherBatchSubject.
- [ ] 2.4 Admin dashboard with counts and recent enrolments.
- [ ] 2.5 Student and teacher list, create, edit, activate/deactivate.
- [ ] 2.6 Bulk student upload from Excel template with error report.
- [ ] 2.7 Portal Access: block/unblock, auto-block defaulters, exemptions, blocked page.

## Phase 3: Lectures

- [ ] 3.1 Lecture CRUD with manual meeting link.
- [ ] 3.2 Recurring schedule builder (Celery task generates lectures).
- [ ] 3.3 Teacher, student, guardian schedule views.
- [ ] 3.4 Countdown card and join button; time zone display.
- [ ] 3.5 Lecture history and states (scheduled, live, finished, cancelled).
- [ ] 3.6 Live Lecture Monitor for admin.

## Phase 4: Attendance

- [ ] 4.1 Teacher marks attendance per lecture.
- [ ] 4.2 Student and guardian attendance views.
- [ ] 4.3 Monthly summary and percentages.

## Phase 5: Assessments

- [ ] 5.1 Assignments: publish, submit, grade.
- [ ] 5.2 Question bank.
- [ ] 5.3 Quizzes and exams: timed attempt, auto-grade.
- [ ] 5.4 Scores on student and guardian portals.

## Phase 6: Notifications and messaging

- [ ] 6.1 Notification service and bell.
- [ ] 6.2 Hook notifications into lectures, assignments, challans.
- [ ] 6.3 Messaging: inbox, sent, starred, drafts, trash; admin broadcast and monitor.

## Phase 7: Fees (Premium)

- [ ] 7.1 Fee structures.
- [ ] 7.2 Bulk challan generation (Celery) and challan PDF.
- [ ] 7.3 Process Payment (office), payments, status, fee history.
- [ ] 7.3b Receipt inbox: guardian Fee Pay upload, admin approve/reject with message.
- [ ] 7.3c Reports: daily, monthly, yearly, defaulters, print/export.
- [ ] 7.4 Reminders.
- [ ] 7.5 Student and guardian fee pages.

## Phase 8: Payroll (Premium)

- [ ] 8.1 Salary plans (fixed, per lecture, per student, hourly, percent, hybrid), plan assignments, advances.
- [ ] 8.2 Monthly payroll run and salary PDF.
- [ ] 8.3 Teacher "My Salary" page.

## Phase 9: Planning, leave, documents (Premium)

- [ ] 9.1 Lesson plans and homework.
- [ ] 9.2 Homework trend chart on guardian dashboard.
- [ ] 9.3 Leave requests and approval, with clash handling (reschedule, reassign, cancel).
- [ ] 9.3b Daily reports and approval queues (homework, lesson plans, reports).
- [ ] 9.3c Sub-admin: `sub_admin` role, `SubAdminProfile.allowed_menus`, `core/menus.py`, `MenuRequiredMixin`, Manage Users and Manage Permissions screens, tests for each menu key.
- [ ] 9.4 Documents per course or lecture.

## Phase 10: Analytics and certificates

- [ ] 10.1 Admin analytics: attendance, fees, performance, payroll.
- [ ] 10.2 Teacher, student, guardian analytics.
- [ ] 10.3 Certificates with verify link.

## Phase 11: Public site and PWA

- [ ] 11.1 Landing, features, portals, pricing, contact, privacy, terms.
- [ ] 11.2 Contact form to Super Admin.
- [ ] 11.3 PWA manifest, service worker, install button.

## Phase 12: Deploy

- [ ] 12.1 Dockerfile, production compose file and first deploy on Pethost (see `DEPLOYMENT.md`).
- [ ] 12.2 Object storage for uploads.
- [ ] 12.3 Backups, error tracking, uptime check.

## Later

- [ ] Zoom provider (paid Zoom needed).
- [ ] Jitsi / BigBlueButton / Google Meet providers.
- [ ] Live whiteboard.
- [ ] Online fee payments.
- [ ] Proctored exams.
- [ ] Optional AI features (see `AGENTS.md` section 10).

## After demo access

- [ ] Compare every screen with `SPEC-DETAILS.md` section 12 and update the spec.
- [ ] Adjust colors, fonts, and components in `UI-GUIDELINES.md`.
