import os
import sqlite3
import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify
from django.utils import timezone

from apps.tenants.models import Tenant
from apps.accounts.models import Profile, Attendance
from apps.courses.models import Course, Subject
from apps.scheduling.models import Batch

User = get_user_model()


class Command(BaseCommand):
    help = "Import live 6-week summer cohort data and attendance logs into CodeCampCore Academy Management Portal"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-slug",
            type=str,
            default="lagos-hq",
            help="Tenant slug to associate the imported summer data with (defaults to lagos-hq)",
        )
        parser.add_argument(
            "--codecamp-db",
            type=str,
            default=r"c:\Projects\codecamp\camp\db.sqlite3",
            help="Path to the SQLite database of the CodeCamp Summer Registration system",
        )
        parser.add_argument(
            "--attendance-db",
            type=str,
            default=r"c:\Projects\attendance-system\backend\db.sqlite3",
            help="Path to the SQLite database of the Attendance Kiosk system",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the import without saving any changes to the database",
        )

    def handle(self, *args, **options):
        tenant_slug = options["tenant_slug"]
        codecamp_db_path = options["codecamp_db"]
        attendance_db_path = options["attendance_db"]
        dry_run = options["dry_run"]

        self.stdout.write(self.style.MIGRATE_HEADING(f"=== Starting Live Summer Cohort Import ({'DRY RUN' if dry_run else 'LIVE TRANSACTION'}) ==="))

        # 1. Resolve Tenant
        tenant = Tenant.objects.filter(slug=tenant_slug).first()
        if not tenant:
            tenant = Tenant.objects.filter(is_default=True).first()
        if not tenant:
            tenant = Tenant.objects.create(
                name="CodeCamp Global Tech Academy",
                slug="lagos-hq",
                subdomain="lagos",
                subscription_tier="enterprise",
                max_students=2000,
                is_default=True,
            )
            self.stdout.write(self.style.SUCCESS(f"[TENANT] Created initial tenant: {tenant.name} ({tenant.slug})"))
        else:
            self.stdout.write(self.style.SUCCESS(f"[TENANT] Using target tenant: {tenant.name} ({tenant.slug})"))

        # 2. Ensure Main Summer Course Exists
        summer_course, created = Course.objects.get_or_create(
            tenant=tenant,
            name="Summer Coding & Robotics Camp (6 Weeks)",
            defaults={
                "slug": "summer-coding-robotics-camp-6-weeks",
                "short_description": "Foundational 6-week summer program in Web Development, Python, and Creative Technology.",
                "duration_weeks": 6,
                "fee": 30000.00,
                "is_published": True,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"[COURSE] Created course: {summer_course.name}"))

        default_subject, _ = Subject.objects.get_or_create(
            course=summer_course,
            name="General Coding & STEM Lab",
            defaults={"description": "Core summer curriculum and practical lab exercises."},
        )

        stats = {
            "batches_created": 0,
            "batches_existing": 0,
            "students_created": 0,
            "students_updated": 0,
            "attendance_imported": 0,
            "attendance_skipped": 0,
        }

        # 3. Connect to SQLite Databases
        codecamp_conn = None
        attendance_conn = None

        if os.path.exists(codecamp_db_path):
            codecamp_conn = sqlite3.connect(codecamp_db_path)
            codecamp_conn.row_factory = sqlite3.Row
            self.stdout.write(self.style.SUCCESS(f"[DATABASE] Connected to CodeCamp DB: {codecamp_db_path}"))
        else:
            self.stdout.write(self.style.WARNING(f"[DATABASE] CodeCamp DB not found at: {codecamp_db_path} (skipping registration sync)"))

        if os.path.exists(attendance_db_path):
            attendance_conn = sqlite3.connect(attendance_db_path)
            attendance_conn.row_factory = sqlite3.Row
            self.stdout.write(self.style.SUCCESS(f"[DATABASE] Connected to Attendance DB: {attendance_db_path}"))
        else:
            self.stdout.write(self.style.WARNING(f"[DATABASE] Attendance DB not found at: {attendance_db_path} (skipping kiosk scan sync)"))

        batch_mapping = {}  # external batch id/code -> Core Batch model instance
        student_id_user_map = {}  # external student id -> Core User model instance

        try:
            with transaction.atomic():
                # 4. Import Batches from CodeCamp
                if codecamp_conn:
                    cursor = codecamp_conn.cursor()
                    try:
                        cursor.execute("SELECT * FROM teencamp_batch")
                        batches = cursor.fetchall()
                        for b in batches:
                            batch_name = b["name"]
                            batch_mode = "online" if (b["mode"] or "").upper() == "VIRTUAL" else "onsite"
                            start_date = b["start_date"] or timezone.localdate().isoformat()
                            end_date = b["end_date"] or (timezone.localdate() + datetime.timedelta(days=42)).isoformat()
                            capacity = b["capacity"] or 30

                            core_batch, b_created = Batch.objects.get_or_create(
                                tenant=tenant,
                                course=summer_course,
                                name=f"Summer Camp - {batch_name}",
                                defaults={
                                    "mode": batch_mode,
                                    "batch_type": "weekdays",
                                    "session_period": "morning",
                                    "days_pattern": "mon_wed_fri",
                                    "start_date": start_date,
                                    "end_date": end_date,
                                    "duration_weeks": 6,
                                    "max_students": capacity,
                                    "is_published": True,
                                },
                            )
                            batch_mapping[b["id"]] = core_batch
                            batch_mapping[b["code"]] = core_batch
                            if b_created:
                                stats["batches_created"] += 1
                            else:
                                stats["batches_existing"] += 1
                    except sqlite3.OperationalError as e:
                        self.stdout.write(self.style.WARNING(f"[BATCH] Could not read teencamp_batch: {e}"))

                # Fallback default batch if none existed in source
                if not batch_mapping:
                    default_batch, _ = Batch.objects.get_or_create(
                        tenant=tenant,
                        course=summer_course,
                        name="Summer Camp 2026 - Main Cohort",
                        defaults={
                            "mode": "onsite",
                            "batch_type": "weekdays",
                            "session_period": "morning",
                            "days_pattern": "mon_wed_fri",
                            "start_date": timezone.localdate(),
                            "end_date": timezone.localdate() + datetime.timedelta(days=42),
                            "duration_weeks": 6,
                            "max_students": 100,
                            "is_published": True,
                        },
                    )
                    batch_mapping["default"] = default_batch

                # 5. Import Students from CodeCamp Registrations
                if codecamp_conn:
                    cursor = codecamp_conn.cursor()
                    try:
                        cursor.execute("SELECT * FROM teencamp_codingcampregistration")
                        registrations = cursor.fetchall()
                        for reg in registrations:
                            first_name = reg["first_name"].strip() if reg["first_name"] else "Student"
                            last_name = reg["last_name"].strip() if reg["last_name"] else ""
                            parent_email = (reg["parent_email"] or "").strip().lower()
                            parent_phone = reg["parent_phone"] or ""
                            reg_code = reg["reg_code"] or reg["reference"] or f"SUMMER-{reg['id']}"
                            attendance_id = reg["attendance_student_id"] or ""

                            # Derive unique username
                            base_username = slugify(f"{first_name}_{last_name}") or f"student_{reg['id']}"
                            username = base_username.replace("-", "_")

                            user = User.objects.filter(email=parent_email).first() if parent_email else None
                            if not user:
                                user = User.objects.filter(username=username).first()

                            assigned_batch = batch_mapping.get(reg["batch_id"]) or list(batch_mapping.values())[0]

                            if not user:
                                user = User.objects.create_user(
                                    username=username,
                                    email=parent_email or f"{username}@summer.codecamp.org",
                                    first_name=first_name,
                                    last_name=last_name,
                                    password="SummerCampStudent2026!",
                                )
                                stats["students_created"] += 1
                            else:
                                stats["students_updated"] += 1

                            # Update Profile
                            profile, _ = Profile.objects.get_or_create(user=user)
                            profile.tenant = tenant
                            profile.role = "student"
                            profile.phone = parent_phone
                            profile.batch = assigned_batch
                            if attendance_id:
                                profile.external_attendance_id = attendance_id
                            profile.is_verified = True
                            profile.is_approved = True
                            profile.onboarding_stage = "finished"
                            profile.save()

                            if attendance_id:
                                student_id_user_map[attendance_id] = user
                            student_id_user_map[reg_code] = user
                            student_id_user_map[user.username] = user
                    except sqlite3.OperationalError as e:
                        self.stdout.write(self.style.WARNING(f"[STUDENTS] Could not read teencamp_codingcampregistration: {e}"))

                # 6. Cross-reference Attendance System Students (Summer + Direct Regular Academy Students)
                if attendance_conn:
                    cursor = attendance_conn.cursor()
                    try:
                        # Fetch teaching classes from attendance-system
                        teaching_classes_map = {}
                        try:
                            cursor.execute("SELECT id, name FROM students_teachingclass")
                            for tc in cursor.fetchall():
                                teaching_classes_map[tc["id"]] = tc["name"]
                        except Exception:
                            pass

                        cursor.execute("SELECT * FROM students_student")
                        att_students = cursor.fetchall()
                        for ast in att_students:
                            ext_id = ast["student_id"]
                            first_name = (ast["first_name"] or "").strip()
                            last_name = (ast["last_name"] or "").strip()
                            integration_key = ast["integration_key"]
                            class_name = (ast["class_name"] or "").strip() if "class_name" in ast.keys() else ""
                            teaching_class_id = ast["teaching_class_id"] if "teaching_class_id" in ast.keys() else None
                            
                            program_title = class_name or teaching_classes_map.get(teaching_class_id) or "General Academy Track"

                            user = student_id_user_map.get(ext_id) or student_id_user_map.get(integration_key)
                            if not user:
                                username = slugify(f"{first_name}_{last_name}_{ext_id}").replace("-", "_")
                                user = User.objects.filter(username=username).first()
                                if not user:
                                    user = User.objects.create_user(
                                        username=username,
                                        email=f"{username}@academy.codecamp.org",
                                        first_name=first_name or "Student",
                                        last_name=last_name,
                                        password="AcademyStudent2026!",
                                    )
                                    stats["students_created"] += 1

                                # Differentiate Summer vs Direct Long-Term Course
                                if integration_key:
                                    assigned_batch = list(batch_mapping.values())[0]
                                else:
                                    # Create / Link Dedicated Academy Program for Direct Students
                                    direct_course, _ = Course.objects.get_or_create(
                                        tenant=tenant,
                                        name=f"{program_title} Program",
                                        defaults={
                                            "slug": slugify(f"{program_title}-program"),
                                            "short_description": f"Comprehensive direct enrollment program for {program_title}.",
                                            "duration_weeks": 24,
                                            "fee": 150000.00,
                                            "is_published": True,
                                        },
                                    )
                                    direct_subject, _ = Subject.objects.get_or_create(
                                        course=direct_course,
                                        name=f"{program_title} Core Curriculum",
                                        defaults={"description": f"Direct curriculum for {program_title}."},
                                    )
                                    assigned_batch, b_created = Batch.objects.get_or_create(
                                        tenant=tenant,
                                        course=direct_course,
                                        name=f"{program_title} - Cohort 1",
                                        defaults={
                                            "mode": "onsite",
                                            "batch_type": "weekdays",
                                            "session_period": "morning",
                                            "days_pattern": "mon_wed_fri",
                                            "start_date": timezone.localdate(),
                                            "end_date": timezone.localdate() + datetime.timedelta(days=168),
                                            "duration_weeks": 24,
                                            "max_students": 50,
                                            "is_published": True,
                                        },
                                    )
                                    if b_created:
                                        stats["batches_created"] += 1

                                profile, _ = Profile.objects.get_or_create(user=user)
                                profile.tenant = tenant
                                profile.role = "student"
                                profile.external_attendance_id = ext_id
                                profile.batch = assigned_batch
                                profile.is_verified = True
                                profile.is_approved = True
                                profile.onboarding_stage = "finished"
                                profile.save()

                            student_id_user_map[ext_id] = user

                        # 7. Import Timestamped Attendance Scans
                        cursor.execute("SELECT * FROM attendance_attendance")
                        scans = cursor.fetchall()
                        for scan in scans:
                            student_raw_id = scan["student_id"]
                            # Lookup student_id in attendance_system
                            cursor.execute("SELECT student_id FROM students_student WHERE id = ?", (student_raw_id,))
                            row = cursor.fetchone()
                            if row:
                                student_code = row["student_id"]
                                matched_user = student_id_user_map.get(student_code)
                                if matched_user:
                                    att_date = scan["date"]
                                    check_in_raw = scan["check_in"]
                                    check_out_raw = scan["check_out"]

                                    check_in_time = None
                                    if check_in_raw:
                                        try:
                                            dt = datetime.datetime.fromisoformat(check_in_raw.replace("Z", "+00:00"))
                                            check_in_time = dt.time()
                                        except Exception:
                                            pass

                                    check_out_time = None
                                    if check_out_raw:
                                        try:
                                            dt = datetime.datetime.fromisoformat(check_out_raw.replace("Z", "+00:00"))
                                            check_out_time = dt.time()
                                        except Exception:
                                            pass

                                    target_batch = matched_user.profile.batch or list(batch_mapping.values())[0]
                                    target_subject = target_batch.course.subjects.first() if target_batch.course.subjects.exists() else default_subject

                                    attendance_obj, a_created = Attendance.objects.get_or_create(
                                        tenant=tenant,
                                        student=matched_user,
                                        subject=target_subject,
                                        date=att_date,
                                        defaults={
                                            "batch": target_batch,
                                            "status": "Present",
                                            "check_in_time": check_in_time,
                                            "check_out_time": check_out_time,
                                            "source": "summer_kiosk_import",
                                            "external_reference": f"kiosk_scan_{scan['id']}",
                                        },
                                    )
                                    if a_created:
                                        stats["attendance_imported"] += 1
                                    else:
                                        stats["attendance_skipped"] += 1
                    except sqlite3.OperationalError as e:
                        self.stdout.write(self.style.WARNING(f"[ATTENDANCE] Could not read attendance logs: {e}"))

                if dry_run:
                    self.stdout.write(self.style.NOTICE("\n[DRY RUN] Rolling back all imported changes."))
                    transaction.set_rollback(True)

        finally:
            if codecamp_conn:
                codecamp_conn.close()
            if attendance_conn:
                attendance_conn.close()

        # 8. Print Results
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 50))
        self.stdout.write(self.style.SUCCESS(f"SUMMER COHORT IMPORT SUMMARY: {tenant.name}"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(f" - Batches Created:     {stats['batches_created']}")
        self.stdout.write(f" - Batches Linked:      {stats['batches_existing']}")
        self.stdout.write(f" - Students Created:    {stats['students_created']}")
        self.stdout.write(f" - Students Updated:    {stats['students_updated']}")
        self.stdout.write(f" - Attendance Imported: {stats['attendance_imported']}")
        self.stdout.write(f" - Attendance Skipped:  {stats['attendance_skipped']}")
        self.stdout.write(self.style.SUCCESS("=" * 50 + "\n"))
