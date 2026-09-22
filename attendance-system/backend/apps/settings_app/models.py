# apps/settings_app/models.py

from django.db import models


class SystemSettings(models.Model):

    organization_name = models.CharField(
        max_length=255,
        default="CodeCamp Innovation Hub"
    )

    contact_email = models.EmailField(
        blank=True
    )

    contact_phone = models.CharField(
        max_length=30,
        blank=True
    )

    auto_email_notifications = models.BooleanField(
        default=True
    )

    auto_whatsapp_popup = models.BooleanField(
        default=False
    )

    attendance_notifications_enabled = models.BooleanField(
        default=True
    )

    parent_portal_enabled = models.BooleanField(
        default=True
    )

    logo = models.ImageField(
        upload_to="settings/",
        blank=True,
        null=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):

        return "System Settings"

    def save(self, *args, **kwargs):

        self.pk = 1

        super().save(*args, **kwargs)

    class Meta:

        verbose_name = "System Settings"

        verbose_name_plural = "System Settings"
