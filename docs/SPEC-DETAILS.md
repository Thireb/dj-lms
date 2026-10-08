# SPEC-DETAILS

Fills the gaps that the public pages do not show: table columns, form fields, statuses, rules, PDFs, notifications.
Everything here is **ASSUMED** from what a normal LMS needs and from the reference's public text. Change it freely. If the demo later shows something different, update this file first.

Notation: `*` required. `(S)` = select. Money is in the institute currency. Dates show as `16 Aug 2026`.

---

## 0. Conventions

- Lists: 25 rows per page, search box, filters above, newest first unless noted.
- Records are never hard-deleted. Use `is_active` or a status. Delete means "deactivate".
- Every list has an empty state with one action.
- IDs per institute, auto-generated, never reused:
  - Student `STU-001`, Teacher `TCH-001`
  - Challan `CH-202610-0001` (year, month, running number)
  - Payment `PAY-202610-0001`
  - Salary slip `SAL-202610-TCH001`
  - Receipt submission `RCP-0001`
- All times stored in UTC, shown in the viewer's time zone.

## 1. Campus profile and institute settings

Two pages, two access levels. The split exists because institute settings change how the institute behaves (for example turning off defaulter blocking or changing attendance thresholds). A helper who manages classes and batches must not be able to do that.

### 1a. Campus profile (Admin > Institute > Campus)

Menu key `institute`: `institute_admin`, and a `sub_admin` granted Institute.

| Setting | Type | Default |
|---|---|---|
| Institute name*, address, phone, email, logo | text/file | blank |

### 1b. Institute settings (profile menu > Institute settings, admin only)

`institute_admin` only. Not grantable to `sub_admin`. Sits in the profile menu next to Manage Users, Manage Permissions, Appearance and Select Currency.

| Setting | Type | Default |
|---|---|---|
| Time zone | (S) | Asia/Karachi |
| Currency symbol and code | (S) | Rs / PKR |
| Join window (minutes before start students can join) | number | 10 |
| Fee due day of month | number 1-28 | 10 |
| Grace days after due date | number | 5 |
| Auto-block defaulters from student portal | on/off | off |
| Auto-approve guardian receipts | on/off | off |
| Require admin approval for homework | on/off | off |
| Require admin approval for lesson plans | on/off | off |
| Require admin approval for daily reports | on/off | on |
| Teacher leave allowance per year (days) | number | 12 |
| Attendance: Present if joined for at least | % of lecture | 75 |
| Attendance: Partial if at least | % of lecture | 25 |
| Attendance: Late if joined after (minutes) | number | 10 |
| Lock course document downloads | on/off | off |
| Recurring lecture horizon (weeks generated ahead) | number | 8 |

## 2. Status lists

| Entity | Statuses (stored) | Badge colors |
|---|---|---|
| Student / Teacher | `active`, `inactive` | green, red |
| Lecture | `scheduled`, `live`, `finished`, `cancelled` | blue, green, grey, red |
| Attendance | `present`, `partial`, `late`, `absent` | green, amber, amber, red |
| Challan | `pending`, `partial`, `paid`, `cancelled` | amber, blue, green, grey |
| Challan display only | `overdue` (pending/partial and past due date) | red |
| Receipt submission | `waiting`, `approved`, `rejected` | amber, green, red |
| Homework | `draft`, `pending_approval`, `published`, `closed` | grey, amber, green, grey |
| Homework submission | `pending`, `submitted`, `late`, `reviewed` | amber, blue, red, green |
| Lesson plan / Daily report | `draft`, `pending_approval`, `approved`, `rejected` | grey, amber, green, red |
| Assignment submission | `pending`, `submitted`, `graded`, `missed` | amber, blue, green, red |
| Quiz | `draft`, `scheduled`, `live`, `closed` | grey, blue, green, grey |
| Quiz attempt | `in_progress`, `submitted`, `graded` | blue, amber, green |
| Leave request | `pending`, `approved`, `rejected`, `cancelled` | amber, green, red, grey |
| Payroll run | `draft`, `finalized` | grey, blue |
| Salary payment | `unpaid`, `paid` | amber, green |
| Advance | `open`, `deducted` | amber, grey |
| Message thread | `unread`, `read` (per user) | bold, normal |

