"""Basic plan holds only Basic features (Phase 1 audit G4)."""

from __future__ import annotations

from django.db import migrations

BASIC_FEATURES = ["messaging", "time_zone_lectures"]
OLD_BASIC_FEATURES = ["fees", "homework", "leave", "lesson_plans", "time_zone_lectures"]


def set_basic_features(apps, schema_editor) -> None:
    Plan = apps.get_model("institutes", "Plan")
    Plan.objects.filter(code="basic").update(feature_keys=BASIC_FEATURES)


def restore_old_basic_features(apps, schema_editor) -> None:
    Plan = apps.get_model("institutes", "Plan")
    Plan.objects.filter(code="basic").update(feature_keys=OLD_BASIC_FEATURES)


class Migration(migrations.Migration):
    dependencies = [
        ("institutes", "0003_plan_institute_settings"),
    ]

    operations = [
        migrations.RunPython(set_basic_features, restore_old_basic_features),
    ]
