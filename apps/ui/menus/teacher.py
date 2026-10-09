from __future__ import annotations

from apps.ui.menu_items import MenuGroup, MenuItem


class TeacherMenu:
    @classmethod
    def groups(cls) -> tuple[MenuGroup, ...]:
        return (
            MenuGroup(
                label="Main",
                items=(
                    MenuItem(
                        "Dashboard",
                        "teacher:home",
                        "gauge",
                        menu_key="dashboard",
                    ),
                ),
            ),
            MenuGroup(
                label="Academics",
                items=(
                    MenuItem("My lectures", "teacher:lecture_list", "video"),
                    MenuItem("Create lecture", "teacher:lecture_create", "plus"),
                    MenuItem(
                        "Schedule recurring",
                        "teacher:lecture_schedule",
                        "calendar-days",
                    ),
                    MenuItem("Schedule", "teacher:schedule", "calendar"),
                    MenuItem(
                        "Lecture history",
                        "teacher:lecture_history",
                        "history",
                    ),
                    MenuItem("Documents", "teacher:documents", "folder-open"),
                ),
            ),
            MenuGroup(
                label="Planning",
                items=(
                    MenuItem(
                        "Lesson plans",
                        "teacher:lesson_plan_list",
                        "clipboard",
                        feature="lesson_plans",
                    ),
                    MenuItem(
                        "Homework",
                        "teacher:homework_list",
                        "book-open",
                        feature="homework",
                    ),
                    MenuItem("Submit report", "teacher:report_submit", "file-text"),
                ),
            ),
            MenuGroup(
                label="Assignments",
                items=(
                    MenuItem("Assignments", "teacher:assignment_list", "list-checks"),
                ),
            ),
            MenuGroup(
                label="Quizzes and exams",
                items=(
                    MenuItem("Quizzes and exams", "teacher:quiz_list", "square-pen"),
                ),
            ),
            MenuGroup(
                label="Messages",
                items=(
                    MenuItem(
                        "Messages",
                        "teacher:message_inbox",
                        "mail",
                        feature="messaging",
                    ),
                ),
            ),
            MenuGroup(
                label="People",
                items=(
                    MenuItem("My students", "teacher:student_list", "graduation-cap"),
                ),
            ),
            MenuGroup(
                label="Leave",
                items=(
                    MenuItem(
                        "Apply leave",
                        "teacher:leave_apply",
                        "calendar-plus",
                        feature="leave",
                    ),
                ),
            ),
            MenuGroup(
                label="Finance",
                items=(
                    MenuItem(
                        "My salary",
                        "teacher:salary",
                        "banknote",
                        feature="payroll",
                    ),
                ),
            ),
            MenuGroup(
                label="Account",
                items=(
                    MenuItem("My profile", "accounts:profile", "user"),
                    MenuItem("Account settings", "teacher:settings", "settings"),
                    MenuItem("Sign out", "accounts:logout", "log-out"),
                ),
            ),
        )