## 3. List screens (columns, filters, row actions)

### Admin

| Screen | Columns | Filters | Row actions |
|---|---|---|---|
| All Students | ID, Name, Class label, Batches, Guardian, Phone, Monthly fee, Status | search, batch, class label, status | View, Edit, Activate/Deactivate, Attendance history, Portal access |
| All Teachers | ID, Name, Batches, Subjects, Phone, Pay plan, Status | search, batch, status | View, Edit, Activate/Deactivate, Lecture history |
| Classes / Batches / Subjects | Name, Students count, Status | search | Edit, Deactivate |
| Fee Plans | Name, Amount, Students count, Status | search | Edit, Deactivate |
| All Lectures | Title, Date, Time, Teacher, Batch, Subject(s), Mode, Status | date range, teacher, batch, subject, status, tab (Today/Upcoming/Past/All) | View, Edit, Cancel |
| Recurring Schedules | Title, Teacher, Batch, Days, Time, Start, End, Lectures created, Status | teacher, batch | Edit, Extend, Stop |
| Challan Records | Challan no., Student, Month, Amount, Paid, Due, Due date, Status | month, batch, status, search | View, Print, Record payment, Cancel |
| Receipt Inbox | Submitted on, Student, Guardian, Months, Amount, Reference, Status | status, date range | View receipt, Approve, Reject |
| Fee Defaulters | Student, Guardian, Phone, Unpaid months, Total due, Oldest due date, Portal blocked | batch, min amount | Message guardian, Block/Unblock |
| Daily/Monthly/Yearly Reports | Date or month, Challans, Billed, Collected, Discounts, Outstanding | date range, batch | Print, Export CSV |
| Salary Plans | Name, Type, Rates, Teachers count | type | Edit, Deactivate |
| Plan Assignments | Teacher, Plan, From date | teacher | Change plan |
| Payroll | Teacher, Plan, Lectures, Gross, Advance deducted, Net, Status | month | View slip, Finalize |
| Payment Status / History | Teacher, Month, Net, Paid on, Method, Status | month, teacher, status | Mark paid, Print slip |
| Advance Salary | Teacher, Date, Amount, Note, Status | teacher, status | Edit (if open) |
| Course Documents | Title, Batch, Subject, Uploaded by, Date, Size | batch, subject | Download, Delete |
| Homework / Lesson Plan / Report Approval | Title, Teacher, Batch, Subject, Submitted on, Status | status, teacher | Preview, Approve, Reject (with note) |
| Quizzes and Exams (overview) | Title, Type, Teacher, Batch, Opens, Duration, Attempts, Status | status, type | View results |
| Leave Approval (student / teacher) | Name, From, To, Days, Reason, Status | status | Approve, Reject (teacher leave: shows clashing lectures) |
| Message Monitor | Date, From, To, Subject, Last message | search, role | Open |
| Manage Users (sub-admin) | Name, Email, Allowed menus, Status | status | Edit, Deactivate |
| Portal Access | Student, Class, Guardian, Fee due, Blocked, Exempt | blocked, exempt | Block, Unblock, Exempt (2.7 adds search and Remove exemption; Fee due comes with Phase 7) |

### Teacher

