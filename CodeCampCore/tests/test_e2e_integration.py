import json
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.utils import timezone
from django.conf import settings

from apps.accounts.models import Profile, Attendance
from apps.courses.models import Course, Subject
from apps.scheduling.models import Batch


class E2EIntegrationAndProgressionTest(TestCase):
    """
    Simulates the end-to-end multi-system integration lifecycle:
    1. Student registers via Codecamp -> Ingested into CodeCampCore.
    2. Student scans QR at kiosk via attendance-system -> Check-in/out synced to CodeCampCore.
    3. Student completes 6-week summer camp -> Registers for 6-Month Diploma course in CodeCampCore.
    """

    def setUp(self):
        self.client = Client()
        self.api_key = getattr(settings, "CORE_API_KEY", "test_core_api_key_123")
        # Ensure test settings have the key
        settings.CORE_API_KEY = self.api_key
        settings.REGISTRATION_API_KEY = self.api_key
        settings.ATTENDANCE_API_KEY = self.api_key

    def test_complete_student_lifecycle_simulation(self):
        # =========================================================================
        # STEP 1: Codecamp Summer Camp Admissions Sync
        # =========================================================================
        camp_payload = {
            "registration_code": "TC-2026-0088",
            "first_name": "Toluwa",
            "last_name": "Praise",
            "email": "sarah.praise@example.com",
            "phone": "+2348011223344",
            "course_name": "Teen CodeCamp",
            "batch_name": "Summer Camp Cohort 1",
            "external_attendance_id": "STU-88001",
            "parent": {
                "name": "Sarah Praise",
                "phone": "+2348011223344",
                "whatsapp": "+2348011223344",
                "email": "sarah.praise@example.com",
                "relationship": "Mother",
            },
            "payment": {
                "amount_paid": 30000.0,
                "status": "paid",
                "reference": "REF-CC-88001",
            },
        }

        enroll_response = self.client.post(
            "/api/v1/enrollment/sync/",
            data=json.dumps(camp_payload),
            content_type="application/json",
            HTTP_X_API_KEY=self.api_key,
        )

        self.assertIn(enroll_response.status_code, [200, 201])
        res_data = enroll_response.json()
        self.assertTrue(res_data.get("success"))

        # Verify User and Profile created in CodeCampCore
        user = User.objects.get(id=res_data["user_id"])
        self.assertEqual(user.first_name, "Toluwa")
        self.assertEqual(user.last_name, "Praise")
        self.assertEqual(user.profile.external_attendance_id, "STU-88001")
        self.assertEqual(user.profile.course.name, "Teen CodeCamp")
        self.assertEqual(user.profile.batch.name, "Summer Camp Cohort 1")
        self.assertTrue(user.profile.has_paid)

        # =========================================================================
        # STEP 2: attendance-system QR Kiosk Scan Sync
        # =========================================================================
        today_str = timezone.localdate().isoformat()
        attendance_payload = {
            "records": [
                {
                    "external_student_id": "STU-88001",
                    "student_username": user.username,
                    "date": today_str,
                    "status": "Present",
                    "check_in": "08:30:00",
                    "check_out": "13:45:00",
                    "source": "kiosk_qr_scanner",
                    "external_reference": "ATT-9901",
                }
            ]
        }

        att_response = self.client.post(
            "/api/v1/attendance/sync/",
            data=json.dumps(attendance_payload),
            content_type="application/json",
            HTTP_X_API_KEY=self.api_key,
        )

        self.assertEqual(att_response.status_code, 200)
        att_data = att_response.json()
        self.assertTrue(att_data.get("success"))
        self.assertEqual(att_data.get("synced_count"), 1)

        # Verify attendance record in CodeCampCore
        attendance_record = Attendance.objects.filter(student=user).first()
        self.assertIsNotNone(attendance_record)
        self.assertEqual(attendance_record.status, "Present")
        self.assertEqual(str(attendance_record.check_in_time), "08:30:00")
        self.assertEqual(str(attendance_record.check_out_time), "13:45:00")

        # =========================================================================
        # STEP 3: Post-Camp Progression to 6-Month Full Academy Diploma Course
        # =========================================================================
        diploma_payload = {
            "registration_code": "DIP-2026-0042",
            "first_name": "Toluwa",
            "last_name": "Praise",
            "email": "sarah.praise@example.com",
            "phone": "+2348011223344",
            "course_name": "Full Stack Web Engineering - 6 Months",
            "batch_name": "Diploma Fall 2026 Batch",
            "external_attendance_id": "STU-88001",
            "parent": {
                "name": "Sarah Praise",
                "phone": "+2348011223344",
                "email": "sarah.praise@example.com",
            },
            "payment": {
                "amount_paid": 150000.0,
                "status": "paid",
                "reference": "REF-DIP-42001",
            },
        }

        diploma_response = self.client.post(
            "/api/v1/enrollment/sync/",
            data=json.dumps(diploma_payload),
            content_type="application/json",
            HTTP_X_API_KEY=self.api_key,
        )

        self.assertIn(diploma_response.status_code, [200, 201])
        dip_res_data = diploma_response.json()
        self.assertTrue(dip_res_data.get("success"))

        # User profile should now be updated to the new Diploma course while preserving user ID
        user.refresh_from_db()
        self.assertEqual(user.id, res_data["user_id"])  # Same user
        self.assertEqual(user.profile.course.name, "Full Stack Web Engineering - 6 Months")
        self.assertEqual(user.profile.batch.name, "Diploma Fall 2026 Batch")

        # Historical attendance records from Summer Camp remain intact
        historical_attendance = Attendance.objects.filter(student=user).count()
        self.assertEqual(historical_attendance, 1)
