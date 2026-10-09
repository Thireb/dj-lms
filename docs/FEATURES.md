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
- [ ] In-app notification bell on every screen; fee and class alerts can be switched off per user.
- [ ] Badge counts on menus (messages, approvals, receipts).
- [ ] Dark / light / auto appearance setting.
- [x] Currency setting per institute. (verify)
- [ ] Currency symbol shown on all amounts (with fees, Phase 7).
- [ ] Per-user time zone; lectures show in the viewer's zone.
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
- [ ] Student Attendance History.
- [ ] **Portal Access:** block a student from the student portal (for example unpaid fees); automatic blocking of fee defaulters can be on or off; single students can be exempted. Blocked student sees a "blocked" page. Built in 2.7: manual block and unblock, exemptions, the Access paused page. Automatic blocking of defaulters comes with roadmap 7.6 (backlog S9).

## 4. Teachers (Admin)

- [x] Add / edit teacher: name, login, batches*, subjects for each batch*. Saving links the teacher to those batches and subjects.
- [x] Teacher code auto-filled (like `TCH-001`).
- [ ] All Teachers list; Teacher Lecture History.

## 5. Lectures (B)

- [ ] Add lecture (Admin or Teacher): title, date, time, duration, teacher, batch, subjects (from what the teacher is assigned).
- [ ] Delivery mode: Zoom API (later), Manual Link (paste any link), In-Person.
- [ ] Recurring schedules: weekly (or custom) timetable creates every lecture in one step.
- [ ] Lecture lists with tabs: Today, Upcoming, Past, All; filter by subject.
- [ ] Teacher actions on a lecture: Start class, open whiteboard, take manual attendance.
- [ ] Student actions: Join (enabled once the teacher starts), "Waiting for host" state, "Join opens soon" state.
- [ ] Teacher calendar view (Schedule) and Lecture History.
- [ ] Admin Lectures Dashboard / Live Lecture Monitor: live and upcoming classes.
- [ ] Up-next card with countdown on teacher and student dashboards.
- [ ] Lecture states: scheduled, live, finished, cancelled.

## 6. Attendance (B)

- [ ] Statuses: Present, Partial, Late, Absent.
- [ ] Manual attendance by the teacher for any lecture.
- [ ] Auto attendance from the meeting provider (needs Zoom, later). Unknown names must be matched to a student or ignored.
- [ ] Student "My Attendance" with percentage.
- [ ] Guardian "Class Attendance" for the chosen child.
- [ ] Admin attendance history per student.

## 7. Academic work

- [ ] **Homework** (P): teacher sets title, instructions, subject, batch, optional specific students, due date, optional worksheet file. Student submits text + files before due. Teacher reviews submissions. Guardian sees submitted / pending / overdue and a 6-month trend chart.
- [ ] **Lesson plans** (P): teacher writes; students see them after admin approval if the institute requires approval.
- [ ] **Daily reports** (P): teacher submits a note about a student or class; admin approves under "Reports Received"; guardian reads it.
- [ ] **Assignments** (B): longer work; filters pending, submitted, graded, missed; teacher grades with feedback.
- [ ] **Quizzes and exams** (B): saved question bank; timed paper; "Live now" status lets students start; MCQ auto-marked; written answers marked by the teacher; guardian sees scores.
- [ ] Exam mode: leaving the page can be flagged; some exams require full screen.
- [ ] **Course documents** (P): upload notes and slides per course/batch; admin can lock downloads (preview only). Uses file uploads in our version (not Google Drive).
- [ ] Admin approval queues: Homework Approval, Lesson Plan Approval, Reports Received, Quizzes & Exams overview.
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

## 11. Messages (P)

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
Main dashboard: campus hero, clock, 4 stat cards (students, teachers, batches, lectures today), quick actions (Enrol Student, New Lecture, Generate Challan, Live Lecture Monitor), students and teachers sections with active/inactive counts and a ring chart. Built in 2.4: hero with today's date (no live clock), stat cards for students, teachers and running batches, quick actions the user may open, active bars instead of a ring chart (no chart library yet), recent students and teachers. Lectures today and the lecture and fee quick actions come with Phases 3 and 7.

**Teacher (left sidebar):** Dashboard | Academics (My Lectures, Create Lecture, Schedule Recurring, Schedule, Lecture History, Documents) | Planning (Lesson Plans, Homework, Submit Report) | Assignments | Quizzes & Exams | Messages | People (My Students) | Leave (Apply Leave) | Finance (My Salary) | Account (My Profile, Account Settings, Sign Out).
Dashboard: welcome banner, subject/batch chips, up-next card with countdown, 4 stat cards (lectures, students, batches, subjects), quick actions.

**Student (left sidebar):** Dashboard | Academics (My Lectures, My Attendance, Leave Requests, Homework, Lesson Plans, Assignments, Quizzes & Exams, Documents) | Messages | Finance (Fee Details) | Account (My Profile, Settings, Sign Out).
Dashboard: attendance %, homework done %, upcoming count, fee paid %, up-next card, fee KPIs (billed, paid, due, pending challans).

**Guardian (left sidebar):** Dashboard | Academics (Lectures Schedule, Homework, Lesson Plans, Quizzes & Exams, Class Attendance) | Finance (Fee & Challans, Fee Pay) | Communication (Messages) | Account (Student Profile, Account Settings, Sign Out).
Dashboard: child switcher in the header, billed / paid / outstanding / upcoming classes, homework progress and 6-month trend chart. One guardian login can cover several children; every page follows the chosen child.

## 14. Analytics

- [ ] Admin: students, fee collection, unpaid, discounts, payroll, lectures.
- [ ] Teacher: batch and attendance numbers on the dashboard.
- [ ] Student: attendance %, homework %, fee paid %.
- [ ] Guardian: homework trend, fees, attendance.

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
