from __future__ import annotations

from types import SimpleNamespace

from django.conf import settings
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from apps.core.menus import ADMIN_MENU_KEYS
from apps.core.roles import Role
from apps.ui.components.actions import Button, ConfirmDialog, QuickAction, Toast
from apps.ui.components.data import (
    Avatar,
    Badge,
    ChartCard,
    Column,
    DataTable,
    EmptyState,
    ProgressBar,
    StatCard,
)
from apps.ui.components.layout import (
    HeroBanner,
    Modal,
    PageHeader,
    SectionCard,
    SidebarShell,
    Tabs,
    TopNavShell,
)
from apps.ui.components.lectures import CountdownCard, LectureRow, ScheduleList
from apps.ui.components.nav import FilterBar, NotificationBell, Pagination
from apps.ui.components.pdf import PdfHeader


def _demo_institute() -> SimpleNamespace:
    return SimpleNamespace(
        name="Demo institute",
        timezone="Asia/Karachi",
        features=["fees", "payroll", "messaging", "homework", "lesson_plans", "leave"],
    )


def _admin_user() -> SimpleNamespace:
    return SimpleNamespace(
        role=Role.INSTITUTE_ADMIN,
        display_name="Demo admin",
        allowed_menus=list(ADMIN_MENU_KEYS),
    )


def _teacher_user() -> SimpleNamespace:
    return SimpleNamespace(
        role=Role.TEACHER,
        display_name="Demo teacher",
        allowed_menus=[],
    )


def _fake_lectures() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            title="Intro to algebra",
            scheduled_at="2026-08-16T15:00:00+00:00",
            meeting_link="https://meet.example.invalid/demo",
            status="scheduled",
            day="Mon 16 Aug 2026",
        ),
        SimpleNamespace(
            title="Lab session",
            scheduled_at="2026-08-17T10:00:00+00:00",
            meeting_link="https://meet.example.invalid/lab",
            status="scheduled",
            day="Tue 17 Aug 2026",
        ),
    ]


def dev_components(request: HttpRequest) -> HttpResponse:
    if not settings.DEBUG:
        raise Http404()

    admin_user = _admin_user()
    teacher_user = _teacher_user()
    lectures = _fake_lectures()
    viewer = SimpleNamespace(timezone_label="PKT")

    institute = _demo_institute()

    table = DataTable(
        rows=[
            {"student_id": "STU-001", "full_name": "Alex Sample", "status": "Active"},
            {
                "student_id": "STU-002",
                "full_name": "Jordan Example",
                "status": "Inactive",
            },
        ],
        columns=[
            Column("student_id", "ID"),
            Column("full_name", "Name"),
            Column(
                "status",
                "Status",
                render=lambda row: Badge(row["status"], tone="success"),
            ),
        ],
    )

    paginator = Paginator(list(range(1, 26)), 10)
    page_obj = paginator.get_page(2)

    components = {
        "top_nav_shell": TopNavShell(
            portal="admin",
            user=admin_user,
            active="dashboards",
            institute=institute,
        ),
        "sidebar_shell": SidebarShell(
            portal="teacher",
            user=teacher_user,
            active="dashboard",
            institute=institute,
        ),
        "hero_banner": HeroBanner(
            title="Welcome back",
            subtitle="Fake demo data only",
            chips=["Campus A", "Fall 2026"],
            actions=[Button("Create lecture", icon="plus", url="#")],
        ),
        "page_header": PageHeader(
            title="Component gallery",
            breadcrumb=["Dev", "Components"],
            actions=[Button("Refresh", variant="secondary", url="#")],
        ),
        "section_card": SectionCard(
            title="Recent activity",
            body=Badge("Sample card body text", tone="neutral"),
            link_url="#",
        ),
        "tabs": Tabs(
            tabs=[
                SimpleNamespace(id="one", label="Tab one", url="#tab-one"),
                SimpleNamespace(id="two", label="Tab two", url="#tab-two"),
            ],
            active="one",
        ),
        "modal": Modal(
            id="demo-modal",
            title="Demo modal",
            body=Button("Close", variant="secondary"),
        ),
        "stat_card": StatCard(
            "42",
            "Active students",
            note="+3 this week",
            icon="users",
        ),
        "data_table": table,
        "badge": Badge("Paid", tone="success"),
        "avatar": Avatar("Alex Sample"),
        "progress_bar": ProgressBar(65, label="Attendance"),
        "chart_card": ChartCard("Enrolments", "demo-chart", "/dev/components/"),
        "empty_state": EmptyState(
            "No lectures yet",
            text="Create your first lecture.",
            action=Button("Create lecture", url="#"),
        ),
        "button": Button("Save changes", icon="check"),
        "quick_action": QuickAction("Mark attendance", "clipboard-check", "#"),
        "confirm_dialog": ConfirmDialog(
            "Delete this record?",
            "Delete",
            url="#",
        ),
        "toast": Toast("Saved successfully"),
        "countdown_card": CountdownCard(lectures[0], viewer),
        "lecture_row": LectureRow(lectures[0], viewer),
        "schedule_list": ScheduleList(lectures, viewer),
        "notification_bell": NotificationBell(teacher_user, unread_count=3),
        "filter_bar": FilterBar(
            filters=[
                SimpleNamespace(name="q", label="Search", placeholder="Name or ID"),
            ]
        ),
        "pagination": Pagination(page_obj),
        "pdf_header": PdfHeader(institute),
    }

    return render(
        request,
        "ui/dev/components.html",
        {
            "page_title": "Component gallery",
            "components": components,
        },
    )
