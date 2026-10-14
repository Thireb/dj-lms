"""Attendance pages (roadmap 4.1 to 4.3, SPEC 3 and 6.3)."""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from apps.attendance.forms import AttendanceForm
from apps.attendance.services import can_mark, roster, save_marks
from apps.lectures.ui import lecture_summary, lecture_when
from apps.lectures.views import LectureObjectMixin, TeacherLectureMixin
from apps.ui.components.data import EmptyState
from apps.ui.views.pages import FormPage


class TakeAttendancePage(LectureObjectMixin, TeacherLectureMixin, FormPage):
    """Teacher "Take attendance" for one of their finished lectures."""

    title = "Take attendance"
    form_class = AttendanceForm

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.load() or super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.load() or super().post(request, *args, **kwargs)

    def load(self) -> HttpResponse | None:
        self.lecture = self.get_lecture()
        if can_mark(self.lecture):
            self.roster = roster(self.lecture)
            return None
        messages.error(self.request, "Attendance is taken only for a finished lecture.")
        return HttpResponseRedirect(self.detail_url())

    def detail_url(self) -> str:
        return self.url("detail", pk=self.lecture.pk)

    def get_subtitle(self) -> str:
        return f"{self.lecture.title}: {lecture_when(self.lecture)}. " + (
            lecture_summary(self.lecture)
        )

    def get_form_kwargs(self) -> dict[str, Any]:
        return {"roster": self.roster, "cancel_url": self.detail_url()}

    def get_components(self) -> dict[str, Any]:
        if not self.roster:
            return {
                "form": EmptyState(
                    "No students to mark.",
                    text="No student is enrolled in this batch and subject.",
                    icon="users",
                )
            }
        return super().get_components()

    def form_valid(self, form: AttendanceForm) -> HttpResponse:
        try:
            save_marks(self.lecture, form.marks(), marked_by=self.request.user)
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, f"Attendance saved for {self.lecture.title}.")
        return HttpResponseRedirect(self.detail_url())