| Screen | Columns | Notes |
|---|---|---|
| My Lectures | Date, Time, Title, Batch, Subject, Mode, Status | tabs Today / Upcoming / Past; row actions Start, Whiteboard, Attendance, Edit |
| Schedule | calendar (week and month) | click an item to open it |
| Lecture History | Date, Title, Batch, Duration, Present / Total | filter by batch |
| Documents | Title, Batch, Subject, Date | upload and delete own |
| Lesson Plans / Homework / Reports | Title, Batch, Subject, Date, Status | create, edit drafts |
| Assignments | Title, Batch, Due, Submitted / Total, Status | open to grade |
| Quizzes and Exams | Title, Type, Batch, Opens, Duration, Attempts, Status | create, view results |
| My Students | ID, Name, Batch, Attendance %, Guardian phone | filter by batch |
| Apply Leave | From, To, Days, Reason, Status | allowance box (used of total) |
| My Salary | Month, Plan, Gross, Advance, Net, Status | print slip |

### Student

| Screen | Columns |
|---|---|
| My Lectures | Date, Time, Title, Subject, Teacher, Status, Join |
| My Attendance | Date, Lecture, Subject, Status, plus overall % and per-subject % |
| Leave Requests | From, To, Reason, Status |
| Homework | Title, Subject, Due, Status |
| Lesson Plans | Title, Subject, Date |
| Assignments | Title, Subject, Due, Status, Marks |
| Quizzes and Exams | Title, Type, Opens, Duration, Status, Score |
| Documents | Title, Subject, Date |
| Fee Details | Challan no., Month, Amount, Paid, Due date, Status |

### Guardian

Same lists as the student for the chosen child, plus:
- **Fee and Challans:** Challan no., Month, Amount, Paid, Due date, Status, Print.
- **Fee Pay:** form (section 4.17) plus a history list of submissions with status.
- **Class Attendance:** same as student My Attendance.

## 4. Forms (fields)

### 4.1 Enrol / edit student
- Personal: Full name*, Father name, CNIC (13 digits, optional), Date of birth, Gender (S) Male/Female/Other, Class label (S, optional), Status (S) Active.
- Contact: Student phone, Guardian phone*, Address, City.
- Academic: Batches* (multi-select). For each chosen batch, a subjects multi-select*.
- Fees: Fee plans* (multi-select) with optional discount per plan (amount or percent). Read-only "Monthly fee" total updates live.
- Guardian: Guardian name*, Guardian email*, Guardian password* (not needed when the email is an existing guardian).
- Logins: Student email* + password*, Guardian email* + password*. Emails must be different and unique in the system.
- Existing guardian: if the guardian email already belongs to a guardian of this institute, the new student is linked to that guardian (one guardian, many children). The password, name and phone typed are ignored. If the email belongs to any other account, show "This email is already used by another account." and do not say which role or institute uses it.
- Validation: at least one batch, each batch has at least one subject, at least one fee plan.

### 4.2 Add / edit teacher
Full name*, Phone*, Email (login)*, Password*, CNIC (optional), Address, Joining date, Status. Batches* (multi) with subjects* per batch.

### 4.3 Class / Batch / Subject
Name*, Status. Name unique per institute.

### 4.4 Fee plan
Name*, Amount* (greater than 0), Status.

### 4.5 Add lecture
Title*, Date*, Start time*, Duration (minutes)*, Teacher* (admin only; teacher is fixed when a teacher creates it), Batch*, Subjects* (only those assigned to the chosen teacher in that batch), Delivery mode* (S) Manual link / In person, Meeting link (required if Manual link), Description.
Validation: no overlap for the same teacher; warn on overlap for the same batch.

### 4.6 Recurring schedule
Title*, Teacher*, Batch*, Subjects*, Delivery mode*, Meeting link, Days of week* (checkboxes), Start time*, Duration*, Start date*, End date* (or "number of weeks"). Preview list of lectures before saving. Edit scope: this one / this and all future.

### 4.7 Generate challans
Month* (month picker), Due date* (default from settings), Students: all active / by batch / pick students. Preview table (student, amount) with a checkbox per row. Skip rule: a student who already has a non-cancelled challan for that month is skipped and listed.

