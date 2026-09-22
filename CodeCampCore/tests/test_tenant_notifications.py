import datetime
from django.test import TestCase
from django.core import mail
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from apps.tenants.models import Tenant, TenantWebhookEndpoint
from apps.tenants.services import TenantNotificationService
from apps.accounts.models import Profile, Attendance
from apps.courses.models import Course, Subject
from apps.scheduling.models import Batch

User = get_user_model()


class TenantNotificationAndWebhookTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Lagos Tech Hub",
            slug="lagos-hub",
            subdomain="lagoshub",
            subscription_tier="pro",
            max_students=500,
        )

        self.student = User.objects.create_user(
            username="kemi_ade",
            first_name="Kemi",
            last_name="Ade",
            email="kemi.parent@example.com",
            password="safe-password-123",
        )
        self.profile = self.student.profile
        self.profile.tenant = self.tenant
        self.profile.external_attendance_id = "STU-990"
        self.profile.save()

        self.course = Course.objects.create(
            tenant=self.tenant,
            name="Robotics Summer Camp",
            duration_weeks=6,
            fee=25000.0,
            is_published=True,
        )
        self.subject = Subject.objects.create(
            course=self.course,
            name="Robotics Lab",
        )
        self.batch = Batch.objects.create(
            tenant=self.tenant,
            course=self.course,
            name="Morning Cohort",
            start_date=datetime.date.today(),
            end_date=datetime.date.today() + datetime.timedelta(days=42),
            duration_weeks=6,
            is_published=True,
        )

    def test_present_attendance_email_alert(self):
        mail.outbox = []

        attendance = Attendance.objects.create(
            tenant=self.tenant,
            student=self.student,
            subject=self.subject,
            batch=self.batch,
            date=datetime.date.today(),
            status="Present",
            check_in_time=datetime.time(9, 15),
        )

        result = TenantNotificationService.send_attendance_alert(attendance)

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn("Safe Arrival Alert", sent_email.subject)
        self.assertIn("Kemi Ade", sent_email.subject)
        self.assertIn("kemi.parent@example.com", sent_email.to)
        self.assertIn("Lagos Tech Hub", sent_email.body)

    def test_absent_attendance_email_alert(self):
        mail.outbox = []

        attendance = Attendance.objects.create(
            tenant=self.tenant,
            student=self.student,
            subject=self.subject,
            batch=self.batch,
            date=datetime.date.today(),
            status="Absent",
        )

        result = TenantNotificationService.send_attendance_alert(attendance)

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn("Attendance Notice", sent_email.subject)
        self.assertIn("marked Absent", sent_email.subject)
        self.assertIn("kemi.parent@example.com", sent_email.to)

    @patch("urllib.request.urlopen")
    def test_outbound_webhook_dispatch(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        webhook_ep = TenantWebhookEndpoint.objects.create(
            tenant=self.tenant,
            target_url="https://external-kiosk.org/api/webhooks/attendance/",
            events="attendance.all",
            is_active=True,
        )

        attendance = Attendance.objects.create(
            tenant=self.tenant,
            student=self.student,
            subject=self.subject,
            batch=self.batch,
            date=datetime.date.today(),
            status="Present",
            check_in_time=datetime.time(8, 45),
        )

        TenantNotificationService.send_attendance_alert(attendance)

        self.assertTrue(mock_urlopen.called)
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://external-kiosk.org/api/webhooks/attendance/")
        self.assertIn("X-codecamp-signature", req.headers)
        self.assertEqual(req.headers["X-codecamp-event"], "attendance.checkin")
