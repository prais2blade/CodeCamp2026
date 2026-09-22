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
    help = "Transfer students from the Attendance Kiosk system into the CodeCampCore Main Portal with temporary passwords."

    def add_arguments(self, parser):
        parser.add_argument(
            "--attendance-db",
            type=str,
            default=None,
            help="Path to attendance system SQLite database (auto-detected if omitted)",
        )
        parser.add_argument(
            "--temp-password",
            type=str,
            default="CodeCamp@2026",
            help="Default temporary password for imported students (default: CodeCamp@2026)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the transfer without saving changes",
        )

    def handle(self, *args, **options):
        custom_db_path = options.get("attendance_db")
        temp_password = options.get("temp_password", "CodeCamp@2026")
        dry_run = options.get("dry_run", False)

        # 1. Resolve DB Path
        candidate_paths = [
            custom_db_path,
            "/var/www/codecamp2026/attendance-system/backend/db.sqlite3",
            r"c:\Projects\attendance-system\backend\db.sqlite3",
            "attendance-system/backend/db.sqlite3",
            "../attendance-system/backend/db.sqlite3",
        ]
        db_path = None
        for path in candidate_paths:
            if path and os.path.exists(path):
                db_path = os.path.abspath(path)
                break

        if not db_path:
            self.stderr.write(self.style.ERROR(
                "❌ Could not find Attendance DB! Please provide path via --attendance-db <path>"
            ))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== Transferring Attendance Students to Main Portal ({'DRY RUN' if dry_run else 'LIVE TRANSACTION'}) ==="
        ))
        self.stdout.write(self.style.SUCCESS(f"Connected to Attendance DB: {db_path}"))
        self.stdout.write(f"Temporary Password for all transferred students: {temp_password}\n")

        # 2. Resolve Academy Tenant
        tenant = Tenant.objects.filter(is_default=True).first() or Tenant.objects.first()

        # 3. Resolve Courses & Batches for Mapping
        default_course = Course.objects.filter(is_published=True).first()
        python_course = Course.objects.filter(name__icontains="python").first() or default_course
        web_course = Course.objects.filter(name__icontains="web").first() or default_course
        innovators_course = Course.objects.filter(name__icontains="innovator").first() or default_course

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Fetch students with parent info
        query = """
            SELECT 
                s.id as student_row_id,
                s.student_id,
                s.first_name,
                s.last_name,
                s.class_name,
                s.teaching_class_id,
                tc.name as teaching_class_name,
                s.gender,
                s.is_active,
                p.full_name as parent_name,
                p.phone_number as parent_phone,
                p.email as parent_email
            FROM students_student s
            LEFT JOIN students_teachingclass tc ON s.teaching_class_id = tc.id
            LEFT JOIN students_studentparent sp ON s.id = sp.student_id
            LEFT JOIN students_parent p ON sp.parent_id = p.id
            ORDER BY s.id ASC
        """
        cur.execute(query)
        students_rows = cur.fetchall()

        stats = {
            "transferred": 0,
            "updated": 0,
            "attendance_records": 0,
            "regular_students": 0,
            "summer_students": 0,
        }

        transferred_roster = []

        try:
            with transaction.atomic():
                for row in students_rows:
                    student_id = (row["student_id"] or "").strip()
                    first_name = (row["first_name"] or "").strip()
                    last_name = (row["last_name"] or "").strip()
                    class_name = (row["class_name"] or "").strip()
                    teaching_class = (row["teaching_class_name"] or "").strip()
                    parent_email = (row["parent_email"] or "").strip().lower()
                    phone = (row["parent_phone"] or "").strip()

                    # Fallback names
                    if not first_name and not last_name:
                        first_name = "Student"
                        last_name = student_id

                    # Determine effective class name
                    effective_class = (teaching_class or class_name).strip().lower()

                    # Categorize student: Regular Innovation Hub Track vs Summer Camp
                    is_summer = "summer" in effective_class or "teen" in effective_class
                    if is_summer:
                        student_type = "Summer"
                        stats["summer_students"] += 1
                        target_course = Course.objects.filter(name__icontains="summer").first() or default_course
                    else:
                        student_type = "Regular"
                        stats["regular_students"] += 1
                        target_course = None
                        if "python" in effective_class or "programing advance" in effective_class:
                            target_course = Course.objects.filter(name__icontains="python").first()
                        elif "data" in effective_class or "analysis" in effective_class:
                            target_course = Course.objects.filter(name__icontains="data").first()
                        elif "robot" in effective_class or "automation" in effective_class:
                            target_course = Course.objects.filter(name__icontains="robotics").first()
                        elif "innovator" in effective_class or "young" in effective_class or "beginner" in effective_class:
                            target_course = Course.objects.filter(name__icontains="innovator").first()
                        elif "cloud" in effective_class or "devops" in effective_class:
                            target_course = Course.objects.filter(name__icontains="cloud").first()
                        elif "cyber" in effective_class or "security" in effective_class or "ethical" in effective_class:
                            target_course = Course.objects.filter(name__icontains="cyber").first()
                        elif "web" in effective_class or "batch a" in effective_class or "batch b" in effective_class:
                            target_course = Course.objects.filter(name__icontains="web").first()
                        elif "advance" in effective_class:
                            target_course = Course.objects.filter(name__icontains="python").first()

                        if not target_course:
                            target_course = default_course

                    target_batch = None
                    if target_course:
                        target_batch = Batch.objects.filter(course=target_course, is_published=True).first()

                    # Determine username
                    clean_first = slugify(first_name).replace("-", "")
                    clean_last = slugify(last_name).replace("-", "")
                    if clean_first and clean_last:
                        username_candidate = f"{clean_first}.{clean_last}"
                    elif clean_first:
                        username_candidate = clean_first
                    else:
                        username_candidate = slugify(student_id).replace("-", "")

                    # Determine email
                    email = parent_email
                    if not email:
                        clean_sid = student_id.lower().replace("-", "")
                        email = f"{clean_sid}@student.codecamp.com.ng"

                    # Check if user already exists by external_attendance_id
                    existing_profile = Profile.objects.filter(external_attendance_id__iexact=student_id).first()
                    user = None

                    if existing_profile:
                        user = existing_profile.user
                        user.first_name = first_name
                        user.last_name = last_name
                        user.set_password(temp_password)
                        user.save()
                        stats["updated"] += 1
                    else:
                        clean_sid = student_id.lower().replace("-", "")
                        # If email is empty or already in use by a sibling/parent account, ensure unique student portal email
                        final_email = parent_email
                        if not final_email or User.objects.filter(email__iexact=final_email).exists():
                            final_email = f"{clean_sid}@student.codecamp.com.ng"

                        # Ensure username uniqueness
                        unique_username = username_candidate
                        counter = 1
                        while User.objects.filter(username__iexact=unique_username).exists():
                            unique_username = f"{username_candidate}{counter}"
                            counter += 1

                        user = User.objects.create_user(
                            username=unique_username,
                            email=final_email,
                            password=temp_password,
                            first_name=first_name,
                            last_name=last_name,
                        )
                        stats["transferred"] += 1

                    # Create or update profile
                    profile, _ = Profile.objects.get_or_create(user=user)
                    profile.role = "student"
                    profile.external_attendance_id = student_id
                    profile.phone = phone or profile.phone
                    profile.tenant = tenant
                    profile.course = target_course
                    profile.batch = target_batch
                    profile.is_verified = True  # Immediately allowed to login
                    profile.onboarding_stage = "finished"  # Direct to dashboard
                    profile.save()

                    transferred_roster.append({
                        "name": f"{first_name} {last_name}",
                        "type": student_type,
                        "student_id": student_id,
                        "username": user.username,
                        "email": user.email,
                        "course": target_course.name if target_course else "General",
                        "password": temp_password,
                    })

                    # 4. Import student's attendance records from attendance_attendance
                    try:
                        cur.execute(
                            "SELECT date, check_in, check_out FROM attendance_attendance WHERE student_id = ?",
                            (row["student_row_id"],)
                        )
                        att_rows = cur.fetchall()

                        default_subject = None
                        if target_course:
                            default_subject = Subject.objects.filter(course=target_course).first()

                        for att in att_rows:
                            att_date_str = att["date"]
                            if att_date_str:
                                try:
                                    att_date = datetime.date.fromisoformat(att_date_str)
                                except Exception:
                                    att_date = timezone.localdate()

                                if default_subject:
                                    _, att_created = Attendance.objects.get_or_create(
                                        student=user,
                                        subject=default_subject,
                                        date=att_date,
                                        defaults={
                                            "tenant": tenant,
                                            "batch": target_batch,
                                            "status": "Present",
                                            "marked_by": user,
                                        }
                                    )
                                    if att_created:
                                        stats["attendance_records"] += 1
                    except Exception as e:
                        pass

                if dry_run:
                    transaction.set_rollback(True)
                    self.stdout.write(self.style.WARNING("\n[DRY RUN] Rolled back all changes without saving."))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error during transfer: {e}"))
            raise

        conn.close()

        # Print Summary Table
        self.stdout.write("\n" + "=" * 115)
        self.stdout.write(self.style.SUCCESS("[OK] ATTENDANCE STUDENTS TRANSFER COMPLETE"))
        self.stdout.write("=" * 115)
        self.stdout.write(f"{'Student Name':<22} | {'Type':<8} | {'Student ID':<13} | {'Username':<20} | {'Course':<24} | {'Temp Password'}")
        self.stdout.write("-" * 115)
        for s in transferred_roster:
            course_short = (s['course'][:22] + '..') if len(s['course']) > 24 else s['course']
            self.stdout.write(f"{s['name']:<22} | {s['type']:<8} | {s['student_id']:<13} | {s['username']:<20} | {course_short:<24} | {s['password']}")
        self.stdout.write("=" * 115)
        self.stdout.write(f"Total: {stats['transferred']} new, {stats['updated']} updated (Regular: {stats['regular_students']}, Summer: {stats['summer_students']})")
        self.stdout.write(f"Attendance Records Synced: {stats['attendance_records']}")
        self.stdout.write(f"Students can log in with: Student ID, Username, or Email using temporary password '{temp_password}'\n")
