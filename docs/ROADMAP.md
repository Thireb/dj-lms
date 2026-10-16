# ROADMAP

Open review follow-ups are tracked in `BACKLOG.md`. Fix each one in the first PR that touches its area.

Build order. Finish each phase before the next. Tick boxes as you go.
From 2.8 on, every phase that adds a model also extends `seed_demo` with that model's rows from `SPEC-DETAILS.md` section 10, in the same PR.

## Phase 0: Foundation

- [x] 0.1 Repo, Django project, settings split, `.env.example`, ruff, pytest.
- [x] 0.2 `core` app: `TenantModel`, tenant manager, tenant middleware, time zone middleware.
- [x] 0.2b Hardening of 0.2: fail-closed tenant manager, `unscoped` manager, `tenant_context()`, reject users without a valid institute, `on_delete=PROTECT`, `config/settings/test.py`, one institute lookup per request, roles in `apps/core/roles.py`, `ruff format --check` clean.
- [x] 0.3 Tailwind, HTMX, Alpine, Font Awesome Free set up (self-hosted, no CDN). `base.html` and `app_shell.html`.
- [x] 0.4 `apps/ui`: `Component` base class, all component classes from `COMPONENTS.md`, `/dev/components/` demo page.
- [x] 0.4b crispy-forms setup: `BaseForm`, `TenantModelForm`, `HtmxModalForm`, layout objects `Section`, `Row`, `FormActions`.
- [x] 0.4c Base page classes: `PortalPageView`, `DashboardPage`, `ListPage`, `DetailPage`, `FormPage`; menu classes per portal.
- [x] 0.5 Local run script and CI; Docker moves to Phase 12.
- [x] 0.5b UI hardening from backlog (B8, B9, B16, C5, C6, C10).

## Phase 1: Accounts and institutes

- [x] 1.0 Tenancy follow-ups from the PR #2 review: test that PROTECT blocks deleting an institute with data; test an anonymous user with an institute id still gets nothing from `for_user`; let authenticated users without an institute reach logout; a base `TenantAdmin` that uses `unscoped` (the default manager is fail-closed, so Django admin shows nothing for tenant models otherwise); rename role helpers to public names; `Institute.is_active` and middleware 403 for inactive institutes. (`createsuperuser` → 1.1.)
- [x] 1.1 `accounts`: User with one `role` field, `is_*` properties, email login (remember me, show password), first-time set-password link (no self-service reset; "Forgot password" says contact the admin, see `FEATURES.md` section 1), profile and change password. `createsuperuser` creates `role=super_admin`.
  - [x] 1.1a Custom `User` model (`AUTH_USER_MODEL`), role properties, institute validation, `createsuperuser` → `super_admin`, TenantAdmin add/delete (M4/M5). Login UI deferred.
  - [x] 1.1b Auth flows: login (email, show password, remember me), POST logout, set-password token link, forgot-password admin message; C8/C9.
  - [x] 1.1c Profile and change password (name, phone, time zone; SPEC 4.22 subset).
- [x] 1.2 `institutes`: Plan, feature flags, campus profile (Institute group), institute settings (rules and currency, admin only).
- [x] 1.3 `superadmin`: create institutes, set plans, activate/deactivate.
- [x] 1.4 `RoleRequiredMixin`, `MenuRequiredMixin` (admin menu keys), `for_user` scoped managers, portal URL prefixes, 403 and data-scope tests for every role.
- [x] Phase 1 complete (accounts, institutes, super admin shell, portal prefixes). Full SPEC section 10 demo volume waits until roadmap 2.8 (`seed_demo` is Phase 1 stack only).

## Phase 2: People and academics

- [x] 2.1 `people`: Student, Teacher, Guardian profiles; auto IDs (`STU-`, `TCH-`).
- [x] 2.2 Guardian links to students; guardian account created on enrolment.
- [x] 2.3 `academics`: ClassLabel, Batch, Subject (independent lists), StudentBatchSubject, TeacherBatchSubject.
  - [x] 2.3a Models, link services (`set_student_batch_subjects`, `set_teacher_batch_subjects`), `for_user` scopes through batches, `StudentProfile.class_label`.
  - [x] 2.3b Admin pages for Classes, Batches and Subjects (Institute menu): list, add, edit, deactivate (SPEC 3 and 4.3).
