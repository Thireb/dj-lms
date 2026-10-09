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
                        "Quizzes and exams",
                        "guardian:quiz_list",
                        "square-pen",
                    ),
                    MenuItem(
                        "Class attendance",
                        "guardian:attendance",
                        "clipboard-check",
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
                        feature="messaging",
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
