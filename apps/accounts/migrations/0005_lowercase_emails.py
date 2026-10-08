"""Lower-case every stored email before the case-insensitive constraint (audit H2)."""

from django.db import migrations
from django.db.models.functions import Lower


def lowercase_emails(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    seen: dict[str, int] = {}
    for pk, email in User.objects.values_list("pk", "email"):
        key = email.strip().lower()
        if key in seen:
            msg = (
                f"Users {seen[key]} and {pk} share the email {key!r} apart from "
                "case. Change one of them, then run the migration again."
            )
            raise RuntimeError(msg)
        seen[key] = pk
    User.objects.exclude(email=Lower("email")).update(email=Lower("email"))


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_merge_20261006_1442")]

    operations = [migrations.RunPython(lowercase_emails, migrations.RunPython.noop)]
