from django.db import models


class Notification(models.Model):

    CHANNEL_CHOICES = (

        ("email", "Email"),

        ("whatsapp", "WhatsApp"),

        ("sms", "SMS"),

    )

    STATUS_CHOICES = (

        ("pending", "Pending"),

        ("sent", "Sent"),

        ("failed", "Failed"),

    )

    recipient = models.CharField(
        max_length=255
    )

    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES
    )

    subject = models.CharField(
        max_length=255,
        blank=True
    )

    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    sent_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):

        return (

            f"{self.channel} - "

            f"{self.recipient}"

        )