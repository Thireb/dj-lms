"""Lectures the finish job closed without a Start become "not held".

Before this change the job marked every lecture past its end as finished.
A finished lecture with no ``started_at`` was never started by the teacher
(End class and the demo seed always set it), so it was not held. Its
``ended_at`` was the planned end, set by the job; clear it as well.
"""

from django.db import migrations


def mark_not_held(apps, schema_editor):
    Lecture = apps.get_model("lectures", "Lecture")
    # Historical models use the plain manager: every institute's rows (a
    # migration, AGENTS.md section 6).
    Lecture.objects.filter(status="finished", started_at__isnull=True).update(
        status="not_held", ended_at=None
    )


def mark_finished(apps, schema_editor):
    Lecture = apps.get_model("lectures", "Lecture")
    Lecture.objects.filter(status="not_held").update(status="finished")


class Migration(migrations.Migration):
    dependencies = [("lectures", "0007_lecture_not_held_status")]

    operations = [migrations.RunPython(mark_not_held, mark_finished)]