- [x] 2.4 Admin dashboard with counts and recent enrolments. Lectures today, the fee strip, approvals and receipts are added by Phases 3, 7 and 9.
- [x] 2.5 Student and teacher list, create, edit, activate/deactivate.
  - [x] 2.5a Teachers: list (search, batch and status filters), add, edit, activate/deactivate.
  - [x] 2.5b Students: list, enrol (with guardian), edit, activate/deactivate. Fee plans wait for Phase 7.
- [x] 2.6 Bulk student upload from Excel template with error report.
- [x] 2.7 Portal Access: manual block/unblock, exemptions, blocked page. The automatic defaulter rule (nightly auto-block and auto-unblock, SPEC 6.2) needs challans, so it moves to Phase 7 as 7.6 (backlog S9).
- [x] 2.8 Demo data at scale: extend `seed_demo` with bulk students per SPEC section 10. Build last in Phase 2, after 2.1 to 2.3 add the people and academics models.
- [x] 2.9 Phase 2 audit (external review; findings and fixes in BACKLOG.md "Phase 2 audit"): full review of everything built in Phase 2 (CLAUDE.md PR review procedure on the whole phase, every open backlog item re-checked, findings added to BACKLOG.md). Phase 3 does not start until it is done.

## Phase R: Redesign (current priority, decided 2026-10-09)

The product owner did not accept the current look (navigation, tables, forms, sign-in, all of it). The whole website is redesigned before new features. Phase 3 was on hold until R5; R5 is signed off (2026-10-13).