### 4.8 Process payment
Search challan or student*, Amount* (up to balance), Date* (default today), Method* (S) Cash / Bank transfer / Online / Other, Reference, Note. Allows partial payment.

### 4.9 Reject receipt
Reason* (short text, shown to guardian).

### 4.10 Salary plan
Name*, Type* (S) Fixed / Per lecture / Per student / Hourly / Percentage / Hybrid. Fields shown by type:
- Fixed: Monthly amount*.
- Per lecture: Rate per lecture*.
- Per student: Rate per enrolled student per month*.
- Hourly: Rate per hour*.
- Percentage: Percent of fees collected*.
- Hybrid: Fixed amount* + one extra rate*: Per lecture or Percentage.

### 4.11 Plan assignment
Teacher*, Plan*, Effective from*.

### 4.12 Advance salary
Teacher*, Amount*, Date*, Note. Deducted from the next payroll run.

### 4.13 Homework
Title*, Instructions*, Batch*, Subject*, Students (all in batch by default, or pick), Due date and time*, Worksheet file (optional), Allow late submission (checkbox).

### 4.14 Lesson plan
Title*, Batch*, Subject*, Date*, Objectives, Content*, Resources (files, optional).

### 4.15 Daily report
Date*, Batch*, Subject, Student (optional, for one-student reports), Topic covered*, Notes*, Visible to guardians (checkbox, default on).

### 4.16 Assignment / Quiz
- Assignment: Title*, Instructions*, Batch*, Subject*, Total marks*, Due date*, File (optional).
- Quiz or exam: Title*, Type* (Quiz / Exam), Batch*, Subject*, Opens at*, Duration (min)*, Total marks, Pass marks, Shuffle questions, Require full screen (exam), Flag tab leaving (exam). Questions: pick from bank or add new.
- Question: Text*, Type* (MCQ / Short answer), Options (MCQ, 2 to 6) with one correct*, Marks*, Subject*, Explanation (optional).

### 4.17 Fee Pay (guardian)
Child* (S), Challan(s) or months* (multi), Amount* (default = selected balance), Paid on* (date), Reference (text), Receipt file* (JPG, PNG, WEBP, PDF, up to 5 MB). On submit: status `waiting`, admins notified.

### 4.18 Leave request
From*, To*, Reason*. For teachers, show days used and remaining.

### 4.19 Message
To* (search by name, role-limited, see 6.5), Subject, Body*, Attachment (optional). Admin broadcast: pick audience (all, teachers, students, guardians, a batch).

### 4.20 Course document
Title*, Batch*, Subject, File* (PDF, DOC, PPT, images, up to 25 MB), Description.

### 4.21 Manage user (sub-admin)
Name*, Email*, Password*, Allowed menus* (checkboxes of the 8 groups), Status.

### 4.22 Account and profile
Name, Phone, Photo, Time zone, Appearance (Light/Dark/Auto), Notification switches (fee alerts, class alerts), Change password (current, new, confirm).

### 4.23 Login and first-time password
Login: Email*, Password*, Show password, Remember me. First-time link: New password*, Confirm*. Password rule: at least 8 characters.

### 4.24 Contact form (public)
Full name*, Institute name*, Phone*, Email, Website, Message*. Saved for Super Admin.

## 5. Bulk student upload

- Excel template with one row per student. Columns:
  `full_name*, father_name, cnic, dob (YYYY-MM-DD), gender, class_label, phone, guardian_name*, guardian_phone*, address, city, batches* (comma list), subjects* (BatchName:Subject1|Subject2; next batch after a semicolon), fee_plans* (comma list), discount, student_email*, student_password*, guardian_email*, guardian_password*`
