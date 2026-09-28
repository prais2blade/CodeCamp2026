import os
import sqlite3
import logging
import json
import secrets
import urllib.request
import urllib.error
import re
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.accounts.models import Profile

logger = logging.getLogger("attendance_sync")
User = get_user_model()


class AttendanceSyncService:
    """
    Two-way synchronization service between CodeCampCore ERP and the Attendance System.
    - Automatically assigns and synchronizes official student IDs (e.g. CDCP-000001).
    - Synchronizes student personal details, enrolled course/classes, and active status.
    - Synchronizes faculty / teachers to eliminate duplicate tutors.
    - Supports both HTTP Integration REST API and direct database fallback.
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

    _api_failed = False

    @classmethod
    def get_api_config(cls):
        """Returns the configured attendance API endpoint URL and authorization API key."""
        api_url = getattr(settings, "ATTENDANCE_API_URL", os.getenv("ATTENDANCE_API_URL", "http://127.0.0.1:8001"))
        api_key = getattr(settings, "ATTENDANCE_API_KEY", os.getenv("ATTENDANCE_API_KEY", ""))
        return api_url.rstrip("/"), api_key

    @classmethod
    def generate_next_cdcp_id(cls, cursor=None):
        """
        Computes the next official CDCP-XXXXXX student ID,
        taking into account the maximum number in both the attendance system
        and CodeCampCore profiles.
        """
        highest_num = 0

        # 1. From Attendance DB if cursor or db_path available
        should_close = False
        conn = None
        try:
            if cursor is None:
                db_path = cls.get_attendance_db_path()
                if db_path and os.path.exists(db_path):
                    conn = sqlite3.connect(db_path, timeout=5)
                    cursor = conn.cursor()
                    should_close = True

            if cursor is not None:
                cursor.execute("SELECT student_id FROM students_student WHERE student_id LIKE 'CDCP-%'")
                for (sid,) in cursor.fetchall():
                    if not sid:
                        continue
                    parts = sid.split("-")
                    if len(parts) == 2 and parts[1].isdigit():
                        num = int(parts[1])
                        if num > highest_num:
                            highest_num = num
        except Exception as exc:
            logger.warning(f"AttendanceSyncService: Error checking attendance DB for max student ID: {exc}")
        finally:
            if should_close and conn:
                try:
                    conn.close()
                except Exception:
                    pass

        # 2. From CodeCampCore Profile records
        try:
            profiles = Profile.objects.filter(external_attendance_id__startswith="CDCP-")
            for p in profiles:
                sid = p.external_attendance_id or ""
                parts = sid.split("-")
                if len(parts) == 2 and parts[1].isdigit():
                    num = int(parts[1])
                    if num > highest_num:
                        highest_num = num
        except Exception as exc:
            logger.warning(f"AttendanceSyncService: Error checking CodeCampCore profiles for max student ID: {exc}")

        next_num = highest_num + 1
        return f"CDCP-{next_num:06d}"

    @classmethod
    def find_matching_teaching_class(cls, cursor, course_name):
        """Matches a course name to a teaching class in the attendance system."""
        if not course_name:
            return None, ""
        try:
            cursor.execute("SELECT id, name FROM students_teachingclass")
            classes = cursor.fetchall()
            c_lower = course_name.lower().strip()

            # Exact or substring match
            for cid, cname in classes:
                if cname.lower() == c_lower or c_lower in cname.lower() or cname.lower() in c_lower:
                    return cid, cname

            # Keyword heuristics
            if "python" in c_lower:
                for cid, cname in classes:
                    if "python" in cname.lower():
                        return cid, cname
            if "full" in c_lower or "web" in c_lower:
                for cid, cname in classes:
                    if "full-stack" in cname.lower() or "web" in cname.lower():
                        return cid, cname
            if "robot" in c_lower:
                for cid, cname in classes:
                    if "robot" in cname.lower():
                        return cid, cname
            if "data" in c_lower:
                for cid, cname in classes:
                    if "data" in cname.lower():
                        return cid, cname
            if "young" in c_lower or "beginner" in c_lower:
                for cid, cname in classes:
                    if "young" in cname.lower() or "beginner" in cname.lower():
                        return cid, cname
            if "cloud" in c_lower or "devops" in c_lower:
                for cid, cname in classes:
                    if "cloud" in cname.lower():
                        return cid, cname
            if "hack" in c_lower or "cyber" in c_lower:
                for cid, cname in classes:
                    if "hack" in cname.lower() or "cyber" in cname.lower():
                        return cid, cname
        except Exception as exc:
            logger.warning(f"AttendanceSyncService: Error matching teaching class: {exc}")

        return None, course_name

    @classmethod
    def sync_or_register_student(cls, profile):
        """
        Ensures a student has an official CDCP-XXXXXX student ID and all details
        are synchronized into the Attendance System.
        
        Supports:
        1. HTTP Integration REST API (/api/integration/register-student/)
        2. Direct SQLite DB synchronization as fallback
        3. Standalone CDCP-XXXXXX sequence generation if attendance is offline
        """
        if not profile or profile.role != 'student':
            return None

        user = profile.user
        first_name = (user.first_name or "").strip() or user.username
        last_name = (user.last_name or "").strip()
        email = (user.email or "").strip()
        phone = (profile.phone or "").strip()
        course_name = profile.course.name.strip() if profile.course else "General"
        is_active = 1 if profile.student_status == 'active' else 0
        integration_key = f"codecamp_user_{user.id}"

        # Extract dedicated Parent details if available
        if profile.parent:
            parent_name = profile.parent.full_name
            parent_phone = profile.parent.phone_number
            parent_email = profile.parent.email or email
            parent_whatsapp = profile.parent.whatsapp_number or parent_phone
            parent_title = profile.parent.title or "Mr"
            relationship = profile.relationship_to_parent or "Guardian"
        else:
            parent_name = user.get_full_name() or user.username
            parent_phone = phone or f"080{user.id:08d}"
            parent_email = email
            parent_whatsapp = parent_phone
            parent_title = "Mr"
            relationship = profile.relationship_to_parent or "Guardian"

        if profile.date_of_birth:
            dob_str = profile.date_of_birth.isoformat() if hasattr(profile.date_of_birth, 'isoformat') else str(profile.date_of_birth)
        else:
            dob_str = None
        gender = profile.gender or ""

        # If student already has an official CDCP- ID, ensure details are synced and return
        if profile.external_attendance_id and profile.external_attendance_id.startswith("CDCP-"):
            cls.sync_student_details_to_attendance(profile)
            cls.sync_photo_to_attendance(profile)
            return profile.external_attendance_id

        # -------------------------------------------------------------
        # STEP 1: Attempt HTTP API Registration
        # -------------------------------------------------------------
        api_url, api_key = cls.get_api_config()
        if not cls._api_failed and api_url and api_key:
            endpoint = f"{api_url}/api/integration/register-student/"
            payload = {
                "first_name": first_name,
                "last_name": last_name,
                "class_name": course_name,
                "date_of_birth": dob_str,
                "gender": gender,
                "parent_title": parent_title,
                "parent_name": parent_name,
                "parent_phone": parent_phone,
                "parent_email": parent_email,
                "parent_whatsapp": parent_whatsapp,
                "relationship": relationship,
                "integration_key": integration_key,
            }
            try:
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "X-API-KEY": api_key,
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=0.5) as resp:
                    if resp.status in (200, 201):
                        data = json.loads(resp.read().decode("utf-8"))
                        student_id = data.get("student_id")
                        if student_id and student_id.startswith("CDCP-"):
                            profile.external_attendance_id = student_id
                            profile.save(update_fields=['external_attendance_id'])
                            cls.sync_photo_to_attendance(profile)
                            logger.info(f"Synchronized student {user.username} via API: {student_id}")
                            return student_id
            except Exception as api_err:
                cls._api_failed = True
                logger.debug(f"Attendance API call failed ({api_err}), falling back to direct DB sync.")

        # -------------------------------------------------------------
        # STEP 2: Direct SQLite DB Synchronization Fallback
        # -------------------------------------------------------------
        db_path = cls.get_attendance_db_path()
        if db_path and os.path.exists(db_path):
            conn = None
            try:
                conn = sqlite3.connect(db_path, timeout=10)
                cursor = conn.cursor()

                # Check if already exists in students_student
                cursor.execute(
                    "SELECT id, student_id, class_name, teaching_class_id FROM students_student WHERE integration_key = ?",
                    (integration_key,)
                )
                existing = cursor.fetchone()

                if not existing and first_name and last_name:
                    cursor.execute(
                        "SELECT id, student_id, class_name, teaching_class_id FROM students_student WHERE LOWER(first_name) = ? AND LOWER(last_name) = ?",
                        (first_name.lower(), last_name.lower())
                    )
                    existing = cursor.fetchone()

                teaching_class_id, resolved_class_name = cls.find_matching_teaching_class(cursor, course_name)
                now_str = timezone.now().strftime("%Y-%m-%d %H:%M:%S")

                if existing:
                    att_id, student_id, cur_class, cur_t_id = existing
                    cursor.execute(
                        """
                        UPDATE students_student
                        SET first_name = ?, last_name = ?, class_name = ?, teaching_class_id = ?,
                            is_active = ?, parent_name = ?, date_of_birth = ?, gender = ?, integration_key = ?
                        WHERE id = ?
                        """,
                        (first_name, last_name, resolved_class_name, teaching_class_id, is_active, parent_name, dob_str, gender, integration_key, att_id)
                    )
                    conn.commit()

                    profile.external_attendance_id = student_id
                    profile.save(update_fields=['external_attendance_id'])
                    conn.close()
                    conn = None
                    cls.sync_photo_to_attendance(profile)
                    logger.info(f"Matched and synced existing attendance student {student_id} for user {user.username}")
                    return student_id

                # Not existing: Create new student record in attendance system
                new_student_id = cls.generate_next_cdcp_id(cursor)

                # Find or create Parent record
                cursor.execute(
                    "SELECT id FROM students_parent WHERE phone_number = ? OR (email != '' AND email = ?)",
                    (parent_phone, parent_email)
                )
                parent_row = cursor.fetchone()

                if parent_row:
                    parent_id = parent_row[0]
                else:
                    cursor.execute(
                        """
                        INSERT INTO students_parent
                        (full_name, phone_number, whatsapp_number, email, title, receive_email, receive_whatsapp,
                         created_at, password, must_change_password, is_active, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            parent_name,
                            parent_phone,
                            parent_whatsapp,
                            parent_email,
                            parent_title,
                            1,
                            1,
                            now_str,
                            "pbkdf2_sha256$1200000$default_codecamp_parent_key",
                            0,
                            1,
                            now_str,
                        )
                    )
                    parent_id = cursor.lastrowid

                # Insert Student
                portal_token = secrets.token_hex(16)
                cursor.execute(
                    """
                    INSERT INTO students_student
                    (student_id, first_name, last_name, is_active, created_at, class_name, gender, parent_name,
                     portal_token, teaching_class_id, integration_key, date_of_birth)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_student_id,
                        first_name,
                        last_name,
                        is_active,
                        now_str,
                        resolved_class_name,
                        gender,
                        parent_name,
                        portal_token,
                        teaching_class_id,
                        integration_key,
                        dob_str,
                    )
                )
                new_student_db_id = cursor.lastrowid

                # Link in students_studentparent
                cursor.execute(
                    """
                    INSERT INTO students_studentparent
                    (relationship, parent_id, student_id, teaching_class_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (relationship, parent_id, new_student_db_id, teaching_class_id)
                )
                conn.commit()

                profile.external_attendance_id = new_student_id
                profile.save(update_fields=['external_attendance_id'])
                conn.close()
                conn = None
                cls.sync_photo_to_attendance(profile)
                logger.info(f"Registered and synchronized new attendance student {new_student_id} for user {user.username}")
                return new_student_id
            except Exception as db_err:
                logger.error(f"AttendanceSyncService: Error during direct DB student sync: {db_err}")
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        # -------------------------------------------------------------
        # STEP 3: Standalone CDCP Sequence Generation Fallback
        # -------------------------------------------------------------
        fallback_id = cls.generate_next_cdcp_id(None)
        profile.external_attendance_id = fallback_id
        profile.save(update_fields=['external_attendance_id'])
        cls.sync_photo_to_attendance(profile)
        logger.info(f"Assigned sequential student ID {fallback_id} to user {user.username} (standalone fallback)")
        return fallback_id

    @classmethod
    def sync_photo_to_attendance(cls, profile):
        """
        Copies the student's avatar/passport from CodeCampCore to the Attendance System
        and updates the student's photo record.
        """
        if not profile or not profile.has_custom_avatar:
            return None

        try:
            db_path = cls.get_attendance_db_path()
            if not db_path or not os.path.exists(db_path):
                return None

            src_path = profile.avatar.path
            if not os.path.exists(src_path):
                return None

            import shutil
            media_root = os.path.join(os.path.dirname(db_path), "media")
            photos_dir = os.path.join(media_root, "students", "photos")
            os.makedirs(photos_dir, exist_ok=True)

            ext = os.path.splitext(src_path)[1].lower() or ".jpg"
            dest_filename = f"{(profile.external_attendance_id or f'student_{profile.user.id}').replace('-', '_')}{ext}"
            dest_full_path = os.path.join(photos_dir, dest_filename)
            shutil.copy2(src_path, dest_full_path)

            rel_photo_path = f"students/photos/{dest_filename}"
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE students_student SET photo = ? WHERE student_id = ? OR integration_key = ?",
                (rel_photo_path, profile.external_attendance_id, f"codecamp_user_{profile.user.id}")
            )
            conn.commit()
            conn.close()
            return rel_photo_path
        except Exception as exc:
            logger.warning(f"AttendanceSyncService: Error syncing student photo: {exc}")
            return None

    @classmethod
    def sync_student_details_to_attendance(cls, profile):
        """
        Pushes student profile updates (course, contact info, active status, DOB, gender)
        to the attendance system.
        """
        if not profile or profile.role != 'student':
            return False

        user = profile.user
        first_name = (user.first_name or "").strip() or user.username
        last_name = (user.last_name or "").strip()
        email = (user.email or "").strip()
        phone = (profile.phone or "").strip()
        course_name = profile.course.name.strip() if profile.course else "General"
        is_active = 1 if profile.student_status == 'active' else 0
        integration_key = f"codecamp_user_{user.id}"
        student_id = profile.external_attendance_id
        if profile.date_of_birth:
            dob_str = profile.date_of_birth.isoformat() if hasattr(profile.date_of_birth, 'isoformat') else str(profile.date_of_birth)
        else:
            dob_str = None
        gender = profile.gender or ""

        if profile.parent:
            parent_name = profile.parent.full_name
            parent_phone = profile.parent.phone_number
            parent_email = profile.parent.email or email
        else:
            parent_name = user.get_full_name() or user.username
            parent_phone = phone or f"080{user.id:08d}"
            parent_email = email

        db_path = cls.get_attendance_db_path()
        if not db_path or not os.path.exists(db_path):
            return False

        conn = None
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            teaching_class_id, resolved_class_name = cls.find_matching_teaching_class(cursor, course_name)

            cursor.execute(
                """
                UPDATE students_student
                SET first_name = ?, last_name = ?, class_name = ?, teaching_class_id = ?,
                    is_active = ?, parent_name = ?, date_of_birth = ?, gender = ?
                WHERE integration_key = ? OR student_id = ?
                """,
                (first_name, last_name, resolved_class_name, teaching_class_id, is_active, parent_name, dob_str, gender, integration_key, student_id)
            )
            conn.commit()

            # Ensure correct parent linking in students_studentparent
            if parent_phone or parent_email:
                try:
                    # Find student DB id
                    cursor.execute("SELECT id FROM students_student WHERE integration_key = ? OR student_id = ?", (integration_key, student_id))
                    s_row = cursor.fetchone()
                    if s_row:
                        student_db_id = s_row[0]

                        # 1. Look for existing parent by real phone_number first
                        target_parent_id = None
                        if parent_phone:
                            cursor.execute("SELECT id FROM students_parent WHERE phone_number = ?", (parent_phone,))
                            p_by_phone = cursor.fetchone()
                            if p_by_phone:
                                target_parent_id = p_by_phone[0]

                        # 2. If not found by phone, check by email (if email is set)
                        if not target_parent_id and parent_email:
                            cursor.execute("SELECT id FROM students_parent WHERE email = ?", (parent_email,))
                            p_by_email = cursor.fetchone()
                            if p_by_email:
                                target_parent_id = p_by_email[0]

                        # 3. Check current linked parent for this student
                        cursor.execute("SELECT id, parent_id FROM students_studentparent WHERE student_id = ?", (student_db_id,))
                        sp_row = cursor.fetchone()
                        sp_id, current_linked_parent_id = sp_row if sp_row else (None, None)

                        if target_parent_id:
                            # Target parent exists: update full_name, email, phone if appropriate
                            if parent_name:
                                cursor.execute("UPDATE students_parent SET full_name = ? WHERE id = ?", (parent_name, target_parent_id))
                            if parent_phone:
                                cursor.execute("UPDATE students_parent SET phone_number = ?, whatsapp_number = ? WHERE id = ?", (parent_phone, parent_phone, target_parent_id))
                            if parent_email:
                                cursor.execute("UPDATE students_parent SET email = ? WHERE id = ?", (parent_email, target_parent_id))
                        elif current_linked_parent_id:
                            # Student already has a linked parent row: update that row with real details!
                            target_parent_id = current_linked_parent_id
                            cursor.execute(
                                """
                                UPDATE students_parent
                                SET full_name = ?, phone_number = ?, whatsapp_number = ?, email = ?
                                WHERE id = ?
                                """,
                                (parent_name or first_name, parent_phone, parent_phone, parent_email, target_parent_id)
                            )
                        else:
                            # Create new parent row
                            now_str = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
                            cursor.execute(
                                """
                                INSERT INTO students_parent
                                (full_name, phone_number, whatsapp_number, email, title, receive_email, receive_whatsapp,
                                 created_at, password, must_change_password, is_active, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    parent_name or f"{first_name} {last_name} Guardian",
                                    parent_phone,
                                    parent_phone,
                                    parent_email,
                                    profile.parent.title if profile.parent else "Mr",
                                    1,
                                    1,
                                    now_str,
                                    "pbkdf2_sha256$1200000$default_codecamp_parent_key",
                                    0,
                                    1,
                                    now_str,
                                )
                            )
                            target_parent_id = cursor.lastrowid

                        # Ensure students_studentparent links student_db_id to target_parent_id
                        rel = profile.relationship_to_parent or "Guardian"
                        if sp_id:
                            if current_linked_parent_id != target_parent_id:
                                cursor.execute("UPDATE students_studentparent SET parent_id = ?, relationship = ? WHERE id = ?", (target_parent_id, rel, sp_id))
                                # Clean up former parent if it has no children
                                cursor.execute("SELECT count(*) FROM students_studentparent WHERE parent_id = ?", (current_linked_parent_id,))
                                if cursor.fetchone()[0] == 0:
                                    cursor.execute("DELETE FROM students_parent WHERE id = ?", (current_linked_parent_id,))
                            else:
                                cursor.execute("UPDATE students_studentparent SET relationship = ? WHERE id = ?", (rel, sp_id))
                        else:
                            cursor.execute(
                                "INSERT INTO students_studentparent (relationship, parent_id, student_id, teaching_class_id) VALUES (?, ?, ?, ?)",
                                (rel, target_parent_id, student_db_id, teaching_class_id)
                            )
                        conn.commit()
                except Exception as p_err:
                    logger.debug(f"Parent update skipped: {p_err}")

            conn.close()
            conn = None
            cls.sync_photo_to_attendance(profile)
            return True
        except Exception as exc:
            logger.warning(f"AttendanceSyncService: Error syncing student details: {exc}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

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
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT username, first_name, last_name, email, is_active FROM accounts_user WHERE role='TEACHER'")
            teachers = cursor.fetchall()
            conn.close()

            for username, first_name, last_name, email, is_active in teachers:
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
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT student_id, first_name, last_name, parent_name, integration_key FROM students_student")
            att_students = cursor.fetchall()
            conn.close()

            for student_id, fn, ln, parent_name, ikey in att_students:
                fn = fn.strip() if fn else ""
                ln = ln.strip() if ln else ""
                if not student_id:
                    continue

                q = Profile.objects.filter(role='student')

                # 1. Match by integration key
                match = None
                if ikey and ikey.startswith("codecamp_user_"):
                    try:
                        uid = int(ikey.replace("codecamp_user_", ""))
                        match = q.filter(user_id=uid).first()
                    except ValueError:
                        pass

                # 2. Match by already set external_attendance_id
                if not match:
                    match = q.filter(external_attendance_id=student_id).first()

                # 3. Match by exact first_name and last_name
                if not match and fn and ln:
                    match = q.filter(
                        user__first_name__iexact=fn,
                        user__last_name__iexact=ln
                    ).first()

                # 4. Match by username (e.g. yinka.ola, opeyemi.oguns)
                if not match and fn and ln:
                    normalized_user = f"{fn.lower()}.{ln.lower()}"
                    combo_user = f"{fn.lower()}{ln.lower()}"
                    match = q.filter(user__username__in=[normalized_user, combo_user]).first()

                # 5. Partial full name matching
                if not match and fn:
                    for s in q.select_related('user'):
                        full_name = s.user.get_full_name().lower()
                        if fn.lower() in full_name and (not ln or ln.lower() in full_name):
                            match = s
                            break

                if match:
                    if match.external_attendance_id != student_id:
                        match.external_attendance_id = student_id
                        match.save(update_fields=['external_attendance_id'])
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
        """
        Runs comprehensive two-way synchronization:
        1. Syncs faculty tutors.
        2. Pulls official student IDs from attendance system into CodeCampCore.
        3. Pushes/registers any students in CodeCampCore missing CDCP- IDs into the attendance system.
        4. Updates class/active status details across both systems.
        """
        db_path = cls.get_attendance_db_path()
        tutor_res = cls.sync_tutors(db_path)
        pull_student_res = cls.sync_student_ids(db_path)

        # Push / Backfill sync: ensure every single CodeCampCore student has an official CDCP- ID and attendance record
        pushed_count = 0
        students = Profile.objects.filter(role='student')
        for profile in students:
            if not profile.external_attendance_id or not profile.external_attendance_id.startswith("CDCP-"):
                cls.sync_or_register_student(profile)
                pushed_count += 1
            else:
                cls.sync_student_details_to_attendance(profile)

        return {
            "success": True,
            "db_path": db_path,
            "tutors": tutor_res,
            "students": pull_student_res,
            "pushed_students_count": pushed_count,
        }
