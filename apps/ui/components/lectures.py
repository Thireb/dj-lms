from apps.ui.components.base import Component


class CountdownCard(Component):
    template_name = "ui/components/countdown_card.html"

    def __init__(self, lecture, viewer, **props):
        super().__init__(
            lecture=lecture,
            viewer=viewer,
            title=getattr(lecture, "title", ""),
            scheduled_at=getattr(lecture, "scheduled_at", ""),
            meeting_link=getattr(lecture, "meeting_link", ""),
            **props,
        )


class LectureRow(Component):
    template_name = "ui/components/lecture_row.html"

    def __init__(self, lecture, viewer, **props):
        super().__init__(lecture=lecture, viewer=viewer, **props)


class ScheduleList(Component):
    template_name = "ui/components/schedule_list.html"

    def __init__(self, lectures, viewer, **props):
        super().__init__(lectures=lectures, viewer=viewer, **props)
