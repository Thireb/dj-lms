from __future__ import annotations

from apps.ui.components.base import Component
from apps.ui.components.lectures import scheduled_at_to_iso


class AttemptTimer(Component):
    """The time left in a quiz attempt, kept at the top of the screen. When
    it reaches zero, ``attemptTimer`` (``static/js/app.js``) submits the
    form ``form_id`` with ``auto_submit=1``. ``deadline`` is validated to a
    UTC ISO string in ``data-deadline``; without JavaScript the text shows
    the deadline and the server still ends the attempt."""

    template_name = "ui/components/attempt_timer.html"

    def __init__(self, deadline, form_id, label="", **props):
        super().__init__(
            deadline_iso=scheduled_at_to_iso(deadline),
            form_id=form_id,
            label=label,
            **props,
        )


class ExamGuard(Component):
    """Exam mode on the attempt page (SPEC 6.8). It says what is recorded
    and, with ``full_screen``, offers "Enter full screen". ``examGuard``
    (``static/js/app.js``) posts ``kind=left_page`` when the page is hidden
    (with ``flag_leaving``) and ``kind=left_full_screen`` when full screen
    ends (with ``full_screen``) to ``event_url``, with the CSRF token of
    the form ``form_id``. Nothing is sent while the page itself navigates
    (Submit or the timer). It never blocks the answers."""

    template_name = "ui/components/exam_guard.html"

    def __init__(
        self, event_url, form_id, *, full_screen=False, flag_leaving=False, **props
    ):
        from apps.ui.safe_url import safe_url

        super().__init__(
            event_url=safe_url(event_url),
            form_id=form_id,
            full_screen=full_screen,
            flag_leaving=flag_leaving,
            **props,
        )
