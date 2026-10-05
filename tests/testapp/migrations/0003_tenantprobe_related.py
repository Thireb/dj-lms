from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("testapp", "0002_alter_tenantprobe_institute"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantprobe",
            name="related",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="linked_probes",
                to="testapp.tenantprobe",
            ),
        ),
    ]