- Brand: Lexicon (https://lexicon.edu.pk), the institute this LMS is for. Use its colours, type and theme.
- UI/UX: modelled on IgnisLMS, the reference product: layout, navigation and interaction patterns only. `AGENTS.md` still applies: never copy its name, logo, text or images.

- [x] R1 Research: extract Lexicon's palette, fonts and logo use; study the reference's public screens for layout and interaction patterns. Write a short style brief.
  - Lexicon (measured in a browser): royal `#002DA8`, indigo `#130C8E`, sky `#1273EB`, near-white `#FAFAFA`, ink `#1C1B1B`; font Familjen Grotesk 400-700; 5px corners, soft shadows; logo is a 200px JPEG (ask for SVG).
  - Reference patterns: light top bar with dropdown groups and a role chip (admin); dark grouped sidebar (other portals); campus hero with stats and actions; people cards with ring and recent list; up-next countdown; split-screen sign-in.
  - Proposal for R2 review: https://claude.ai/artifact/EeJ9dKpEKbsJX5jehZurga (private to the owner).
- [x] R2 Design system for approval: tokens (colour, type, spacing, radius, shadow, motion) and every component with previews, for the four portals, super admin and the public pages (sign-in, set password, forgot password, access paused). The owner approves before any template changes.
  - Approved by the owner on 2026-10-09 (proposal artifact above). Decisions: one Lexicon look for every portal (no per-portal colours); light only, no dark mode; the "LEX" mark stands in until an SVG logo arrives; "sign-up pages" means the sign-in and set-password pages (there is no self-registration).
- [x] R3 Docs: rewrite `UI-GUIDELINES.md` and `COMPONENTS.md` to the approved system.
- [x] R4 Build: tokens, shells (top menu, sidebar), public pages, tables, forms, dashboards and every Phase 1-2 page; checked at 360px and desktop in a browser; new walkthrough video.
  - [x] R4a Foundation: tokens, font, Lucide icons, shells, public pages, base components.
  - [x] R4b Tables (people as avatar cards, cards on phones), filters, pagination, form sections with explanations.
  - [x] R4c Dashboards and portal home pages; walkthrough video.
- [x] R5 Owner sign-off. Then Phase 3 resumes.
  - Signed off by the owner on 2026-10-13 after the R4c walkthrough. The redesign audit findings (RA1-RA8 in `BACKLOG.md`) are fixed before Phase 3.

## Phase 3: Lectures

- [x] 3.1 Lecture CRUD with manual meeting link.
  - Admin All lectures, Add lecture, Edit; teacher My lectures, Create lecture, Edit. Deferred parts are LC1-LC4 in `BACKLOG.md`.
- [x] 3.2 Recurring schedule builder (Celery task generates lectures).
  - Celery and Redis added (owner approved, 2026-10-13). Admin Recurring schedules and teacher Schedule recurring: list, add with a preview, edit (this and all future), extend, stop. A task makes the lectures after a save; Celery beat extends every active schedule each night.
- [x] 3.3 Teacher, student, guardian schedule views.
- [x] 3.4 Countdown card and join button; time zone display.
- [x] 3.5 Lecture history and states (scheduled, live, finished, cancelled).
- [x] 3.6 Live Lecture Monitor for admin.
- [x] 3.7 Phase 3 audit (findings and fixes in BACKLOG.md "Phase 3 audit"): CLAUDE.md PR review procedure on the whole phase, every page opened as each demo role at 360px and 1440px, every open backlog item re-checked. Phase 4 does not start until it is merged.

## Phase 4: Attendance

- [x] 4.1 Teacher marks attendance per lecture. Built: the `attendance` app (`Attendance`, one row per lecture and student), "Take attendance" for a finished lecture (form starts at Present), the marks on the lecture page, the "Attendance" row action and Lecture history Present / Total.
- [x] 4.2 Student and guardian attendance views. Built: student "My attendance", guardian "Class attendance" and admin "Student attendance history" (finished classes with marks, the % and filters), and the guardian header child switcher (backlog LC7) that "Lectures schedule" now follows too.
- [x] 4.3 Monthly summary and percentages. Built: "By month" and "By subject" views on the three attendance pages, the attendance % on the student dashboard and for each child on the guardian dashboard.
- [x] 4.4 Phase 4 audit (findings and fixes in BACKLOG.md "Phase 4 audit"): CLAUDE.md PR review procedure on the whole phase, every attendance page opened as each demo role at 360px and 1440px, every open backlog item re-checked. Phase 5 does not start until it is merged.

## Phase 5: Assessments

- [x] 5.1 Assignments: publish, submit, grade. Built: the `assessments` app (`Assignment`, `Submission`), teacher "Assignments" (list, Add, Edit, the answers of every expected student, the grade page with marks and feedback), student "Assignments" (status and subject filters) and the assignment page with the answer form, the teacher dashboard card "Answers to grade", and demo assignments. Text answers only (backlog AS1); the guardian view comes with 5.4 (AS2).
- [x] 5.2 Question bank. Built: `Question` and `QuestionOption` in `assessments`; teacher "Question bank" (Quizzes and exams menu group) with search, subject and type filters, Add, Edit and Delete (confirm dialog); MCQ (2 to 6 options, one correct) and short answer questions; six demo questions.
- [x] 5.3 Quizzes and exams: timed attempt, auto-grade. Part 1 built (set-up): `Quiz` and `QuizQuestion`; teacher "Quizzes and exams" (list with type and status filters, Add, Edit, the quiz page, Add from bank, New question, Remove, Publish, Back to draft); the status rule (SPEC 6.8); a question in a quiz stays in the bank (backlog AS6); two demo quizzes (one live). Part 2a built (student attempt): `QuizAttempt` and `AttemptAnswer`; student "Quizzes and exams" (Status and Score), the quiz page with Start, and the paper with the `AttemptTimer` countdown, Save and Submit; auto-submit at zero; MCQ marked at submit. Part 2b built (results and marks): the Results card on the teacher's quiz page (every student with Status, Submitted and Score), the attempt page with each answer, the right answer and the marks form for the written answers (graded when all are marked; marks can change), the Attempts column with "N to mark", and a closed demo quiz with two attempts. Part 2c built (exam mode): `AttemptEvent`; the `ExamGuard` notice on the paper with "Enter full screen", which records leaving the page or full screen; the Exam flags column and card for the teacher; the closed demo quiz is now an exam with one flag. Part 2d built (admin overview): admin "Quizzes and exams" (Academic menu: every teacher's quizzes with Teacher, Attempts and Status, type and status filters) and the read-only quiz page with Results, Questions and Details (backlog AS7).
- [x] 5.4 Scores on student and guardian portals. Part 1 built: guardian "Assignments" and "Quizzes and exams" for the chosen child (read only; a quiz score shows once graded; backlog AS2) and the student's "Your answers" review after a quiz closes (backlog AS8). Part 2 built: the teacher dashboard card "Answers to grade" also counts quiz attempts with written answers to mark (backlog AS10).

