from __future__ import annotations

from apps.core import menus as menu_keys
from apps.ui.menu_items import MenuGroup, MenuItem


class AdminMenu:
    @classmethod
    def groups(cls) -> tuple[MenuGroup, ...]:
        return (
            MenuGroup(
                label="Dashboards",
                menu_key=menu_keys.DASHBOARDS,
                items=(
                    MenuItem("Main", "admin:dashboard_main", "gauge"),
                    MenuItem("Salary", "admin:dashboard_salary", "money-bill"),
                    MenuItem("Lectures", "admin:dashboard_lectures", "video"),
                    MenuItem("Challan", "admin:dashboard_challan", "file-invoice"),
                ),
            ),
            MenuGroup(
                label="Institute",
                menu_key=menu_keys.INSTITUTE,
                items=(
                    MenuItem("Campus", "admin:campus", "school"),
                    MenuItem("Classes", "admin:class_list", "layer-group"),
                    MenuItem("Batches", "admin:batch_list", "users"),
                    MenuItem("Subjects", "admin:subject_list", "book"),
                    MenuItem(
                        "Fee plans",
                        "admin:fee_plan_list",
                        "coins",
                        feature="fees",
                    ),
                ),
            ),
            MenuGroup(
                label="People",
                menu_key=menu_keys.PEOPLE,
                items=(
                    MenuItem("All students", "admin:student_list", "user-graduate"),
                    MenuItem("Enrol student", "admin:student_create", "user-plus"),
                    MenuItem("Bulk upload", "admin:student_bulk_upload", "upload"),
                    MenuItem(
                        "Student attendance history",
                        "admin:student_attendance_history",
                        "clipboard-list",
                    ),
                    MenuItem("Portal access", "admin:portal_access", "lock"),
                    MenuItem("All teachers", "admin:teacher_list", "chalkboard-user"),
                    MenuItem("Add teacher", "admin:teacher_create", "user-plus"),
                    MenuItem(
                        "Teacher lecture history",
                        "admin:teacher_lecture_history",
                        "clock-rotate-left",
                    ),
                ),
            ),
            MenuGroup(
                label="Online lectures",
                menu_key=menu_keys.ONLINE_LECTURES,
                items=(
                    MenuItem("All lectures", "admin:lecture_list", "list"),
                    MenuItem("Add lecture", "admin:lecture_create", "plus"),
                    MenuItem(
                        "Recurring schedules",
                        "admin:lecture_schedule_list",
                        "calendar-days",
                    ),
                    MenuItem("Master meeting", "admin:master_meeting", "link"),
                ),
            ),
            MenuGroup(
                label="Finance",
                menu_key=menu_keys.FINANCE,
                items=(
                    MenuItem(
                        "Generate challan",
                        "admin:challan_generate",
                        "file-circle-plus",
                        feature="fees",
                    ),
                    MenuItem(
                        "Challan records",
                        "admin:challan_list",
                        "file-invoice-dollar",
                        feature="fees",
                    ),
                    MenuItem(
                        "Process payment",
                        "admin:payment_process",
                        "cash-register",
                        feature="fees",
                    ),
                    MenuItem(
                        "Receipt inbox",
                        "admin:receipt_inbox",
                        "inbox",
                        feature="fees",
                    ),
                    MenuItem(
                        "Daily reports",
                        "admin:fee_report_daily",
                        "chart-line",
                        feature="fees",
                    ),
                    MenuItem(
                        "Monthly reports",
                        "admin:fee_report_monthly",
                        "chart-column",
                        feature="fees",
                    ),
                    MenuItem(
                        "Yearly reports",
                        "admin:fee_report_yearly",
                        "chart-pie",
                        feature="fees",
                    ),
                    MenuItem(
                        "Fee defaulters",
                        "admin:fee_defaulters",
                        "triangle-exclamation",
                        feature="fees",
                    ),
                ),
            ),
            MenuGroup(
                label="Teacher salary",
                menu_key=menu_keys.TEACHER_SALARY,
                items=(
                    MenuItem(
                        "Salary plans",
                        "admin:salary_plan_list",
                        "file-contract",
                        feature="payroll",
                    ),
                    MenuItem(
                        "Plan assignments",
                        "admin:salary_plan_assignments",
                        "user-tag",
                        feature="payroll",
                    ),
                    MenuItem(
                        "Payroll",
                        "admin:payroll_run",
                        "calculator",
                        feature="payroll",
                    ),
                    MenuItem(
                        "Payment status",
                        "admin:salary_payment_status",
                        "circle-check",
                        feature="payroll",
                    ),
                    MenuItem(
                        "Payment history",
                        "admin:salary_payment_history",
                        "clock-rotate-left",
                        feature="payroll",
                    ),
                    MenuItem(
                        "Advance salary",
                        "admin:salary_advance",
                        "hand-holding-dollar",
                        feature="payroll",
                    ),
                    MenuItem(
                        "Salary reports",
                        "admin:salary_reports",
                        "chart-bar",
                        feature="payroll",
                    ),
                ),
            ),
            MenuGroup(
                label="Academic",
                menu_key=menu_keys.ACADEMIC,
                items=(
                    MenuItem(
                        "Course documents",
                        "admin:course_documents",
                        "folder-open",
                    ),
                    MenuItem(
                        "Homework approval",
                        "admin:homework_approval",
                        "book-open",
                        feature="homework",
                    ),
                    MenuItem(
                        "Lesson plan approval",
                        "admin:lesson_plan_approval",
                        "clipboard",
                        feature="lesson_plans",
                    ),
                    MenuItem("Quizzes and exams", "admin:quiz_list", "pen-to-square"),
                    MenuItem(
                        "Reports received",
                        "admin:reports_received",
                        "file-lines",
                    ),
                    MenuItem(
                        "Student leave approval",
                        "admin:student_leave_approval",
                        "calendar-check",
                        feature="leave",
                    ),
                    MenuItem(
                        "Teacher leave approval",
                        "admin:teacher_leave_approval",
                        "calendar-check",
                        feature="leave",
                    ),
                ),
            ),
            MenuGroup(
                label="Messages",
                menu_key=menu_keys.MESSAGES,
                items=(
                    MenuItem(
                        "Inbox",
                        "admin:message_inbox",
                        "inbox",
                        feature="messaging",
                    ),
                    MenuItem(
                        "Send message",
                        "admin:message_compose",
                        "paper-plane",
                        feature="messaging",
                    ),
                    MenuItem(
                        "Message monitor",
                        "admin:message_monitor",
                        "eye",
                        feature="messaging",
                    ),
                ),
            ),
        )
