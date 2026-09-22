from django.db import migrations, models
from django.utils import timezone


def backfill_parent_updated_at(apps, schema_editor):
    Parent = apps.get_model("students", "Parent")
    Parent.objects.filter(updated_at__isnull=True).update(
        updated_at=timezone.now()
    )


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0009_tutor_teachingclass_studentparent_teaching_class"),
    ]

    operations = [
        migrations.AddField(
            model_name="parent",
            name="must_change_password",
            field=models.BooleanField(
                default=False,
                help_text="Require the parent to change their password after first login.",
            ),
        ),
        migrations.AlterField(
            model_name="parent",
            name="must_change_password",
            field=models.BooleanField(
                default=True,
                help_text="Require the parent to change their password after first login.",
            ),
        ),
        migrations.AddField(
            model_name="parent",
            name="last_login_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="parent",
            name="last_password_change",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="parent",
            name="is_active",
            field=models.BooleanField(
                default=True,
            ),
        ),
        migrations.AddField(
            model_name="parent",
            name="updated_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.RunPython(
            backfill_parent_updated_at,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="parent",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
            ),
        ),
    ]