## Phase 6: Notifications and messaging

- [x] 6.1 Notification service and bell. Part 1 built (service): the `notifications` app (`Notification`), `notify` with every SPEC 7 event and its group, the fee and class alert switches on `User`, and the nightly delete after 90 days. Part 2 built (pages): the bell in every portal (the latest 8 in a panel, the unread count every 60 seconds), the Notifications page with Open and Mark all as read, and the switches on My profile. The events are hooked in 6.2.
- [x] 6.2 Hook notifications into lectures, assignments, challans. Built: lectures (a new lecture or a new time, length, teacher or link; started; cancelled; one notice per recurring schedule save, change or stop; "starts soon" 15 minutes before), assignments (published, first answer received, graded), quizzes ("opens soon" 1 hour before, graded), portal access (blocked, open again). Times are in each recipient's zone; a guardian's notice names the child; the person who made the change gets nothing. Challans have no notices yet: they come with Phase 7 (the events are in `notifications.services.EVENTS`). Backlog LC11 and AS4.
- [x] 6.3 Messaging: inbox, sent, starred, drafts, trash; admin broadcast and monitor. Part 1 built (rules): the `messaging` app with threads, each person's state, drafts and broadcasts, and the SPEC 6.5 reach rule. Part 2 built (pages): Messages in every portal with the Inbox, Sent, Starred, Drafts and Trash tabs, a thread with Reply, Star, Trash, Restore and Delete forever, New message with a search for the person, drafts, the "New message" notification and the unread count in the menu. Part 3 built (admin): Broadcast (everyone, teachers, students, guardians or a batch; one private thread each), Message Monitor (every thread, search and role filter, read only) and 30 demo messages.
- [x] 6.4 Phase 6 audit (findings and fixes in BACKLOG.md "Phase 6 audit"): CLAUDE.md PR review procedure on the whole phase on `phase/6`, every page opened with the browser walk at 360px and 1440px, every open backlog item re-checked. One PR for the whole phase.

## Phase 7: Fees (Premium)

- [x] 7.1 Fee structures. Part 1 built: the `finance` app (`FeePlan`, `StudentFeePlan`), admin Fee plans (list with search and the students count, Add, Edit, Activate and Deactivate), the monthly fee rule with discounts, and the late fee and academic year settings (owner decisions 2026-10-16). Part 2 built: fee plans and discounts on Enrol and Edit, and the Monthly fee column on All Students. Part 3 built: the `fee_plans` and `discount` columns of the bulk upload.
- [x] 7.2 Bulk challan generation (Celery) and challan PDF. Part 1 built: `Challan` and `ChallanLine`, Generate challans (month, due date, all active or one batch, a preview with a tick per student and the skipped list, then a Celery task), Challan records (search, month, batch and status filters, overdue shown), the challan page and Cancel. Part 2 built: the challan PDF with WeasyPrint (three labelled copies on one A4 page; Print these challans prints the filtered list, one challan per page).
- [ ] 7.3 Process Payment (office), payments, status, fee history.
- [ ] 7.3b Receipt inbox: guardian Fee Pay upload, admin approve/reject with message.
- [ ] 7.3c Reports: daily, monthly, yearly, defaulters, print/export.
- [ ] 7.4 Reminders.
- [ ] 7.5 Student and guardian fee pages.
- [ ] 7.6 Automatic defaulter blocking from 2.7: nightly job blocks defaulters that are not exempt and unblocks them when nothing is overdue beyond grace (SPEC 6.2, setting `auto_block_defaulters`).

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
