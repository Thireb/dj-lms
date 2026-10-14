"""Fill occurrence_date for schedule lectures made before it existed.

The best value we have is the start date in the schedule's zone. A lecture
already moved on its own keeps its new date (the old one is not stored).
"""

from zoneinfo import ZoneInfo

from django.db import migrations


def backfill(apps, schema_editor):
    Lecture = apps.get_model("lectures", "Lecture")
    # Historical models use the plain manager, so every institute's rows are
    # seen here (a migration, AGENTS.md section 6).
    lectures = Lecture.objects.filter(
        schedule__isnull=False, occurrence_date__isnull=True
    ).select_related("schedule")
    for lecture in lectures.iterator():
        zone = ZoneInfo(lecture.schedule.time_zone)
        lecture.occurrence_date = lecture.starts_at.astimezone(zone).date()
        lecture.save(update_fields=["occurrence_date"])


class Migration(migrations.Migration):
    dependencies = [("lectures", "0005_lecture_occurrence_date")]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
