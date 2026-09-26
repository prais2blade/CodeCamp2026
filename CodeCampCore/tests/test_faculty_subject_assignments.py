from django.test import TestCase, Client
from django.contrib.auth.models import User
from apps.courses.models import Course, Subject, Assignment, Submission, BatchSubjectTutor
from apps.scheduling.models import Batch
from apps.accounts.models import Profile
from datetime import date, timedelta


class FacultySubjectAssignmentTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin
        self.admin_user = User.objects.create_superuser(
            username='admin_boss',
            password='password123',
            email='admin@codecamp.org'
        )

        # Tutors
        self.tutor_python = User.objects.create_user(
            username='tutor_python',
            password='password123',
            first_name='Peter',
            last_name='Python'
        )
        Profile.objects.filter(user=self.tutor_python).update(role='instructor')

        self.tutor_electronics = User.objects.create_user(
            username='tutor_electronics',
            password='password123',
            first_name='Eli',
            last_name='Electronics'
        )
        Profile.objects.filter(user=self.tutor_electronics).update(role='instructor')

        # Course: Robotics
        self.robotics_course = Course.objects.create(
            name="Robotics & Embedded Systems",
            slug="robotics",
            duration_weeks=8,
            fee=35000.00,
            is_published=True
        )

        # Subjects under Robotics
        self.subj_python = Subject.objects.create(
            course=self.robotics_course,
            name="Python Programming"
        )
        self.subj_cpp = Subject.objects.create(
            course=self.robotics_course,
            name="C++ Core"
        )
        self.subj_electronics = Subject.objects.create(
            course=self.robotics_course,
            name="Electronics & Sensors"
        )

        # Cohort / Batch
        self.batch_a = Batch.objects.create(
            name="Robotics 2026 Batch A",
            course=self.robotics_course,
            mode='onsite',
            batch_type='weekdays',
            session_period='morning',
            days_pattern='mon_wed_fri',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=60),
            is_published=True
        )

        # Students
        self.student_all = User.objects.create_user(
            username='student_full',
            password='password123'
        )
        self.profile_all, _ = Profile.objects.get_or_create(user=self.student_all)
        self.profile_all.role = 'student'
        self.profile_all.course = self.robotics_course
        self.profile_all.batch = self.batch_a
        self.profile_all.has_paid = True
        self.profile_all.tuition_paid = True
        self.profile_all.is_verified = True
        self.profile_all.onboarding_stage = 'finished'
        self.profile_all.save()
        # Enrolls in all subjects
        self.profile_all.enroll_in_course_subjects()

        self.student_spec = User.objects.create_user(
            username='student_python_only',
            password='password123'
        )
        self.profile_spec, _ = Profile.objects.get_or_create(user=self.student_spec)
        self.profile_spec.role = 'student'
        self.profile_spec.course = self.robotics_course
        self.profile_spec.batch = self.batch_a
        self.profile_spec.has_paid = True
        self.profile_spec.tuition_paid = True
        self.profile_spec.is_verified = True
        self.profile_spec.onboarding_stage = 'finished'
        self.profile_spec.save()
        # Enrolls ONLY in Python
        self.profile_spec.enroll_in_course_subjects([self.subj_python.id])

    def test_student_subject_enrollment(self):
        """Verifies students enroll in all course subjects or specific electives."""
        self.assertEqual(self.profile_all.enrolled_subjects.count(), 3)
        self.assertEqual(self.profile_spec.enrolled_subjects.count(), 1)
        self.assertIn(self.subj_python, self.profile_spec.enrolled_subjects.all())
        self.assertNotIn(self.subj_electronics, self.profile_spec.enrolled_subjects.all())

    def test_1click_bulk_assign_tutor_to_all_subjects(self):
        """Verifies Admin can assign a single tutor to all subjects under a course in 1 click."""
        self.client.force_login(self.admin_user)

        res = self.client.post('/courses/admin/faculty-assignments/bulk-assign/', {
            'course_id': self.robotics_course.id,
            'tutor_id': self.tutor_python.id,
        })
        self.assertEqual(res.status_code, 302)

        # Refresh all subjects
        self.subj_python.refresh_from_db()
        self.subj_cpp.refresh_from_db()
        self.subj_electronics.refresh_from_db()

        self.assertEqual(self.subj_python.instructor, self.tutor_python)
        self.assertEqual(self.subj_cpp.instructor, self.tutor_python)
        self.assertEqual(self.subj_electronics.instructor, self.tutor_python)

    def test_specialist_subject_matrix_assignment(self):
        """Verifies Admin can assign different specialist tutors to different subjects."""
        self.client.force_login(self.admin_user)

        res = self.client.post(f'/courses/admin/faculty-assignments/?course_id={self.robotics_course.id}', {
            'action': 'save_matrix',
            f'tutor_subj_{self.subj_python.id}': self.tutor_python.id,
            f'tutor_subj_{self.subj_electronics.id}': self.tutor_electronics.id,
            f'tutor_subj_{self.subj_cpp.id}': '',
        })
        self.assertEqual(res.status_code, 302)

        self.subj_python.refresh_from_db()
        self.subj_electronics.refresh_from_db()
        self.subj_cpp.refresh_from_db()

        self.assertEqual(self.subj_python.instructor, self.tutor_python)
        self.assertEqual(self.subj_electronics.instructor, self.tutor_electronics)
        self.assertIsNone(self.subj_cpp.instructor)

    def test_cohort_specific_tutor_override(self):
        """Verifies assigning a tutor for a specific batch/cohort using BatchSubjectTutor."""
        self.client.force_login(self.admin_user)

        # Assign tutor_electronics specifically to Python for Batch A
        res = self.client.post(f'/courses/admin/faculty-assignments/?course_id={self.robotics_course.id}&batch_id={self.batch_a.id}', {
            'action': 'save_matrix',
            f'tutor_subj_{self.subj_python.id}': self.tutor_electronics.id,
        })
        self.assertEqual(res.status_code, 302)

        # Default subject instructor should still be tutor_python, but for batch_a it resolves to tutor_electronics
        self.subj_python.instructor = self.tutor_python
        self.subj_python.save()

        # Batch-specific check
        self.assertEqual(self.subj_python.get_tutor_for_batch(self.batch_a), self.tutor_electronics)
        self.assertEqual(self.subj_python.get_tutor_for_batch(None), self.tutor_python)

    def test_targeted_assignment_dispatch_to_enrolled_students(self):
        """Verifies that an assignment for Electronics & Sensors is only seen by student_full, not student_python_only."""
        assign_electronics = Assignment.objects.create(
            subject=self.subj_electronics,
            batch=self.batch_a,
            week_number=1,
            title="Sensor Interfacing Lab",
            due_date=date.today() + timedelta(days=7),
            max_score=100,
            created_by=self.tutor_electronics
        )

        assign_python = Assignment.objects.create(
            subject=self.subj_python,
            batch=self.batch_a,
            week_number=1,
            title="Python Functions Lab",
            due_date=date.today() + timedelta(days=7),
            max_score=100,
            created_by=self.tutor_python
        )

        # 1. Student enrolled in all subjects sees both assignments
        self.client.login(username='student_full', password='password123')
        res_all = self.client.get('/courses/student/gradebook/')
        self.assertEqual(res_all.status_code, 200)
        self.assertEqual(res_all.context['total_assignments'], 2)

        # 2. Student enrolled only in Python only sees Python assignment
        self.client.login(username='student_python_only', password='password123')
        res_spec = self.client.get('/courses/student/gradebook/')
        self.assertEqual(res_spec.status_code, 200)
        self.assertEqual(res_spec.context['total_assignments'], 1)
        self.assertEqual(res_spec.context['weeks_dict'][1][0].title, "Python Functions Lab")