- Steps: download template, upload, preview with row-level errors, confirm to import valid rows only.
- Built in 2.6 without `fee_plans` and `discount` (they come with Phase 7). Limits: one `.xlsx` file up to 1 MB and 50 rows. Column names are not case sensitive. Batch, subject and class names must match active rows of the institute (case is ignored). `guardian_password` may be blank when the guardian already has an account, or when an earlier row in the same file creates that guardian.
- The checked rows travel to the import step in a signed form field (valid 30 minutes, only for the admin who uploaded the file). Import checks every row again and enrols each good row in its own transaction.
- Errors listed per row (missing field, unknown batch/subject/plan, duplicate email). Import is all-or-nothing per row, never partial per row.

## 6. Business rules

### 6.1 Fees and challans
- Monthly fee = sum of the student's fee plan amounts minus discounts. Percent discounts apply per plan.
- Challan amount = monthly fee at generation time (frozen on the challan).
- Balance = amount - sum of payments. Status: `pending` (no payment), `partial` (some), `paid` (balance 0).
- Overdue = status pending or partial and today is after due date. Defaulter = overdue longer than grace days.
- A cancelled challan cannot receive payments. Cancelling a challan with payments is blocked.
- Approving a receipt creates a Payment (method Online, reference from the receipt) against the chosen challans, oldest first. Over-payment beyond balance is rejected at submit time.
- Rejecting a receipt changes nothing on the challan.

### 6.2 Portal access
- A blocked student sees a full-page "Access paused" message with the institute phone number. Guardian portal is never blocked.
- If auto-block is on: a nightly job blocks every student who is a defaulter and not exempt, and unblocks once no challan is overdue beyond grace.
- Manual block and unblock always win until the next auto run changes them. A student marked Exempt is never auto-blocked.

### 6.3 Attendance
- Attendance is per lecture per student, one row each.
- Manual: the teacher sets Present / Partial / Late / Absent for each student.
- Provider-based (later): time joined divided by lecture duration. At least Present threshold = Present; at least Partial threshold = Partial; below = Absent. Joining after the Late minutes sets Late if otherwise Present.
- Attendance % = (Present + Late + 0.5 x Partial) divided by finished lectures the student was expected in.
- Only finished lectures count. A cancelled lecture never counts.

### 6.4 Lectures
- Join opens at start minus join window. Student Join button states: `Join opens soon` (before window), `Waiting for host` (window open, teacher not started), `Join` (teacher started), `Ended`.
- Teacher presses Start to set status `live`. Finish sets `finished` automatically after the end time unless ended earlier.
- A student sees a lecture only if enrolled in that batch and subject.
- Recurring generation: on save creates lectures up to the end date, limited by the horizon setting. A nightly job extends the horizon.
- Teacher assignment check: a teacher can only create lectures for a batch and subject they are linked to.

### 6.5 Messaging reach (who can message whom)
- Admin and sub-admin: anyone in the institute.
- Teacher: admin, other teachers, students in their batches, guardians of those students.
- Student: admin, teachers of their batches.
- Guardian: admin, teachers of their children's batches.

