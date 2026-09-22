from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import Course

from .models import Payment


class PaymentReminderCommandTests(TestCase):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_payment_reminders_command_sends_due_email(self):
        student = User.objects.create_user(
            username="payer",
            email="payer@example.com",
            password="safe-password-123",
        )
        course = Course.objects.create(name="Python Basics", fee=100000, is_published=True)
        payment = Payment.objects.create(
            student=student,
            course=course,
            amount_due=100000,
            amount_paid=20000,
            monthly_payment=20000,
            status="partial",
        )
        payment.payment_date = timezone.now() - timedelta(days=30)
        payment.save(update_fields=["payment_date"])

        call_command("send_payment_reminders")

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Payment Reminder", mail.outbox[0].subject)
