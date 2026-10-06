"""Hash existing SetPasswordToken.key values (previously stored in plain text)."""

from __future__ import annotations

import hashlib

from django.db import migrations


def _is_sha256_hex(value: str) -> bool:
    if len(value) != 64:
        return False
    return all(ch in "0123456789abcdef" for ch in value)


def hash_plaintext_keys(apps, schema_editor) -> None:
    SetPasswordToken = apps.get_model("accounts", "SetPasswordToken")
    for token in SetPasswordToken.objects.all().iterator():
        if _is_sha256_hex(token.key):
            continue
        token.key = hashlib.sha256(token.key.encode("utf-8")).hexdigest()
        token.save(update_fields=["key"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_set_password_token"),
    ]

    operations = [
        migrations.RunPython(hash_plaintext_keys, migrations.RunPython.noop),
    ]