### 6.6 Payroll (monthly, per teacher)
Lectures counted = lectures with status `finished` in the month, taught by the teacher (the lecture's current teacher).
- Fixed: gross = monthly amount.
- Per lecture: gross = lectures x rate.
- Per student: gross = distinct active students in the teacher's batches x rate.
- Hourly: gross = total finished lecture hours x rate.
- Percentage: gross = percent x fees collected in the month for batches the teacher teaches, divided by the number of teachers sharing that batch.
- Hybrid: gross = fixed + (lectures x rate, or percent calculation).
- Net = gross - open advances (deducted in full; any balance carries to next month).
- Payroll run: Admin picks month, system creates a draft row per teacher, admin can review, then Finalize. Finalized runs cannot be edited. Marking paid creates the payment record and the slip.
- Example: 18 lectures x 4,500 = 81,000, advance 10,000, net 71,000.

### 6.7 Leave
- Student leave: request, admin approves or rejects. Approved leave marks the student's attendance for that period as "excused" in reports (not counted against percentage).
- Teacher leave: days counted against yearly allowance (weekends excluded). On approval, the system lists lectures in the leave period. For each lecture the admin picks Reschedule (new date and time), Reassign (another teacher assigned to that batch and subject), or Cancel. Salary follows the teacher who finally teaches the lecture.
- Over allowance is allowed but flagged "Over allowance".

### 6.8 Homework, assignments, quizzes
- Homework due time passed: new submissions are `late` if late submission is allowed, otherwise blocked. Students without a submission at close are `pending` (shown "Missed" for assignments).
- Teacher reviews homework with a short comment and "Reviewed". Assignments get marks and feedback.
- Quiz: status becomes `live` at Opens and `closed` after opens + duration + 10 minutes. Student attempt has a countdown timer. Auto-submit when the timer ends. MCQ marked instantly. Short answers wait for the teacher. One attempt only.
- Exam mode: leaving the tab or exiting full screen is logged and shown to the teacher. It does not auto-fail.
- Guardian sees scores only after the quiz is graded.

### 6.9 Approvals
- If approval is required: new homework, lesson plan, or report is `pending_approval`. Students and guardians see it only after `approved` (homework: `published`).
- If not required: they go straight to approved.
- Rejection requires a note, shown to the teacher.

### 6.10 Documents
- Teachers upload to batches and subjects they teach. Students and guardians see documents for the child's batches.
- If downloads are locked, files open in preview only.

### 6.11 Plans and limits (assumed)
- Basic (B): setup, students, teachers, lectures, attendance, assignments, quizzes, PWA.
- Premium (P): everything in Basic plus fees, payroll, leave, homework, lesson plans, reports, messages, documents, sub-admin.
- Max active students per plan: Basic 100, Premium unlimited. (Adjustable per institute by Super Admin.)

## 7. Notifications (in-app bell)

| Event | Goes to |
|---|---|
| Lecture created or changed | students and guardians of the batch, teacher |
| Lecture starts in 15 minutes | enrolled students, teacher |
| Lecture started (host started) | enrolled students |
| Lecture cancelled | students, guardians, teacher |
| Challan generated | guardian and student of that student |
| Challan due in 3 days | guardian |
| Challan overdue | guardian, admin (defaulter list) |
| Receipt submitted | admins with Finance access |
| Receipt approved or rejected | guardian |
| Payment recorded | guardian |
| Homework or assignment published | students, guardians |
| Homework due tomorrow | students with no submission |
| Submission received | teacher |
| Homework/assignment graded | student, guardian |
| Quiz opens soon | students |
| Quiz graded | student, guardian |
| Leave requested | admins with the right access |
| Leave approved or rejected | requester |
| Item needs approval (homework, plan, report) | admins with Academic access |
| Approval result | teacher |
| New message | recipient |
| Salary slip ready | teacher |
| Portal blocked or unblocked | student |

- Each user can switch off "fee alerts" and "class alerts" (not system notices).
- Notifications older than 90 days are deleted.

## 8. Dashboards (KPI definitions)

**Admin main:** students (total, active, inactive), teachers (total, active), batches (running = batches with at least one active student), lectures today, plus recent 5 students and recent teachers, fee strip (billed this month, collected, outstanding), pending approvals count, waiting receipts count.
**Salary dashboard:** payroll this month (gross, advances, net), paid vs unpaid teachers, top lecture counts.
**Lectures dashboard:** live now, starting in the next 2 hours, today by status, teachers on leave today.
**Challan dashboard:** billed, collected, outstanding this month, challans by status, waiting receipts, defaulters count.
**Teacher:** next lecture (countdown), lectures today and this week, students, batches, subjects, pending reviews (homework and assignments to grade).
**Student:** attendance %, homework done % (submitted divided by assigned in last 30 days), upcoming lectures (7 days), fee paid % (this academic year), up-next card, fee KPIs (billed, paid, due, pending challans).
**Guardian:** per child: billed, paid, outstanding, upcoming classes (7 days), homework (submitted, pending, overdue), 6-month homework trend.

## 9. Print layouts (PDF, A4)

### 9.1 Challan
- Header: institute logo, name, address, phone. Title "Fee Challan".
- Meta: challan no., month, issue date, due date.
- Student block: name, ID, class label, batches, guardian name and phone.
- Table: fee plan lines, discounts, total payable, previous balance (if any), amount in words.
- Footer: payment instructions text (editable in settings), signature line, note about late fee (if set).
- Three copies on one page: Institute, Student, Bank/Office (labelled).
- Bulk print: all selected challans in one PDF, 1 per page.

### 9.2 Salary slip
- Header as above. Title "Salary Slip", slip no., month.
- Teacher block: name, ID, plan name.
- Earnings: lines depending on plan (lectures x rate, fixed, percent). Deductions: advances. Net pay and amount in words.
- Signature lines for teacher and accountant.

### 9.3 Receipt (payment)
Header, receipt no., date, student, challan no., amount, method, balance after, received by.

### 9.4 Report prints
Collection and defaulter reports: header, date range, table, totals row, page numbers.

### 9.5 Certificate (optional, build last)
Landscape. Institute logo, "Certificate of Completion", student name, batch and subjects, date, unique code and verify link, signature lines. Issued by admin per student on request. Rules for when to issue are manual in v1.

## 10. Seed / demo data

Built by management command: `uv run python manage.py seed_demo` (needs `DEBUG` and `SEED_DEMO_PASSWORD`; `--reset` removes it). Roadmap 2.8 built the people and academics part below. Each later phase adds the rows for its own models.

- Built in 2.8: 3 classes, 4 batches, 6 subjects, 5 teachers, 52 students (30 active, 22 inactive), 20 guardians, 1 admin, 1 sub-admin, 1 blocked and 1 exempt student. Sign-ins: `demo-admin`, `demo-sub`, `demo-super`, `demo-teacher`, `demo-student` and `demo-guardian` `@example.com`.
- Every student needs a guardian, so "20 guardians (one with two children)" cannot cover 52 students. Decided in 2.8: `demo-guardian` has exactly two children; the other 19 guardians share the other 50 students (2 or 3 each).
- Waiting for later phases: the sub-admin's Finance and People menus (9.3c), fee plans, challans and defaulters (Phase 7), lectures and attendance (Phases 3 and 4), and the rest of the list.

- 1 institute "Demo Institute" on Premium plan, Asia/Karachi, currency Rs.
- 3 class labels, 4 batches, 6 subjects, 3 fee plans.
- 52 students (30 active, 22 inactive), 5 teachers, 1 admin, 1 sub-admin (Finance and People only).
- 20 guardians (one with two children).
- 60 lectures across past, today (one live), and next 2 weeks, with one recurring series.
- Attendance for finished lectures with a mix of statuses.
- 3 months of challans: mixed paid, partial, pending, overdue. 3 waiting receipts. 4 defaulters.
- Homework, assignments, 2 quizzes (one live), approvals pending, 3 leave requests.
- Salary plans for each of the 6 types, 1 finalized payroll, 2 advances.
- 30 messages across roles.
- Fake names, numbers, and addresses only. No real people.

## 11. Copy and messages (examples)

- Empty list: "No students yet. Enrol your first student."
- Blocked student: "Access paused. Please contact the institute office at [phone]."
- Receipt rejected: "Your receipt was rejected: [reason]. You can upload a new one."
- Validation: "Choose at least one subject for [batch]."
- Success toast: "Student enrolled."
- Destructive confirm: "Deactivate [name]? They will not be able to sign in."

## 12. Open items to check against the demo later

- Real table columns and filter names.
- Real status names (especially challan and quiz attempt).
- Challan layout (copies, extra fields, late fee).
- Percentage payroll split among teachers.
- Attendance thresholds and Late rule.
- Plan limits (student caps).
- Anything in settings that has a different default.
