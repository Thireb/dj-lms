# FEATURES

Target: a multi-institute LMS for tuition centers, academies, and online schools.
All text is our own wording. Source: the reference product's public landing page, Feature Book, and User Manual (captured by Cursor into the WebScraping101 repo, `raw/` and `requirements/`).

**Verification status:** nothing here was seen on a logged-in session (login is protected by Cloudflare Turnstile). Everything is PREVIEW level. Items marked **(verify)** need a manual check.

**Scope for first release:** no integrations. Zoom, Google login, Google Drive, WhatsApp, and payment gateways are out (see section 15).

Plan: **B** = Basic, **P** = Premium. Plan split is from the reference pricing page (verify exact split).

---

## 1. Platform

- [x] Many institutes on one install, each with isolated data. (B) (verify)
- [x] Super Admin panel: create institutes, set plan, activate/deactivate. (verify)
- [x] Super Admin: new one-time sign-in link for an institute admin who lost theirs (also `manage.py make_set_password_link`).
- [ ] Super Admin: read contact requests (roadmap 11.2).
- [ ] Five logins per institute: Admin, Sub-admin (helper), Teacher, Student, Guardian. (Sub-admin menus wait for roadmap 9.3c.)
- [x] One campus per institute. (verify)
- [x] Per-institute plan flags switch modules on or off. (verify)
- [ ] Installable web app (PWA). (B)
- [x] In-app notification bell on every screen; fee and class alerts can be switched off per user. Built in 6.1: the bell, the Notifications page and the switches on My profile; the events come with 6.2 and the later phases.
- [ ] Badge counts on menus (messages, approvals, receipts).
- [ ] Dark / light / auto appearance setting.
- [x] Currency setting per institute. (verify)
- [ ] Currency symbol shown on all amounts (with fees, Phase 7).
- [x] Per-user time zone; lectures show in the viewer's zone. Built in 3.4: the page clock shows the zone label (for example PKT); lecture times already show it.
- [ ] "Default portal" and "Toolbar settings" in the profile menu. (verify what they do)
- [ ] Public site: Home, Features, Portals, Pricing, Contact, Privacy, Terms, Sign in.
- [ ] Contact / demo-request form that lands in Super Admin.
- [x] Sign in with email + password, show-password toggle, remember me.
- [x] Sign-in limit: 5 failed attempts per 15 minutes per email and IP; email is not case sensitive.
- [x] No self-service password reset: "Forgot password" tells the user to contact the admin.
- [x] First-time "set your password" screen (password + confirm) reached from a link.
- [x] Account profile: edit name, phone, and time zone; change password (current, new, confirm).

## 2. Institute setup (Admin) (B)

Setup order the reference teaches: Campus, Classes, Batches, Subjects, Fee Plans, Teachers, Students, then a test lecture and test challan.

- [x] Campus profile: name, address, contact (logo deferred to roadmap 12.2). (verify)
- [x] Classes: name-only list (an optional label on a student, e.g. "Grade 9").
- [x] Batches: name-only list (a running group, e.g. "Morning", "Weekend").
- [x] Subjects: name-only list.
- [ ] Fee Plans: name + amount.
- [x] **Key rule:** classes, batches, and subjects are independent lists. Links are made only when a student is enrolled or a teacher is added (see sections 3 and 4).

## 3. Students (Admin)

- [ ] Enrol student form: name*, father name, CNIC, date of birth, gender, class label, batches*, subjects for each chosen batch*, fee plans* with optional discount, read-only monthly fee summary, phones, address, city, status (Active). Built in 2.5b except fee plans (Phase 7, `fees` feature).
- [x] Student login (email + password) and guardian login (email + password) created at enrolment. Emails must differ.
- [x] Student code auto-filled (like `STU-054`).
- [ ] Edit student: change batches, subjects, fee plans, contacts. Built in 2.5b except fee plans (Phase 7).
- [x] All Students list with Active/Inactive status.
- [x] Bulk upload from an Excel template (one student per row; error rows reported). Fee plan columns come with Phase 7.
- [x] Student Attendance History. Built in 4.2: one student at a time (a search by name, code, email or phone, or the row action on All students).
- [ ] **Portal Access:** block a student from the student portal (for example unpaid fees); automatic blocking of fee defaulters can be on or off; single students can be exempted. Blocked student sees a "blocked" page. Built in 2.7: manual block and unblock, exemptions, the Access paused page. Automatic blocking of defaulters comes with roadmap 7.6 (backlog S9).

## 4. Teachers (Admin)

