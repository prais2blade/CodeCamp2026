import os
import sqlite3
import logging
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from apps.accounts.models import Profile

logger = logging.getLogger("attendance_sync")
User = get_user_model()


class AttendanceSyncService:
    """
    Two-way synchronization service between CodeCampCore ERP and the Attendance System.
    - Synchronizes official student IDs (e.g. CDCP-000001).
    - Synchronizes faculty / teachers to eliminate duplicate tutors.
    """

    @classmethod
    def get_attendance_db_path(cls):
        """Locates the attendance database path across development and production environments."""
        env_path = getattr(settings, "ATTENDANCE_DB_PATH", os.getenv("ATTENDANCE_DB_PATH", ""))
        if env_path and os.path.exists(env_path):
            return env_path

        candidates = [
            # Local Windows paths
            "C:/Projects/attendance-system/backend/db.sqlite3",
            "c:/Projects/attendance-system/backend/db.sqlite3",
            os.path.join(settings.BASE_DIR.parent, "attendance-system", "backend", "db.sqlite3"),
            # Linux VPS Production paths
            "/var/www/attendance-system/backend/db.sqlite3",
            "/var/www/attendance/backend/db.sqlite3",
            "/var/www/codecamp2026/attendance/backend/db.sqlite3",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    @classmethod
    def sync_tutors(cls, db_path=None):
        """
        Synchronizes registered teachers from attendance system into CodeCampCore as instructors.
        Ensures zero tutor duplication.
        """
        db_path = db_path or cls.get_attendance_db_path()
        if not db_path:
            return {"count": 0, "error": "Attendance database not found"}

        tutors_created = 0
        tutors_updated = 0

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT username, first_name, last_name, email, is_active FROM accounts_user WHERE role='TEACHER'")
            teachers = cursor.fetchall()
            conn.close()

            for username, first_name, last_name, email, is_active in teachers:
                # Find or create User in CodeCampCore
                user = User.objects.filter(username__iexact=username).first()
                if not user and email:
                    user = User.objects.filter(email__iexact=email).first()

                if not user:
                    user = User.objects.create_user(
                        username=username,
                        email=email or f"{username.lower()}@codecamp.com.ng",
                        first_name=first_name or username.title(),
                        last_name=last_name or "",
                        is_active=bool(is_active)
                    )
                    user.set_unusable_password()
                    user.save()
                    tutors_created += 1

                # Ensure Profile has instructor role
                profile, prof_created = Profile.objects.get_or_create(user=user)
                if profile.role != 'instructor':
                    profile.role = 'instructor'
                    profile.is_approved = True
                    profile.save(update_fields=['role', 'is_approved'])
                    tutors_updated += 1

            return {
                "success": True,
                "tutors_total": len(teachers),
                "tutors_created": tutors_created,
                "tutors_updated": tutors_updated,
            }
        except Exception as exc:
            logger.error(f"Error syncing tutors: {exc}")
            return {"success": False, "error": str(exc)}

    @classmethod
    def sync_student_ids(cls, db_path=None):
        """
        Matches students from the attendance system with CodeCampCore profiles
        and populates their official external_attendance_id (e.g. CDCP-000001).
        """
        db_path = db_path or cls.get_attendance_db_path()
        if not db_path:
            return {"count": 0, "error": "Attendance database not found"}

        students_matched = 0
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT student_id, first_name, last_name, parent_name FROM students_student")
            att_students = cursor.fetchall()
            conn.close()

            for student_id, fn, ln, parent_name in att_students:
                fn = fn.strip()
                ln = ln.strip()
                if not fn or not student_id:
                    continue

                # Query CodeCampCore students
                q = Profile.objects.filter(role='student')

                # 1. Match by already set external_attendance_id
                match = q.filter(external_attendance_id=student_id).first()

                # 2. Match by exact first_name and last_name
                if not match:
                    match = q.filter(
                        user__first_name__iexact=fn,
                        user__last_name__iexact=ln
                    ).first()

                # 3. Match by username (e.g. yinka.ola, opeyemi.oguns)
                if not match:
                    normalized_user = f"{fn.lower()}.{ln.lower()}"
                    combo_user = f"{fn.lower()}{ln.lower()}"
                    match = q.filter(user__username__in=[normalized_user, combo_user]).first()

                # 4. Partial full name matching
                if not match:
                    for s in q.select_related('user'):
                        full_name = s.user.get_full_name().lower()
                        if fn.lower() in full_name and ln.lower() in full_name:
                            match = s
                            break

                if match:
                    if match.external_attendance_id != student_id:
                        match.external_attendance_id = student_id
                        match.save(update_fields=['external_attendance_id'])
                        students_matched += 1
                    else:
                        students_matched += 1

            return {
                "success": True,
                "attendance_students_count": len(att_students),
                "students_matched": students_matched,
            }
        except Exception as exc:
            logger.error(f"Error syncing student IDs: {exc}")
            return {"success": False, "error": str(exc)}

    @classmethod
    def sync_all(cls):
        """Runs complete two-way synchronization of tutors and student IDs."""
        db_path = cls.get_attendance_db_path()
        tutor_res = cls.sync_tutors(db_path)
        student_res = cls.sync_student_ids(db_path)

        return {
            "success": tutor_res.get("success", False) or student_res.get("success", False),
            "db_path": db_path,
            "tutors": tutor_res,
            "students": student_res,
        }
