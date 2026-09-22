from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="staff_must_change_password",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Require this staff user to change their "
                    "temporary password after login."
                ),
            ),
        ),
    ]