- [x] Add / edit teacher: name, login, batches*, subjects for each batch*. Saving links the teacher to those batches and subjects.
- [x] Teacher code auto-filled (like `TCH-001`).
- [ ] All Teachers list; Teacher Lecture History. Built in 3.5: Teacher lecture history (People menu; filter by teacher and batch; a row action on All teachers opens it for one teacher).

## 5. Lectures (B)

- [x] Add lecture (Admin or Teacher): title, date, time, duration, teacher, batch, subjects (from what the teacher is assigned).
- [ ] Delivery mode: Zoom API (later), Manual Link (paste any link), In-Person. Built in 3.1: Manual link and In person.
- [x] Recurring schedules: weekly (or custom) timetable creates every lecture in one step. Built in 3.2: weekly days, a date range (or number of weeks) and a preview; "custom" rules beyond weekdays are not built.
- [x] Lecture lists with tabs: Today, Upcoming, Past, All; filter by subject. Built in 3.1 for the admin (All lectures) and teacher (My lectures). Built in 3.3: student "My lectures" and guardian "Lectures schedule" (read only, for one chosen child), and a date range on All lectures.
- [ ] Teacher actions on a lecture: Start class, open whiteboard, take manual attendance. Built in 3.5: Start class and End class (list row, lecture page and "Up next"). Built in 4.1: Take attendance (lecture page and list row) for a finished lecture. The whiteboard comes later (ROADMAP "Live whiteboard").
- [ ] Student actions: Join (enabled once the teacher starts), "Waiting for host" state, "Join opens soon" state. Built in 3.4: the states and the Join button on "My lectures" and "Up next"; Join posts to the server, which checks the state again and opens the link. The teacher starts a lecture in 3.5, so until then Join stays at "Waiting for host".
- [ ] Teacher calendar view (Schedule) and Lecture History. Built in 3.3: the Schedule calendar (week and month; a scheduled lecture opens its edit page). Built in 3.5: Lecture history (finished lectures, filter by batch); its Present / Total column fills with attendance (built in 4.1).
- [x] Admin Lectures Dashboard / Live Lecture Monitor: live and upcoming classes. Built in 3.6: Dashboards > Lectures with live now, late start (past its start, not started), the next 2 hours and today by status; it reloads every 30 seconds. Each list shows its first 20 lectures with a "View all" link to All lectures (backlog LC13). "Teachers on leave today" comes with leave (9.3).
- [x] Up-next card with countdown on teacher and student dashboards. Built in 3.4: the card refreshes itself every 30 seconds; the teacher card has "Open meeting link" (Start class comes with 3.5); the guardian home lists the next 5 classes with the child's name.
- [x] Lecture states: scheduled, live, finished, cancelled, and not held (Phase 3 audit: past its end, never started). Built in 3.5: the teacher starts and ends a class, the admin cancels a lecture, and a job finishes lectures past their end every 5 minutes.

## 6. Attendance (B)

- [x] Statuses: Present, Partial, Late, Absent. Built in 4.1; no mark shows as "Not marked" ("Waiting for teacher" to students and guardians) and is left out of the % (owner decision 2026-10-14).
- [x] Manual attendance by the teacher for any lecture. Built in 4.1: for any of their finished lectures, and editable later. The admin sees the marks on the lecture page (read only).
- [ ] Auto attendance from the meeting provider (needs Zoom, later). Unknown names must be matched to a student or ignored.
- [x] Student "My Attendance" with percentage. Built in 4.2.
- [x] Guardian "Class Attendance" for the chosen child. Built in 4.2, with the header child switcher.
- [x] Admin attendance history per student. Built in 4.2 ("Student attendance history", People menu).

## 7. Academic work

