from __future__ import annotations

from apps.ui.menu_items import MenuGroup, MenuItem


class GuardianMenu:
    @classmethod
    def groups(cls) -> tuple[MenuGroup, ...]:
        return (
            MenuGroup(
                label="Main",
                items=(
                    MenuItem(
                        "Dashboard",
                        "guardian:home",
                        "gauge",
                        menu_key="dashboard",
                    ),
                ),
            ),
            MenuGroup(
                label="Academics",
                items=(
                    MenuItem(
                        "Lectures schedule",
                        "guardian:lecture_schedule",
                        "calendar",
                        menu_key="lecture_schedule",
                    ),
                    MenuItem(
                        "Homework",
                        "guardian:homework_list",
                        "book-open",
                        feature="homework",
                    ),
                    MenuItem(
                        "Lesson plans",
                        "guardian:lesson_plan_list",
                        "clipboard",
                        feature="lesson_plans",
                    ),
                    MenuItem(
                        "Assignments",
                        "guardian:assignment_list",
                        "list-checks",
                        menu_key="assignments",
                    ),
                    MenuItem(
                        "Quizzes and exams",
                        "guardian:quiz_list",
                        "square-pen",
                        menu_key="quizzes",
                    ),
                    MenuItem(
                        "Class attendance",
                        "guardian:attendance",
                        "clipboard-check",
                        menu_key="attendance",
                    ),
                ),
            ),
            MenuGroup(
                label="Finance",
                items=(
                    MenuItem(
                        "Fee and challans",
                        "guardian:fee_list",
                        "receipt",
                        feature="fees",
                    ),
                    MenuItem(
                        "Fee pay",
                        "guardian:fee_pay",
                        "credit-card",
                        feature="fees",
                    ),
                ),
            ),
            MenuGroup(
                label="Communication",
                items=(
                    MenuItem(
                        "Messages",
                        "guardian:message_inbox",
                        "mail",
                        menu_key="messages",
                        feature="messaging",
                        badge="guardian:message_unread",
                    ),
                ),
            ),
            MenuGroup(
                label="Account",
                items=(
                    MenuItem("Student profile", "guardian:student_profile", "user"),
                    MenuItem("My account", "accounts:profile", "user"),
                    MenuItem("Account settings", "guardian:settings", "settings"),
                    MenuItem("Sign out", "accounts:logout", "log-out"),
                ),
            ),
        )
