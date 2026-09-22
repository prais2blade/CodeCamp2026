from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    ADMIN = "ADMIN"
    TEACHER = "TEACHER"

    ROLE_CHOICES = (
        (ADMIN, "Admin"),
        (TEACHER, "Teacher"),
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=TEACHER
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    staff_must_change_password = models.BooleanField(
        default=False,
        help_text=(
            "Require this staff user to change their "
            "temporary password after login."
        ),
    )

    def __str__(self):
        return self.username