- [ ] **Homework** (P): teacher sets title, instructions, subject, batch, optional specific students, due date, optional worksheet file. Student submits text + files before due. Teacher reviews submissions. Guardian sees submitted / pending / overdue and a 6-month trend chart.
- [ ] **Lesson plans** (P): teacher writes; students see them after admin approval if the institute requires approval.
- [ ] **Daily reports** (P): teacher submits a note about a student or class; admin approves under "Reports Received"; guardian reads it.
- [x] **Assignments** (B): longer work; filters pending, submitted, graded, missed; teacher grades with feedback. Built in 5.1: the teacher publishes to one batch and subject, the student sends a text answer until the due time, the teacher gives marks and feedback. The file (SPEC 4.16) waits for file storage (backlog AS1); guardians see the marks once graded (built in 5.4: guardian "Assignments").
- [x] **Quizzes and exams** (B): saved question bank (built in 5.2: each teacher's own bank, MCQ and short answer); timed paper (5.3 part 1 built the teacher set-up: draft, publish, questions from the bank; part 2a the student attempt: Start while live, countdown, auto-submit, MCQ marked at once; part 2b the teacher results and the marks for written answers; 5.4 the guardian list with scores once graded, and the student's answers after the quiz closes); "Live now" status lets students start; MCQ auto-marked; written answers marked by the teacher; guardian sees scores.
- [x] Exam mode: leaving the page can be flagged; some exams require full screen. Built in 5.3 part 2c: the paper asks for full screen and records leaving the page or full screen; the teacher sees the flags; they never change the score.
- [ ] **Course documents** (P): upload notes and slides per course/batch; admin can lock downloads (preview only). Uses file uploads in our version (not Google Drive).
- [ ] Admin approval queues: Homework Approval, Lesson Plan Approval, Reports Received, Quizzes & Exams overview. Built in 5.3: the Quizzes & Exams overview (read only, with each quiz's results).
- [ ] Whiteboard in class with export to PDF. Build last.

## 8. Fees (P)

- [ ] **Generate challan:** pick students, month, due date; bulk generate; print.
- [ ] Challan Dashboard and Challan Records.
- [ ] **Process payment:** office records cash or transfer against a challan (amount, date, method).
- [ ] **Receipt inbox:** guardians upload proof of payment; admin approves or rejects with an optional message. Optional auto-approve setting.
- [ ] **Fee Pay (guardian):** choose child, months/year paid for, amount, optional reference, upload receipt (JPG, PNG, WEBP, PDF), submit. Status starts as Waiting.
- [ ] After approval the challan shows Paid.
- [ ] Student "Fee Details": view only (total billed, paid, due, pending challans); payment is done by the guardian.
- [ ] Guardian "Fee & Challans": bills, due dates, paid/unpaid.
- [ ] Reports: Daily, Monthly, Yearly collection, Fee Defaulters; set a date range, print or export.
- [ ] Discounts per student; fee plans attached at enrolment.

## 9. Teacher salary (P)

- [ ] Salary Plans with six types: Fixed (monthly), Per lecture, Per student (enrolment), Hourly, Percentage of fees, Hybrid.
- [ ] Plan Assignments (plan per teacher).
- [ ] Payroll: monthly amount from lectures taught; example `18 lectures x 4,500 - 10,000 advance = 71,000 net`.
- [ ] Advance Salary: deducted from the next slip.
- [ ] Payment Status, Payment History, Salary Reports (print).
- [ ] Salary Dashboard.
- [ ] Teacher "My Salary": slips and history.
- [ ] When a lecture is reassigned, salary follows the new teacher.

## 10. Leave (P)

- [ ] Student and teacher apply with dates + reason.
- [ ] Status: Pending, Approved, Rejected.
- [ ] Teacher leave shows days used vs allowance (example: 2 of 12).
- [ ] On approving teacher leave, clashing lectures are listed with three actions: Reschedule, Reassign (to another teacher), Cancel.
- [ ] Admin screens: Student Leave Approval, Teacher Leave Approval.

## 11. Messages (B)

Owner decision 2026-10-16: Messages are in the Basic plan, as the `messaging` feature key already is (ARCHITECTURE 5, backlog G4). Before, this heading said (P).

- [ ] Mailbox between admin, teachers, students, and guardians.
- [ ] Folders: Inbox, Sent, Starred, Drafts, Trash.
- [ ] Admin extras: Broadcast and Message Monitor (admin can read all threads).
- [ ] Compose with search; attachments optional.
- [ ] Unread badge in the menu.

## 12. Sub-admin (helper) (P)

- [ ] Same portal as Admin, but only the menu groups the admin ticks (for example Finance yes, Salary no).
- [ ] Tickable groups: Dashboards, Institute, People, Online Lectures, Finance, Teacher Salary, Academic, Messages.
- [ ] Admin screens: Manage Users (email + password for helpers) and Manage Permissions (tick the groups).
- [ ] Manage Users, Manage Permissions, Institute settings (rules and currency) and Select Currency stay admin-only. The Campus profile page is in the Institute group and a sub-admin granted Institute can open it.

## 13. Dashboards and menus per role

**Admin (top horizontal menus):** Dashboards (Main, Salary, Lectures, Challan) | Institute (Campus, Classes, Batches, Subjects, Fee Plans) | People (All Students, Enrol Student, Bulk Upload, Student Attendance History, Portal Access, All Teachers, Add Teacher, Teacher Lecture History) | Online Lectures (All Lectures, Add Lecture, Recurring Schedules, Master Meeting) | Finance (Generate Challan, Challan Records, Process Payment, Receipt Inbox, Daily, Monthly, Yearly Reports, Fee Defaulters) | Teacher Salary (Salary Plans, Plan Assignments, Payroll, Payment Status, Payment History, Advance Salary, Salary Reports) | Academic (Course Documents, Homework Approval, Lesson Plan Approval, Quizzes & Exams, Reports Received, Student Leave Approval, Teacher Leave Approval) | Messages (Inbox, Send Message, Message Monitor).
Profile menu: Account Settings, Toolbar Settings, Default Portal, Institute Settings, Manage Users, Manage Permissions, Select Currency, Appearance, Sign Out. "Master Meeting", Zoom and Google Drive items are integrations (later).
Main dashboard: campus hero, clock, 4 stat cards (students, teachers, batches, lectures today), quick actions (Enrol Student, New Lecture, Generate Challan, Live Lecture Monitor), students and teachers sections with active/inactive counts and a ring chart. Built in 2.4: hero with today's date (no live clock), stat cards for students, teachers and running batches, quick actions the user may open, active bars instead of a ring chart (no chart library yet), recent students and teachers. Lectures today and the lecture and fee quick actions come with Phases 3 and 7 (3.6 adds "Add lecture" and "Lecture monitor"). Redesigned in R4c: the hero holds the quick actions and the numbers (students, teachers, running batches), and the students and teachers cards have a ring chart (plain SVG) and the five newest people; the date moved to the live clock in the page header.

**Teacher (left sidebar):** Dashboard | Academics (My Lectures, Create Lecture, Schedule Recurring, Schedule, Lecture History, Documents) | Planning (Lesson Plans, Homework, Submit Report) | Assignments | Quizzes & Exams (Quizzes and exams, Question bank) | Messages | People (My Students) | Leave (Apply Leave) | Finance (My Salary) | Account (My Profile, Account Settings, Sign Out).
Dashboard: welcome banner, subject/batch chips, up-next card with countdown, 4 stat cards (lectures, students, batches, subjects), quick actions. Built in R4c: welcome banner with chips, an empty up-next card, and stat cards for students, batches and subjects. Built in 3.4: the up-next card with a countdown and a "Lectures today" card. Built for backlog AT2: a fifth card, "Attendance to take" (finished lectures with students and no marks). Quick actions come later.

**Student (left sidebar):** Dashboard | Academics (My Lectures, My Attendance, Leave Requests, Homework, Lesson Plans, Assignments, Quizzes & Exams, Documents) | Messages | Finance (Fee Details) | Account (My Profile, Settings, Sign Out).
Dashboard: attendance %, homework done %, upcoming count, fee paid %, up-next card, fee KPIs (billed, paid, due, pending challans). Built in R4c: welcome banner with code, class and batch/subject chips, and an up-next card (with a countdown and Join since 3.4). Built in 4.3: attendance % and "Lectures today" cards. The other KPIs come with their phases.

**Guardian (left sidebar):** Dashboard | Academics (Lectures Schedule, Homework, Lesson Plans, Assignments, Quizzes & Exams, Class Attendance) | Finance (Fee & Challans, Fee Pay) | Communication (Messages) | Account (Student Profile, Account Settings, Sign Out).
Dashboard: child switcher in the header, billed / paid / outstanding / upcoming classes, homework progress and 6-month trend chart. One guardian login can cover several children; every page follows the chosen child. Built in R4c: welcome banner, a "Your children" card (code, class, batches, status) and an upcoming classes card (the next 5 classes with the child's name since 3.4). The child switcher is built in 4.2 (header, kept in the session; shown with two or more children). Built in 4.3: each child's attendance % in "Your children". The other KPIs come with their phases.

## 14. Analytics

- [ ] Admin: students, fee collection, unpaid, discounts, payroll, lectures.
- [ ] Teacher: batch and attendance numbers on the dashboard. "Attendance to take" built (backlog AT2).
- [ ] Student: attendance %, homework %, fee paid %. Attendance % built in 4.3.
- [ ] Guardian: homework trend, fees, attendance. Attendance % per child built in 4.3.

## 15. Out of scope for now (integrations)

- Zoom API and Master Meeting, auto attendance from Zoom (needs a paid Zoom account; alternatives: Jitsi, BigBlueButton, Google Meet, Teams via manual link).
- Google sign-in, Google Drive document storage.
- WhatsApp login links and reminders.
- Online payment gateways (the reference does not have one either: payment is outside the site, then a receipt is uploaded).
- Push notifications beyond the in-app bell.

## 16. Details filled in by assumption

Table columns, form fields, statuses, business rules, PDF layouts, notification triggers, settings, and seed data are written in `SPEC-DETAILS.md`. They are ASSUMED from normal LMS practice and the reference's public text. Items to compare with the demo later are listed in SPEC-DETAILS section 12.

## 17. Not copying

Name, logo, wording, screenshots, theme assets, Feature Book and User Manual text. Their "AI" claims. Any AI we add is our own, optional, later.
