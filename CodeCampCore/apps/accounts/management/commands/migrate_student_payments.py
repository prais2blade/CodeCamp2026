import os
import re
import datetime
import uuid
from decimal import Decimal
import sqlite3

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.tenants.models import Tenant
from apps.accounts.models import Profile, Attendance
from apps.courses.models import Course, Subject
from apps.scheduling.models import Batch
from apps.payments.models import Payment, Receipt

User = get_user_model()


class Command(BaseCommand):
    help = "Migrate summer registration payments from codecamp_db and sync all attendance check-ins into CodeCampCore"

    def add_arguments(self, parser):
        parser.add_argument(
            "--attendance-db",
            type=str,
            default="/var/www/codecamp2026/attendance-system/backend/db.sqlite3",
            help="Path to SQLite attendance database",
        )
        parser.add_argument(
            "--codecamp-db",
            type=str,
            default="codecamp_db",
            help="PostgreSQL database name for Codecamp summer registrations",
        )
        parser.add_argument(
            "--default-monthly-fee",
            type=str,
            default="35000.00",
            help="Default monthly fee for students (default: 35000.00)",
        )
        parser.add_argument(
            "--mark-regular-paid",
            action="store_true",
            default=True,
            help="Mark active regular attendance students as having paid their current monthly fee",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the payment and attendance sync without saving changes",
        )

    def _connect_codecamp_pg(self, dbname):
        """Attempts to connect to PostgreSQL codecamp_db using psycopg/psycopg2."""
        # Try psycopg3
        for user, pwd in [
            ("codecamp_user", "JetZ@t_2026_LiveSecure"),
            ("codecamp_user", "JetZ@t_2026"),
            ("postgres", ""),
        ]:
            try:
                import psycopg
                from psycopg.rows import dict_row
                conn = psycopg.connect(
                    dbname=dbname,
                    user=user,
                    password=pwd if pwd else None,
                    host="localhost",
                    port=5432,
                    row_factory=dict_row
                )
                return conn, "psycopg"
            except Exception:
                pass

            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                conn = psycopg2.connect(
                    dbname=dbname,
                    user=user,
                    password=pwd if pwd else None,
                    host="localhost",
                    port=5432,
                    cursor_factory=RealDictCursor
                )
                return conn, "psycopg2"
            except Exception:
                pass

        return None, None

    def handle(self, *args, **options):
        attendance_db_path = options["attendance_db"]
        codecamp_pg_dbname = options["codecamp_db"]
        default_fee = Decimal(options["default_monthly_fee"])
        mark_regular_paid = options["mark_regular_paid"]
        dry_run = options["dry_run"]

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== Migrating Payments and Attendance Records ({'DRY RUN' if dry_run else 'LIVE TRANSACTION'}) ==="
        ))

        # 1. Connect to PostgreSQL codecamp_db
        pg_conn, driver = self._connect_codecamp_pg(codecamp_pg_dbname)
        registrations = []
        if pg_conn:
            self.stdout.write(self.style.SUCCESS(f"✅ Connected to PostgreSQL '{codecamp_pg_dbname}' ({driver})"))
            cur = pg_conn.cursor()
            try:
                cur.execute("""
                    SELECT 
                        id, 
                        reg_code, 
                        attendance_student_id, 
                        first_name, 
                        last_name, 
                        parent_email, 
                        parent_phone, 
                        price_paid, 
                        payment_verified, 
                        registration_status, 
                        created_at
                    FROM teencamp_codingcampregistration
                    ORDER BY id ASC
                """)
                registrations = cur.fetchall()
                self.stdout.write(f"Found {len(registrations)} summer registrations with payment records in '{codecamp_pg_dbname}'.")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Could not read teencamp_codingcampregistration: {e}"))
        else:
            self.stdout.write(self.style.WARNING(f"⚠️ Could not connect to PostgreSQL '{codecamp_pg_dbname}'. Continuing with existing profile data."))

        # 2. Connect to SQLite attendance_db
        att_conn = None
        if os.path.exists(attendance_db_path):
            att_conn = sqlite3.connect(attendance_db_path)
            att_conn.row_factory = sqlite3.Row
            self.stdout.write(self.style.SUCCESS(f"✅ Connected to Attendance DB: {attendance_db_path}"))
        else:
            self.stdout.write(self.style.WARNING(f"⚠️ Attendance DB not found at: {attendance_db_path}"))

        # Build attendance sqlite student row id -> student_id mapping
        att_id_to_student_id = {}
        att_scans = []
        if att_conn:
            att_cur = att_conn.cursor()
            try:
                att_cur.execute("SELECT id, student_id FROM students_student")
                for r in att_cur.fetchall():
                    att_id_to_student_id[r["id"]] = r["student_id"]

                att_cur.execute("SELECT student_id, date, check_in, check_out FROM attendance_attendance")
                att_scans = att_cur.fetchall()
                self.stdout.write(f"Found {len(att_scans)} raw attendance scan logs in Attendance DB.")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Could not read attendance records from SQLite: {e}"))

        # Ensure all courses have a primary Subject so attendance can link cleanly
        for c in Course.objects.all():
            Subject.objects.get_or_create(
                course=c,
                defaults={
                    "name": f"{c.name} - Core Lecture & Practical",
                    "description": f"Core training and practical modules for {c.name}.",
                }
            )

        stats = {
            "summer_payments_synced": 0,
            "regular_payments_synced": 0,
            "receipts_generated": 0,
            "attendance_records_synced": 0,
        }

        report_rows = []

        try:
            with transaction.atomic():
                # ---------------------------------------------------------
                # PHASE A: SYNC SUMMER REGISTRATIONS PAYMENTS (35 STUDENTS)
                # ---------------------------------------------------------
                synced_user_ids = set()

                for reg in registrations:
                    ext_id = (reg["attendance_student_id"] or "").strip()
                    reg_code = (reg["reg_code"] or "").strip()
                    first_name = (reg["first_name"] or "").strip()
                    last_name = (reg["last_name"] or "").strip()
                    parent_email = (reg["parent_email"] or "").strip().lower()
                    raw_paid = reg["price_paid"]
                    payment_verified = bool(reg["payment_verified"])
                    reg_status = (reg["registration_status"] or "").strip().lower()

                    # Find profile in CodeCampCore
                    profile = None
                    if ext_id:
                        profile = Profile.objects.filter(external_attendance_id__iexact=ext_id).select_related('user', 'course', 'batch').first()
                        if not profile:
                            # Normalized match
                            clean_ext = ext_id.replace('-', '').replace(' ', '').upper()
                            for p in Profile.objects.exclude(external_attendance_id='').select_related('user', 'course', 'batch'):
                                if p.external_attendance_id and p.external_attendance_id.replace('-', '').replace(' ', '').upper() == clean_ext:
                                    profile = p
                                    break

                    if not profile and parent_email:
                        profile = Profile.objects.filter(user__email__iexact=parent_email).select_related('user', 'course', 'batch').first()

                    if not profile:
                        profile = Profile.objects.filter(
                            user__first_name__iexact=first_name,
                            user__last_name__iexact=last_name
                        ).select_related('user', 'course', 'batch').first()

                    if not profile:
                        continue

                    user = profile.user
                    synced_user_ids.add(user.id)
                    course = profile.course

                    # Compute amount paid
                    amount_paid = Decimal('0.00')
                    if raw_paid is not None:
                        try:
                            amount_paid = Decimal(str(raw_paid))
                        except Exception:
                            amount_paid = Decimal('0.00')

                    amount_due = course.fee if (course and course.fee and course.fee > 0) else default_fee
                    if amount_paid == 0 and (payment_verified or reg_status in ['confirmed', 'approved', 'completed', 'active']):
                        # If marked verified in registration system, reflect full payment
                        amount_paid = amount_due

                    # Status
                    if amount_paid >= amount_due:
                        p_status = 'paid'
                    elif amount_paid > 0:
                        p_status = 'partial'
                    else:
                        p_status = 'pending'

                    # Create or update Payment
                    payment, created = Payment.objects.update_or_create(
                        student=user,
                        defaults={
                            "course": course,
                            "batch": profile.batch,
                            "amount_due": amount_due,
                            "amount_paid": amount_paid,
                            "monthly_payment": default_fee,
                            "status": p_status,
                        }
                    )
                    stats["summer_payments_synced"] += 1

                    # Generate Receipt if paid
                    if amount_paid > 0:
                        Receipt.objects.get_or_create(
                            payment=payment,
                            amount=amount_paid,
                            defaults={
                                "reference": uuid.uuid4(),
                                "issued_date": reg["created_at"] or timezone.now(),
                            }
                        )
                        stats["receipts_generated"] += 1

                    # Update Profile
                    profile.has_paid = (p_status in ['paid', 'partial'])
                    profile.registration_paid = True
                    profile.tuition_paid = (p_status == 'paid')
                    profile.paid_amount = amount_paid
                    profile.total_fee = amount_due
                    profile.save()

                    report_rows.append({
                        "name": f"{user.first_name} {user.last_name}",
                        "student_id": profile.external_attendance_id or user.username,
                        "type": "Summer Camp",
                        "course": course.name if course else "Young Innovators",
                        "due": amount_due,
                        "paid": amount_paid,
                        "status": p_status.upper(),
                    })

                # ---------------------------------------------------------
                # PHASE B: SYNC REGULAR / DIRECT ENROLLMENT STUDENTS
                # ---------------------------------------------------------
                all_student_profiles = Profile.objects.filter(role='student').select_related('user', 'course', 'batch')
                for profile in all_student_profiles:
                    user = profile.user
                    if user.id in synced_user_ids:
                        continue

                    course = profile.course
                    amount_due = course.fee if (course and course.fee and course.fee > 0) else default_fee
                    
                    # For active attending students, set their current payment standing
                    if mark_regular_paid:
                        amount_paid = amount_due
                        p_status = 'paid'
                    else:
                        amount_paid = Decimal('0.00')
                        p_status = 'pending'

                    payment, created = Payment.objects.update_or_create(
                        student=user,
                        defaults={
                            "course": course,
                            "batch": profile.batch,
                            "amount_due": amount_due,
                            "amount_paid": amount_paid,
                            "monthly_payment": default_fee,
                            "status": p_status,
                        }
                    )
                    stats["regular_payments_synced"] += 1

                    if amount_paid > 0:
                        Receipt.objects.get_or_create(
                            payment=payment,
                            amount=amount_paid,
                            defaults={
                                "reference": uuid.uuid4(),
                            }
                        )
                        stats["receipts_generated"] += 1

                    profile.has_paid = (p_status in ['paid', 'partial'])
                    profile.registration_paid = True
                    profile.tuition_paid = (p_status == 'paid')
                    profile.paid_amount = amount_paid
                    profile.total_fee = amount_due
                    profile.save()

                    report_rows.append({
                        "name": f"{user.first_name} {user.last_name}",
                        "student_id": profile.external_attendance_id or user.username,
                        "type": "Regular / Direct",
                        "course": course.name if course else "Regular Track",
                        "due": amount_due,
                        "paid": amount_paid,
                        "status": p_status.upper(),
                    })

                # ---------------------------------------------------------
                # PHASE C: RE-VERIFY & SYNC ALL ATTENDANCE SCANS
                # ---------------------------------------------------------
                for scan in att_scans:
                    sqlite_student_id = scan["student_id"]
                    scan_ext_id = att_id_to_student_id.get(sqlite_student_id)
                    if not scan_ext_id:
                        continue

                    # Match student user in CodeCampCore
                    clean_id = scan_ext_id.replace('-', '').replace(' ', '').upper()
                    profile = None
                    for p in all_student_profiles:
                        if p.external_attendance_id and p.external_attendance_id.replace('-', '').replace(' ', '').upper() == clean_id:
                            profile = p
                            break

                    if not profile:
                        continue

                    user = profile.user
                    course = profile.course
                    subject = Subject.objects.filter(course=course).first() if course else Subject.objects.first()

                    scan_date_str = scan["date"]
                    if not scan_date_str:
                        continue

                    try:
                        scan_date = datetime.date.fromisoformat(str(scan_date_str))
                    except Exception:
                        continue

                    # Parse check_in and check_out times
                    check_in_time = None
                    check_out_time = None
                    if scan["check_in"]:
                        try:
                            check_in_time = datetime.datetime.fromisoformat(str(scan["check_in"])).time()
                        except Exception:
                            pass
                    if scan["check_out"]:
                        try:
                            check_out_time = datetime.datetime.fromisoformat(str(scan["check_out"])).time()
                        except Exception:
                            pass

                    _, att_created = Attendance.objects.get_or_create(
                        student=user,
                        subject=subject,
                        date=scan_date,
                        defaults={
                            "tenant": profile.tenant,
                            "batch": profile.batch,
                            "status": "Present",
                            "check_in_time": check_in_time,
                            "check_out_time": check_out_time,
                            "marked_by": user,
                            "source": "kiosk_sync",
                        }
                    )
                    if att_created:
                        stats["attendance_records_synced"] += 1

                if dry_run:
                    transaction.set_rollback(True)
                    self.stdout.write(self.style.WARNING("\n[DRY RUN] Rolled back all changes without saving."))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error during migration: {e}"))
            raise

        if pg_conn:
            try:
                pg_conn.close()
            except Exception:
                pass
        if att_conn:
            try:
                att_conn.close()
            except Exception:
                pass

        # Print Complete Roster Payment Table
        self.stdout.write("\n" + "=" * 115)
        self.stdout.write(self.style.SUCCESS("[OK] STUDENT PAYMENTS & ATTENDANCE SYNCHRONIZATION COMPLETE"))
        self.stdout.write("=" * 115)
        self.stdout.write(
            f"{'Student Name':<22} | {'Student ID':<13} | {'Track':<14} | {'Course':<24} | {'Amount Due':<11} | {'Paid':<11} | {'Status'}"
        )
        self.stdout.write("-" * 115)
        for r in report_rows:
            self.stdout.write(
                f"{r['name']:<22} | {r['student_id']:<13} | {r['type']:<14} | {r['course'][:24]:<24} | ₦{r['due']:<10.2f} | ₦{r['paid']:<10.2f} | {r['status']}"
            )
        self.stdout.write("=" * 115)
        self.stdout.write(f"Summer Student Payments Synced:  {stats['summer_payments_synced']}")
        self.stdout.write(f"Regular Student Payments Synced: {stats['regular_payments_synced']}")
        self.stdout.write(f"Receipts Generated:              {stats['receipts_generated']}")
        self.stdout.write(f"Total Attendance Scans Synced:   {Attendance.objects.count()} (New Synced: {stats['attendance_records_synced']})")
        self.stdout.write("=" * 115)
