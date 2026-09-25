from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import Profile, Attendance, SummerCertificate
from apps.courses.models import Course, Subject
from apps.scheduling.models import Batch
from apps.payments.models import Payment


class SummerAlumniTransitionTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create Course & Batch
        self.summer_course = Course.objects.create(
            name="Summer Coding Bootcamp 2026",
            description="Summer bootcamp curriculum",
            fee=Decimal("25000.00"),
            is_published=True
        )
        self.main_course = Course.objects.create(
            name="Full-Stack Web Engineering",
            description="Full academic term software engineering",
            fee=Decimal("50000.00"),
            is_published=True
        )

        import datetime
        today = datetime.date.today()
        self.summer_batch = Batch.objects.create(
            name="Summer Cohort A",
            course=self.summer_course,
            mode="onsite",
            batch_type="weekdays",
            session_period="morning",
            days_pattern="mon_wed_fri",
            start_date=today - datetime.timedelta(days=30),
            end_date=today,
            is_published=True
        )
        self.main_batch = Batch.objects.create(
            name="Fall Term Cohort 1",
            course=self.main_course,
            mode="onsite",
            batch_type="weekdays",
            session_period="morning",
            days_pattern="mon_wed_fri",
            start_date=today + datetime.timedelta(days=7),
            end_date=today + datetime.timedelta(days=90),
            is_published=True
        )

        # Create Summer Student
        self.student_user = User.objects.create_user(
            username="summer_student",
            email="summer@example.com",
            password="Password123!",
            first_name="Summer",
            last_name="Graduate"
        )
        self.profile = self.student_user.profile
        self.profile.role = "student"
        self.profile.student_status = "active"
        self.profile.course = self.summer_course
        self.profile.batch = self.summer_batch
        self.profile.has_paid = True
        self.profile.paid_amount = Decimal("25000.00")
        self.profile.save()

        # Initial summer fee payment (1-month summer fee)
        self.summer_payment = Payment.objects.create(
            student=self.student_user,
            course=self.summer_course,
            batch=self.summer_batch,
            amount_due=Decimal("25000.00"),
            amount_paid=Decimal("25000.00"),
            status="paid"
        )

        # Create subject and attendance
        self.subject = Subject.objects.create(
            name="Python Fundamentals",
            course=self.summer_course
        )
        Attendance.objects.create(
            student=self.student_user,
            subject=self.subject,
            batch=self.summer_batch,
            status="Present"
        )

    def test_management_command_deactivates_to_summer_alumni(self):
        """Management command transitions students to summer_alumni and resets has_paid for new term."""
        call_command('deactivate_summer_students', '--all-summer', '--auto-certificates')

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.student_status, 'summer_alumni')
        self.assertFalse(self.profile.has_paid)

        # Verify auto-certificate was created
        cert = SummerCertificate.objects.filter(student=self.student_user).first()
        self.assertIsNotNone(cert)
        self.assertIn("Summer Coding Bootcamp 2026", cert.title)

    def test_student_dashboard_redirects_summer_alumni_to_hub(self):
        """Summer alumni accessing student_dashboard are gated and redirected to student_summer_hub."""
        self.profile.student_status = 'summer_alumni'
        self.profile.save()

        self.client.login(username="summer_student", password="Password123!")
        response = self.client.get(reverse('student_dashboard'))
        self.assertRedirects(response, reverse('student_summer_hub'))

    def test_student_summer_hub_renders_performance_and_certificate(self):
        """Summer hub view renders attendance, certificates, and continuation options."""
        self.profile.student_status = 'summer_alumni'
        self.profile.save()

        self.client.login(username="summer_student", password="Password123!")
        response = self.client.get(reverse('student_summer_hub'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Summer Completion & Continuation Hub")
        self.assertContains(response, "Congratulations, Summer!")
        self.assertContains(response, "100.0%")  # Attendance percentage
        self.assertContains(response, "Continue to Next Term")

    def test_certificate_view_and_printable_template(self):
        """Students can view their certificate template and verification ID."""
        cert = SummerCertificate.objects.create(
            student=self.student_user,
            course=self.summer_course,
            title="Certificate of Completion - Summer 2026",
            grade_or_score="Distinction"
        )

        self.client.login(username="summer_student", password="Password123!")
        response = self.client.get(reverse('view_summer_certificate'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Certificate of Completion")
        self.assertContains(response, "Summer Graduate")
        self.assertContains(response, cert.reference_id)

    def test_continuation_registration_flow(self):
        """Student selects new main term course/batch; invoice is generated and redirects to payments."""
        self.profile.student_status = 'summer_alumni'
        self.profile.save()

        self.client.login(username="summer_student", password="Password123!")

        # GET continuation form
        get_response = self.client.get(reverse('student_continue_registration'))
        self.assertEqual(get_response.status_code, 200)
        self.assertContains(get_response, "Select Your Program Track & Cohort")

        # POST continuation registration
        post_response = self.client.post(reverse('student_continue_registration'), {
            'course_id': self.main_course.id,
            'batch_id': self.main_batch.id,
        })
        self.assertRedirects(post_response, reverse('student_payments'))

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.course, self.main_course)
        self.assertEqual(self.profile.batch, self.main_batch)

        # Check pending continuation payment
        pending_payment = Payment.objects.filter(
            student=self.student_user,
            course=self.main_course,
            status='pending'
        ).first()
        self.assertIsNotNone(pending_payment)
        self.assertEqual(pending_payment.amount_due, Decimal("50000.00"))

    def test_payment_recording_automatically_reactivates_student(self):
        """When accountant/student records tuition payment, student_status automatically flips to 'active'."""
        self.profile.student_status = 'summer_alumni'
        self.profile.has_paid = False
        self.profile.save()

        new_payment = Payment.objects.create(
            student=self.student_user,
            course=self.main_course,
            batch=self.main_batch,
            amount_due=Decimal("50000.00"),
            amount_paid=Decimal("0.00"),
            status='pending'
        )

        # Record payment (either via accountant desk, admin command center, or student checkout)
        new_payment.amount_paid = Decimal("50000.00")
        new_payment.update_status()

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.student_status, 'active')
        self.assertTrue(self.profile.has_paid)

        # Now accessing student_dashboard directly loads the dashboard without redirect
        self.client.login(username="summer_student", password="Password123!")
        response = self.client.get(reverse('student_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome, Summer Graduate")
