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
