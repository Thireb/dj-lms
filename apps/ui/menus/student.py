from __future__ import annotations

from apps.ui.menu_items import MenuGroup, MenuItem


class StudentMenu:
    @classmethod
    def groups(cls) -> tuple[MenuGroup, ...]:
        return (
            MenuGroup(
                label="Main",
                items=(
                    MenuItem(
                        "Dashboard",
                        "student:dashboard",
                        "gauge",
                        menu_key="dashboard",
                    ),
                ),
            ),
            MenuGroup(
                label="Academics",
                items=(
                    MenuItem("My lectures", "student:lecture_list", "video"),
                    MenuItem("My attendance", "student:attendance", "clipboard-check"),
                    MenuItem(
                        "Leave requests",
                        "student:leave_list",
                        "calendar",
                        feature="leave",
                    ),
                    MenuItem(
                        "Homework",
                        "student:homework_list",
                        "book-open",
                        feature="homework",
                    ),
                    MenuItem(
                        "Lesson plans",
                        "student:lesson_plan_list",
                        "clipboard",
                        feature="lesson_plans",
                    ),
                    MenuItem("Assignments", "student:assignment_list", "list-check"),
                    MenuItem("Quizzes and exams", "student:quiz_list", "pen-to-square"),
                    MenuItem("Documents", "student:documents", "folder-open"),
                ),
            ),
            MenuGroup(
                label="Messages",
                items=(
                    MenuItem(
                        "Messages",
                        "student:message_inbox",
                        "envelope",
                        feature="messaging",
                    ),
                ),
            ),
            MenuGroup(
                label="Finance",
                items=(
                    MenuItem(
                        "Fee details",
                        "student:fee_details",
                        "coins",
                        feature="fees",
                    ),
                ),
            ),
            MenuGroup(
                label="Account",
                items=(
                    MenuItem("My profile", "student:profile", "user"),
                    MenuItem("Settings", "student:settings", "gear"),
                    MenuItem("Sign out", "accounts:logout", "right-from-bracket"),
                ),
            ),
        )
