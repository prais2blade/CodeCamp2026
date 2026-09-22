import os
import sqlite3
import tempfile
from django.test import TestCase
from django.core.management import call_command
from django.contrib.auth import get_user_model

from apps.tenants.models import Tenant
from apps.accounts.models import Profile, Attendance
from apps.courses.models import Course
from apps.scheduling.models import Batch

User = get_user_model()


class LiveSummerCohortImporterTests(TestCase):
    def setUp(self):
        # Create target tenant
        self.tenant = Tenant.objects.create(
            name="Alpha Academy",
            slug="alpha-campus",
            subdomain="alpha",
            subscription_tier="pro",
            max_students=500,
            is_default=True,
        )

        # Create temporary SQLite databases mimicking CodeCamp and Attendance-System
        self.temp_dir = tempfile.TemporaryDirectory()
        self.codecamp_db_path = os.path.join(self.temp_dir.name, "codecamp.sqlite3")
        self.attendance_db_path = os.path.join(self.temp_dir.name, "attendance.sqlite3")

        # Setup mock CodeCamp schema & sample data
        conn_cc = sqlite3.connect(self.codecamp_db_path)
        cur_cc = conn_cc.cursor()
        cur_cc.execute("""
            CREATE TABLE teencamp_batch (
                id INTEGER PRIMARY KEY,
                name TEXT,
                code TEXT,
                mode TEXT,
                capacity INTEGER,
                start_date TEXT,
                end_date TEXT
            )
        """)
        cur_cc.execute("""
            INSERT INTO teencamp_batch (id, name, code, mode, capacity, start_date, end_date)
            VALUES (1, 'Robotics Pioneer', 'ROB-01', 'PHYSICAL', 25, '2026-07-01', '2026-08-15')
        """)
        cur_cc.execute("""
            CREATE TABLE teencamp_codingcampregistration (
                id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                parent_email TEXT,
                parent_phone TEXT,
                reg_code TEXT,
                reference TEXT,
                attendance_student_id TEXT,
                batch_id INTEGER
            )
        """)
        cur_cc.execute("""
            INSERT INTO teencamp_codingcampregistration 
            (id, first_name, last_name, parent_email, parent_phone, reg_code, reference, attendance_student_id, batch_id)
            VALUES (1, 'Tunde', 'Adeyemi', 'tunde.parent@test.com', '+234800111222', 'REG-1001', 'REF-1001', 'STU-001', 1)
        """)
        conn_cc.commit()
        conn_cc.close()

        # Setup mock Attendance-System schema & sample data
        conn_att = sqlite3.connect(self.attendance_db_path)
        cur_att = conn_att.cursor()
        cur_att.execute("""
            CREATE TABLE students_student (
                id INTEGER PRIMARY KEY,
                student_id TEXT,
                integration_key TEXT,
                first_name TEXT,
                last_name TEXT
            )
        """)
        cur_att.execute("""
            INSERT INTO students_student (id, student_id, integration_key, first_name, last_name)
            VALUES (1, 'STU-001', 'REG-1001', 'Tunde', 'Adeyemi')
        """)
        cur_att.execute("""
            CREATE TABLE attendance_attendance (
                id INTEGER PRIMARY KEY,
                student_id INTEGER,
                date TEXT,
                check_in TEXT,
                check_out TEXT
            )
        """)
        cur_att.execute("""
            INSERT INTO attendance_attendance (id, student_id, date, check_in, check_out)
            VALUES (1, 1, '2026-07-15', '2026-07-15T09:05:00Z', '2026-07-15T15:30:00Z')
        """)
        conn_att.commit()
        conn_att.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dry_run_does_not_commit_records(self):
        call_command(
            "import_live_summer_cohort",
            tenant_slug="alpha-campus",
            codecamp_db=self.codecamp_db_path,
            attendance_db=self.attendance_db_path,
            dry_run=True,
        )
        self.assertFalse(User.objects.filter(email="tunde.parent@test.com").exists())
        self.assertFalse(Attendance.objects.filter(external_reference="kiosk_scan_1").exists())

    def test_live_import_creates_batches_students_and_scans(self):
        call_command(
            "import_live_summer_cohort",
            tenant_slug="alpha-campus",
            codecamp_db=self.codecamp_db_path,
            attendance_db=self.attendance_db_path,
        )

        # 1. Verify User & Profile
        user = User.objects.filter(email="tunde.parent@test.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.first_name, "Tunde")
        self.assertEqual(user.last_name, "Adeyemi")

        profile = user.profile
        self.assertEqual(profile.tenant, self.tenant)
        self.assertEqual(profile.role, "student")
        self.assertEqual(profile.external_attendance_id, "STU-001")
        self.assertTrue(profile.is_verified)
        self.assertTrue(profile.is_approved)

        # 2. Verify Batch
        batch = Batch.objects.filter(tenant=self.tenant, name__icontains="Robotics Pioneer").first()
        self.assertIsNotNone(batch)
        self.assertEqual(profile.batch, batch)

        # 3. Verify Attendance Record
        attendance_record = Attendance.objects.filter(
            tenant=self.tenant,
            student=user,
            external_reference="kiosk_scan_1",
        ).first()
        self.assertIsNotNone(attendance_record)
        self.assertEqual(str(attendance_record.date), "2026-07-15")
        self.assertEqual(attendance_record.status, "Present")
        self.assertEqual(attendance_record.source, "summer_kiosk_import")
