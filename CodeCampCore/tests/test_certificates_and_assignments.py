import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from apps.accounts.models import Profile, Certificate
from apps.courses.models import Course, Subject, Assignment, Submission
from apps.scheduling.models import Batch
from apps.tenants.models import Tenant
from apps.tenants.utils import get_tenant_signatory_data


class CertificatesAndAssignmentsTest(TestCase):
    def setUp(self):
        self.client = Client()

        # Create Tenant
        self.tenant = Tenant.objects.create(
            name="CodeCamp Global Tech Academy",
            slug="lagos-hq",
            is_default=True,
            director_name="Engr. Praise",
            director_title="Academic Director & Lead Instructor"
        )

        # Admin user
        self.admin_user = User.objects.create_superuser(
            username="admin_praise",
            email="praise@codecamp.com.ng",
            password="adminpassword123"
        )

        # Student user
        self.student_user = User.objects.create_user(
            username="alex_student",
            email="alex@codecamp.com.ng",
            password="studentpassword123",
            first_name="Alex",
            last_name="Doe"
        )

        # Course & Batch
        self.course = Course.objects.create(
            name="Full-Stack Web Development",
            slug="full-stack-web-development",
            duration_weeks=12,
            is_published=True
        )
        self.batch = Batch.objects.create(
            course=self.course,
            name="Cohort Alpha 2026",
            start_date=datetime.date.today(),
            end_date=datetime.date.today() + datetime.timedelta(days=90)
        )
        self.subject = Subject.objects.create(
            course=self.course,
            name="Backend API Architecture",
            instructor=self.admin_user
        )

        # Profile
        self.student_profile = self.student_user.profile
        self.student_profile.role = 'student'
        self.student_profile.student_status = 'active'
        self.student_profile.course = self.course
        self.student_profile.batch = self.batch
        self.student_profile.tenant = self.tenant
        self.student_profile.save()

    def test_tenant_signatory_helper(self):
        signatory = get_tenant_signatory_data(tenant=self.tenant)
        self.assertEqual(signatory['director_name'], "Engr. Praise")
        self.assertEqual(signatory['director_title'], "Academic Director & Lead Instructor")

    def test_certificate_issuance_and_verification(self):
        cert = Certificate.objects.create(
            student=self.student_user,
            course=self.course,
            batch=self.batch,
            title="Certificate of Completion - Full-Stack Web Development",
            grade="Distinction",
            tenant=self.tenant,
            issued_by=self.admin_user
        )
        self.assertIsNotNone(cert.reference_id)
        self.assertTrue(cert.formatted_ref.startswith("CC-"))

        # Verify endpoint (public)
        verify_url = reverse('verify_certificate', args=[cert.reference_id])
        response = self.client.get(verify_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alex Doe")
        self.assertContains(response, "Distinction")

    def test_assignment_rubric_and_submission_grading(self):
        assignment = Assignment.objects.create(
            subject=self.subject,
            batch=self.batch,
            week_number=1,
            title="REST API Architecture Lab",
            due_date=datetime.date.today() + datetime.timedelta(days=7),
            max_score=100,
            created_by=self.admin_user
        )
        self.assertEqual(assignment.week_number, 1)
        rubric = assignment.get_rubric()
        self.assertEqual(len(rubric), 4)

        # Student submission
        submission = Submission.objects.create(
            assignment=assignment,
            student=self.student_user,
            repo_url="https://github.com/alexdoe/api-lab",
            live_demo_url="https://api-lab.vercel.app",
            notes="Implemented JWT authentication and Swagger documentation."
        )

        # Instructor grades with rubric
        submission.rubric_scores = {
            'functionality': 38.0,
            'code_quality': 24.0,
            'ui_ux': 18.0,
            'best_practices': 14.0
        }
        total = sum(submission.rubric_scores.values())
        submission.total_score = total
        submission.letter_grade = submission.calculate_letter_grade()
        submission.status = 'graded'
        submission.graded_by = self.admin_user
        submission.save()

        self.assertEqual(submission.total_score, 94.0)
        self.assertEqual(submission.letter_grade, 'Distinction')

        # Student Gradebook
        self.client.login(username="alex_student", password="studentpassword123")
        gradebook_url = reverse('student_weekly_gradebook')
        res = self.client.get(gradebook_url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "94.0%")
        self.assertContains(res, "Distinction")
