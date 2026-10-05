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
                        "teacher:dashboard",
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
                        "clock-rotate-left",
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
                    MenuItem("Submit report", "teacher:report_submit", "file-lines"),
                ),
            ),
            MenuGroup(
                label="Assignments",
                items=(
                    MenuItem("Assignments", "teacher:assignment_list", "list-check"),
                ),
            ),
            MenuGroup(
                label="Quizzes and exams",
                items=(
                    MenuItem("Quizzes and exams", "teacher:quiz_list", "pen-to-square"),
                ),
            ),
            MenuGroup(
                label="Messages",
                items=(
                    MenuItem(
                        "Messages",
                        "teacher:message_inbox",
                        "envelope",
                        feature="messaging",
                    ),
                ),
            ),
            MenuGroup(
                label="People",
                items=(
                    MenuItem("My students", "teacher:student_list", "user-graduate"),
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
                        "money-bill",
                        feature="payroll",
                    ),
                ),
            ),
            MenuGroup(
                label="Account",
                items=(
                    MenuItem("My profile", "teacher:profile", "user"),
                    MenuItem("Account settings", "teacher:settings", "gear"),
                    MenuItem("Sign out", "accounts:logout", "right-from-bracket"),
                ),
            ),
        )
