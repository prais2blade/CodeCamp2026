import os
import re
import glob
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
    help = "Transfer student records from Attendance DB (SQLite or PostgreSQL) to CodeCampCore main portal"

    def add_arguments(self, parser):
        parser.add_argument(
            "--attendance-db",
            type=str,
            default=None,
            help="Path to attendance system SQLite database (auto-detected if omitted)",
        )
        parser.add_argument(
            "--pg-dbname",
            type=str,
            default="attendance_db",
            help="PostgreSQL database name for attendance system (default: attendance_db)",
        )
        parser.add_argument(
            "--pg-user",
            type=str,
            default="attendance_user",
            help="PostgreSQL user for attendance system (default: attendance_user)",
        )
        parser.add_argument(
            "--pg-password",
            type=str,
            default="JetZ@t_2026",
            help="PostgreSQL password for attendance system",
        )
        parser.add_argument(
            "--pg-host",
            type=str,
            default="localhost",
            help="PostgreSQL host for attendance system (default: localhost)",
        )
        parser.add_argument(
            "--pg-port",
            type=int,
            default=5432,
            help="PostgreSQL port for attendance system (default: 5432)",
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

    def _try_sqlite(self, path):
        """Returns (conn, count) if valid SQLite DB with students_student table, else (None, 0)."""
        if not path or not os.path.exists(path):
            return None, 0
        try:
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM students_student")
            count = cur.fetchone()[0]
            if count > 0:
                return conn, count
            conn.close()
        except Exception:
            pass
        return None, 0

    def _try_postgres(self, dbname, user, password, host, port):
        """Attempts connection to PostgreSQL attendance database."""
        # Try psycopg (v3)
        try:
            import psycopg
            from psycopg.rows import dict_row
            conn = psycopg.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port,
                row_factory=dict_row
            )
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM students_student")
            row = cur.fetchone()
            count = list(row.values())[0] if isinstance(row, dict) else row[0]
            if count > 0:
                return conn, "psycopg", count
            conn.close()
        except Exception:
            pass

        # Try psycopg2 (v2)
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            conn = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port,
                cursor_factory=RealDictCursor
            )
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM students_student")
            row = cur.fetchone()
            count = list(row.values())[0] if isinstance(row, dict) else row[0]
            if count > 0:
                return conn, "psycopg2", count
            conn.close()
        except Exception:
            pass

        return None, None, 0

    def handle(self, *args, **options):
        custom_db_path = options.get("attendance_db")
        temp_password = options.get("temp_password", "CodeCamp@2026")
        dry_run = options.get("dry_run", False)

        pg_dbname = options.get("pg_dbname", "attendance_db")
        pg_user = options.get("pg_user", "attendance_user")
        pg_password = options.get("pg_password", "JetZ@t_2026")
        pg_host = options.get("pg_host", "localhost")
        pg_port = options.get("pg_port", 5432)

        source_type = None  # "sqlite" or "postgres"
        db_conn = None
        db_description = None
        placeholder = "?"

        # 1. Check custom path if provided
        if custom_db_path:
            c, count = self._try_sqlite(custom_db_path)
            if c:
                db_conn = c
                source_type = "sqlite"
                placeholder = "?"
                db_description = f"Custom SQLite ({custom_db_path}) with {count} students"

        # 2. Check candidate SQLite paths
        if not db_conn:
            candidate_paths = [
                "/var/www/codecamp2026/attendance-system/backend/db.sqlite3",
                "/var/www/attendance-system/backend/db.sqlite3",
                "/var/www/attendance/backend/db.sqlite3",
                "/var/www/attendance-system/db.sqlite3",
                "/var/www/attendance/db.sqlite3",
                "/var/www/codecamp/attendance-system/backend/db.sqlite3",
                r"c:\Projects\attendance-system\backend\db.sqlite3",
                r"c:\Projects\codecamp2026\attendance-system\backend\db.sqlite3",
                "attendance-system/backend/db.sqlite3",
                "../attendance-system/backend/db.sqlite3",
            ]
            for path in candidate_paths:
                c, count = self._try_sqlite(path)
                if c:
                    db_conn = c
                    source_type = "sqlite"
                    placeholder = "?"
                    db_description = f"SQLite ({os.path.abspath(path)}) with {count} students"
                    break

        # 3. Search filesystem for any .sqlite3 with students_student table
        if not db_conn:
            search_roots = ["/var/www", "/home", "c:\\Projects"]
            for s_root in search_roots:
                if os.path.exists(s_root):
                    for root_dir, _, files in os.walk(s_root):
                        for f in files:
                            if f.endswith(".sqlite3") or f.endswith(".db"):
                                full_p = os.path.join(root_dir, f)
                                c, count = self._try_sqlite(full_p)
                                if c:
                                    db_conn = c
                                    source_type = "sqlite"
                                    placeholder = "?"
                                    db_description = f"Auto-discovered SQLite ({full_p}) with {count} students"
                                    break
                        if db_conn:
                            break
                if db_conn:
                    break

        # 4. Try PostgreSQL attendance_db
        if not db_conn:
            self.stdout.write("Checking PostgreSQL attendance_db...")
            pg_conn, pg_driver, count = self._try_postgres(pg_dbname, pg_user, pg_password, pg_host, pg_port)
            if pg_conn:
                db_conn = pg_conn
                source_type = "postgres"
                placeholder = "%s"
                db_description = f"PostgreSQL {pg_dbname} on {pg_host}:{pg_port} ({pg_driver}) with {count} students"

        # If still nothing, try postgres as postgres user (peer/local socket default on Linux)
        if not db_conn:
            pg_conn, pg_driver, count = self._try_postgres(pg_dbname, "postgres", "", "localhost", pg_port)
            if pg_conn:
                db_conn = pg_conn
                source_type = "postgres"
                placeholder = "%s"
                db_description = f"PostgreSQL {pg_dbname} as postgres user with {count} students"

        if not db_conn:
            self.stderr.write(self.style.ERROR(
                "❌ Could not find active Attendance database with student records!\n"
                "Checked SQLite candidates and PostgreSQL attendance_db.\n"
                "Please specify path via: --attendance-db <path> OR postgres via --pg-dbname <name>"
            ))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== Transferring Attendance Students to Main Portal ({'DRY RUN' if dry_run else 'LIVE TRANSACTION'}) ==="
        ))
        self.stdout.write(self.style.SUCCESS(f"✅ Connected to Attendance Source: {db_description}"))
        self.stdout.write(f"Temporary Password for all transferred students: {temp_password}\n")

        # 2. Resolve Academy Tenant
        tenant = None
        try:
            tenant = Tenant.objects.filter(is_default=True).first() or Tenant.objects.first()
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠️ Tenant resolution skipped (table or record not found: {e})"))

        # 3. Resolve Courses & Batches for Mapping
        default_course = None
        python_course = None
        web_course = None
        innovators_course = None
        try:
            default_course = Course.objects.filter(is_published=True).first()
            python_course = Course.objects.filter(name__icontains="python").first() or default_course
            web_course = Course.objects.filter(name__icontains="web").first() or default_course
            innovators_course = Course.objects.filter(name__icontains="innovator").first() or default_course
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠️ Course resolution skipped: {e}"))

        cur = db_conn.cursor()

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
        try:
            cur.execute(query)
            students_rows = cur.fetchall()
        except Exception as q_err:
            self.stdout.write(self.style.WARNING(f"Full join failed ({q_err}), falling back to direct table query..."))
            fallback_query = """
                SELECT 
                    s.id as student_row_id,
                    s.student_id,
                    s.first_name,
                    s.last_name,
                    s.class_name,
                    s.teaching_class_id,
                    '' as teaching_class_name,
                    '' as gender,
                    1 as is_active,
                    '' as parent_name,
                    '' as parent_phone,
                    '' as parent_email
                FROM students_student s
                ORDER BY s.id ASC
            """
            cur.execute(fallback_query)
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

                    young_innovators_course = Course.objects.filter(name__icontains="innovator").first() or default_course

                    # User rule: All classes referring to "summer" map directly to Young Innovators!
                    if "summer" in effective_class or "teen" in effective_class or "innovator" in effective_class or "young" in effective_class or "beginner" in effective_class:
                        target_course = young_innovators_course
                        student_type = "Young Innovator"
                        stats["summer_students"] += 1
                    elif "python" in effective_class or "programing advance" in effective_class or "advance" in effective_class:
                        target_course = Course.objects.filter(name__icontains="python").first() or default_course
                        student_type = "Regular"
                        stats["regular_students"] += 1
                    elif "data" in effective_class or "analysis" in effective_class:
                        target_course = Course.objects.filter(name__icontains="data").first() or default_course
                        student_type = "Regular"
                        stats["regular_students"] += 1
                    elif "robot" in effective_class or "automation" in effective_class:
                        target_course = Course.objects.filter(name__icontains="robotics").first() or default_course
                        student_type = "Regular"
                        stats["regular_students"] += 1
                    elif "cloud" in effective_class or "devops" in effective_class:
                        target_course = Course.objects.filter(name__icontains="cloud").first() or default_course
                        student_type = "Regular"
                        stats["regular_students"] += 1
                    elif "cyber" in effective_class or "security" in effective_class or "ethical" in effective_class:
                        target_course = Course.objects.filter(name__icontains="cyber").first() or default_course
                        student_type = "Regular"
                        stats["regular_students"] += 1
                    elif "web" in effective_class or "batch a" in effective_class or "batch b" in effective_class:
                        target_course = Course.objects.filter(name__icontains="web").first() or default_course
                        student_type = "Regular"
                        stats["regular_students"] += 1
                    else:
                        target_course = young_innovators_course
                        student_type = "Young Innovator"
                        stats["summer_students"] += 1

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
                        clean_sid = student_id.lower().replace("-", "")
                        username_candidate = f"student_{clean_sid}"

                    # Check if user already exists by external_attendance_id
                    existing_profile = Profile.objects.filter(external_attendance_id__iexact=student_id).first()
                    if not existing_profile:
                        # Also check without hyphens
                        clean_sid = student_id.replace("-", "").replace(" ", "").upper()
                        for p_check in Profile.objects.exclude(external_attendance_id="").select_related("user"):
                            if p_check.external_attendance_id and p_check.external_attendance_id.replace("-", "").replace(" ", "").upper() == clean_sid:
                                existing_profile = p_check
                                break

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

                    # Import attendance records
                    try:
                        att_query = f"SELECT date, check_in, check_out FROM attendance_attendance WHERE student_id = {placeholder}"
                        cur.execute(att_query, (row["student_row_id"],))
                        att_rows = cur.fetchall()

                        default_subject = None
                        if target_course:
                            default_subject = Subject.objects.filter(course=target_course).first()

                        for att in att_rows:
                            att_date_str = att["date"] if isinstance(att, dict) or hasattr(att, "keys") else att[0]
                            if att_date_str:
                                if isinstance(att_date_str, datetime.date):
                                    att_date = att_date_str
                                else:
                                    try:
                                        att_date = datetime.date.fromisoformat(str(att_date_str))
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
                    except Exception:
                        pass

                if dry_run:
                    transaction.set_rollback(True)
                    self.stdout.write(self.style.WARNING("\n[DRY RUN] Rolled back all changes without saving."))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error during transfer: {e}"))
            raise

        try:
            db_conn.close()
        except Exception:
            pass

        # Print Summary Table
        self.stdout.write("\n" + "=" * 115)
        self.stdout.write(self.style.SUCCESS("[OK] ATTENDANCE STUDENTS TRANSFER COMPLETE"))
        self.stdout.write("=" * 115)
        self.stdout.write(
            f"{'Student Name':<22} | {'Type':<10} | {'Student ID':<13} | {'Username':<20} | {'Course':<24} | {'Temp Password'}"
        )
        self.stdout.write("-" * 115)
        for r in transferred_roster:
            self.stdout.write(
                f"{r['name']:<22} | {r['type']:<10} | {r['student_id']:<13} | {r['username']:<20} | {r['course'][:24]:<24} | {r['password']}"
            )
        self.stdout.write("=" * 115)
        self.stdout.write(
            f"Total: {stats['transferred']} new, {stats['updated']} updated (Regular: {stats['regular_students']}, Summer: {stats['summer_students']})"
        )
        self.stdout.write(f"Attendance Records Synced: {stats['attendance_records']}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Students can log in with: Student ID, Username, or Email using temporary password '{temp_password}'"
            )
        )
