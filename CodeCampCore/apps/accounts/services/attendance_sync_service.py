import os
import shutil
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
from apps.accounts.models import Profile, Parent

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
            "/var/www/codecamp2026/attendance-system/backend/db.sqlite3",
            "/var/www/attendance-system/backend/db.sqlite3",
            "/var/www/attendance/backend/db.sqlite3",
            "/var/www/codecamp2026/attendance/backend/db.sqlite3",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    @classmethod
    def get_attendance_media_path(cls, db_path=None):
        """Locates the primary media directory of the attendance system containing photos and QR codes."""
        dirs = cls.get_all_attendance_media_dirs(db_path)
        return dirs[0] if dirs else None

    @classmethod
    def get_all_attendance_media_dirs(cls, db_path=None):
        """Returns all potential media directories for the attendance system in priority order."""
        dirs = []
        env_media = getattr(settings, "ATTENDANCE_MEDIA_PATH", os.getenv("ATTENDANCE_MEDIA_PATH", ""))
        if env_media and os.path.exists(env_media):
            dirs.append(env_media)

        if db_path:
            cand = os.path.join(os.path.dirname(db_path), "media")
            if os.path.exists(cand) and cand not in dirs:
                dirs.append(cand)
            cand2 = os.path.join(os.path.dirname(os.path.dirname(db_path)), "media")
            if os.path.exists(cand2) and cand2 not in dirs:
                dirs.append(cand2)

        candidates = [
            "/var/www/codecamp2026/attendance-system/backend/media",
            "/var/www/codecamp2026/attendance-system/media",
            "/var/www/attendance-system/backend/media",
            "/var/www/attendance-system/media",
            "/var/www/attendance/backend/media",
            "/var/www/attendance/media",
            "/var/www/codecamp/attendance-system/backend/media",
            "/var/www/codecamp2026/media",
            "C:/Projects/attendance-system/backend/media",
            "c:/Projects/attendance-system/backend/media",
            "C:/Projects/codecamp2026/attendance-system/backend/media",
            "c:/Projects/codecamp2026/attendance-system/backend/media",
            os.path.join(settings.BASE_DIR.parent, "attendance-system", "backend", "media"),
            os.path.join(settings.BASE_DIR.parent, "attendance-system", "media"),
            str(settings.BASE_DIR / "media"),
        ]
        for p in candidates:
            if os.path.exists(p) and p not in dirs:
                dirs.append(p)
        return dirs

    @classmethod
    def find_student_photo_file(cls, student_id, first_name=None, last_name=None, db_photo=None, db_path=None):
        """
        Exhaustively scans all attendance media directories for the student's passport photo.
        Checks:
        1. Explicit DB photo path (if non-empty)
        2. Exact student_id file (CDCP_000001.jpeg/png/jpg, CDCP-000001.jpg)
        3. Numeric student suffix (000001.jpg, 1.jpeg)
        4. Student full name (first_last.jpg)
        5. Student first name (Diamond.jpeg, Favour.jpeg, Anuoluwapo.jpeg)
        6. Student last name
        """
        clean_sid = (student_id or "").replace("-", "_").strip()
        sid_num = clean_sid.split("_")[-1] if "_" in clean_sid else ""
        fn = (first_name or "").strip().lower()
        ln = (last_name or "").strip().lower()

        media_roots = cls.get_all_attendance_media_dirs(db_path)

        for m_root in media_roots:
            # 1. Direct db_photo lookup
            if db_photo:
                rel = db_photo.lstrip("/").replace("\\", "/")
                for candidate in [
                    os.path.join(m_root, rel),
                    os.path.join(m_root, "students", "photos", os.path.basename(rel)),
                    os.path.join(m_root, "photos", os.path.basename(rel)),
                    os.path.join(m_root, os.path.basename(rel)),
                ]:
                    if os.path.isfile(candidate):
                        return candidate

            search_subdirs = [
                os.path.join(m_root, "students", "photos"),
                os.path.join(m_root, "photos"),
                os.path.join(m_root, "students"),
                m_root,
            ]

            for s_dir in search_subdirs:
                if not os.path.isdir(s_dir):
                    continue
                try:
                    for fname in os.listdir(s_dir):
                        f_path = os.path.join(s_dir, fname)
                        if not os.path.isfile(f_path):
                            continue
                        name_no_ext = os.path.splitext(fname)[0]
                        name_lower = name_no_ext.lower()

                        # ID match (e.g. CDCP_000001 or CDCP-000001)
                        if clean_sid and (name_lower == clean_sid.lower() or name_lower == (student_id or "").lower().replace("-", "")):
                            return f_path
                        # Number suffix match (e.g. 000001 or 1)
                        if sid_num and (name_no_ext == sid_num or (sid_num.isdigit() and name_no_ext == str(int(sid_num)))):
                            return f_path
                        # Full name match (first_last)
                        if fn and ln and (name_lower == f"{fn}_{ln}" or name_lower == f"{fn}{ln}"):
                            return f_path
                        # First name match (e.g. Diamond, Favour, Anuoluwapo)
                        if fn and len(fn) > 2 and name_lower == fn:
                            return f_path
                        # Last name match
                        if ln and len(ln) > 2 and name_lower == ln:
                            return f_path
                except Exception:
                    continue

        return None

    @classmethod
    def _get_or_create_student_profile(cls, student_id, first_name, last_name, class_name=None, email=None, phone=None):
        """
        Locates or creates a CodeCampCore Profile (and User) for a student from attendance-system.
        Guarantees that all 55 students exist in CodeCampCore with role='student' and official CDCP- ID.
        """
        from django.utils.text import slugify
        from apps.courses.models import Course
        from apps.scheduling.models import Batch
        from apps.tenants.models import Tenant

        fn = (first_name or "").strip()
        ln = (last_name or "").strip()
        student_id = (student_id or "").strip()
        q = Profile.objects.filter(role="student")
        profile = None

        # 1. Match by external_attendance_id
        if student_id:
            profile = q.filter(external_attendance_id__iexact=student_id).first()
            if not profile:
                clean_sid = student_id.replace("-", "").upper()
                for p_check in q.exclude(external_attendance_id=""):
                    if p_check.external_attendance_id and p_check.external_attendance_id.replace("-", "").upper() == clean_sid:
                        profile = p_check
                        break

        # 2. Match by exact first and last name
        if not profile and fn and ln:
            profile = q.filter(user__first_name__iexact=fn, user__last_name__iexact=ln).first()

        # 3. Match by normalized username
        if not profile and fn and ln:
            clean_first = slugify(fn).replace("-", "")
            clean_last = slugify(ln).replace("-", "")
            if clean_first and clean_last:
                profile = q.filter(user__username__in=[f"{clean_first}.{clean_last}", f"{clean_first}{clean_last}"]).first()

        # 4. Partial name match
        if not profile and fn:
            for s in q.select_related("user"):
                full_name = s.user.get_full_name().lower()
                if fn.lower() in full_name and (not ln or ln.lower() in full_name):
                    profile = s
                    break

        if profile:
            updated = False
            if student_id and profile.external_attendance_id != student_id:
                profile.external_attendance_id = student_id
                updated = True
            if fn and not profile.user.first_name:
                profile.user.first_name = fn
                profile.user.save(update_fields=['first_name'])
            if ln and not profile.user.last_name:
                profile.user.last_name = ln
                profile.user.save(update_fields=['last_name'])
            if updated:
                profile.save(update_fields=['external_attendance_id'])
            return profile, False

        # Create new student User + Profile
        clean_first = slugify(fn).replace("-", "")
        clean_last = slugify(ln).replace("-", "")
        if clean_first and clean_last:
            username_candidate = f"{clean_first}.{clean_last}"
        elif clean_first:
            username_candidate = clean_first
        else:
            clean_sid = student_id.lower().replace("-", "")
            username_candidate = f"student_{clean_sid}"

        unique_username = username_candidate
        counter = 1
        while User.objects.filter(username__iexact=unique_username).exists():
            unique_username = f"{username_candidate}{counter}"
            counter += 1

        clean_sid = student_id.lower().replace("-", "")
        final_email = email
        if not final_email or User.objects.filter(email__iexact=final_email).exists():
            final_email = f"{clean_sid}@student.codecamp.com.ng"

        user = User.objects.create_user(
            username=unique_username,
            email=final_email,
            password="CodeCamp@2026",
            first_name=fn,
            last_name=ln,
        )

        tenant = Tenant.objects.filter(is_default=True).first() or Tenant.objects.first()

        # Resolve Course
        target_course = None
        c_name = (class_name or "").lower()
        if "summer" in c_name or "innovator" in c_name or "teen" in c_name or "young" in c_name or "beginner" in c_name:
            target_course = Course.objects.filter(name__icontains="innovator").first()
        elif "python" in c_name or "advance" in c_name:
            target_course = Course.objects.filter(name__icontains="python").first()
        elif "data" in c_name:
            target_course = Course.objects.filter(name__icontains="data").first()
        elif "web" in c_name:
            target_course = Course.objects.filter(name__icontains="web").first()

        if not target_course:
            target_course = Course.objects.filter(is_published=True).first() or Course.objects.first()

        target_batch = None
        if target_course:
            target_batch = Batch.objects.filter(course=target_course, is_published=True).first()

        profile, _ = Profile.objects.get_or_create(
            user=user,
            defaults={
                'role': 'student',
                'external_attendance_id': student_id,
                'phone': phone or "",
                'tenant': tenant,
                'course': target_course,
                'batch': target_batch,
                'is_verified': True,
                'is_approved': True,
                'onboarding_stage': 'finished',
            }
        )

        return profile, True

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
    def sync_parents(cls, db_path=None, connection=None):
        """
        Pulls registered parent/guardian records from the attendance system
        and links them to their respective student Profiles in CodeCampCore.
        Supports SQLite (via path or connection) and PostgreSQL (via connection).
        """
        should_close = False
        conn = connection
        if conn is None:
            db_path = db_path or cls.get_attendance_db_path()
            if not db_path or not os.path.exists(db_path):
                return {"count": 0, "error": "Attendance database not found"}
            try:
                conn = sqlite3.connect(db_path, timeout=5)
                should_close = True
            except Exception as exc:
                return {"count": 0, "error": str(exc)}

        parents_created = 0
        parents_linked = 0
        students_matched = 0
        updated_roster = []

        try:
            cursor = conn.cursor()
            query = """
                SELECT 
                    s.id as student_row_id,
                    s.student_id,
                    s.first_name,
                    s.last_name,
                    s.parent_name,
                    p.id as parent_id,
                    p.title,
                    p.full_name,
                    p.phone_number,
                    p.whatsapp_number,
                    p.email,
                    sp.relationship
                FROM students_student s
                LEFT JOIN students_studentparent sp ON s.id = sp.student_id
                LEFT JOIN students_parent p ON sp.parent_id = p.id
                ORDER BY s.id ASC
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for row in rows:
                if isinstance(row, dict):
                    student_row_id = row.get("student_row_id")
                    student_id = row.get("student_id")
                    fn = row.get("first_name")
                    ln = row.get("last_name")
                    s_parent_name = row.get("parent_name")
                    p_id = row.get("parent_id")
                    p_title = row.get("title")
                    p_full_name = row.get("full_name")
                    p_phone = row.get("phone_number")
                    p_whatsapp = row.get("whatsapp_number")
                    p_email = row.get("email")
                    sp_rel = row.get("relationship")
                else:
                    (student_row_id, student_id, fn, ln, s_parent_name,
                     p_id, p_title, p_full_name, p_phone, p_whatsapp, p_email, sp_rel) = row

                fn = (fn or "").strip()
                ln = (ln or "").strip()
                student_id = (student_id or "").strip()

                # Find student profile in CodeCampCore
                q = Profile.objects.filter(role="student")
                profile = None

                # 1. Match by external_attendance_id
                if student_id:
                    profile = q.filter(external_attendance_id__iexact=student_id).first()

                # 2. Match by names
                if not profile and fn and ln:
                    profile = q.filter(user__first_name__iexact=fn, user__last_name__iexact=ln).first()

                # 3. Match by username
                if not profile and fn and ln:
                    normalized_user = f"{fn.lower()}.{ln.lower()}"
                    combo_user = f"{fn.lower()}{ln.lower()}"
                    profile = q.filter(user__username__in=[normalized_user, combo_user]).first()

                # 4. Partial full name matching
                if not profile and fn:
                    for s in q.select_related("user"):
                        full_name = s.user.get_full_name().lower()
                        if fn.lower() in full_name and (not ln or ln.lower() in full_name):
                            profile = s
                            break

                if not profile:
                    profile, _ = cls._get_or_create_student_profile(
                        student_id=student_id,
                        first_name=fn,
                        last_name=ln,
                        email=p_email,
                        phone=p_phone
                    )

                students_matched += 1

                # Normalize parent information
                effective_name = (p_full_name or s_parent_name or "").strip()
                effective_phone = (p_phone or profile.phone or "").strip()
                effective_whatsapp = (p_whatsapp or effective_phone or "").strip()
                effective_email = (p_email or "").strip().lower()
                effective_title = (p_title or "Mr").strip().replace(".", "").title()
                allowed_titles = {'Mr', 'Mrs', 'Ms', 'Dr', 'Engr', 'Chief', 'Pastor', 'Alhaji', 'Hajiya'}
                if effective_title not in allowed_titles:
                    effective_title = "Mr"

                effective_rel = (sp_rel or "Guardian").strip().capitalize()
                allowed_rels = {'Father', 'Mother', 'Guardian', 'Sponsor', 'Self'}
                if effective_rel not in allowed_rels:
                    if 'dad' in effective_rel.lower() or 'father' in effective_rel.lower():
                        effective_rel = 'Father'
                    elif 'mom' in effective_rel.lower() or 'mother' in effective_rel.lower():
                        effective_rel = 'Mother'
                    else:
                        effective_rel = 'Guardian'

                if not effective_name and not effective_phone:
                    continue

                # Locate or create Parent in CodeCampCore
                parent_obj = None
                if effective_phone:
                    parent_obj = Parent.objects.filter(phone_number=effective_phone).first()

                if not parent_obj and effective_email:
                    parent_obj = Parent.objects.filter(email=effective_email).first()

                if not parent_obj and effective_name:
                    parent_obj = Parent.objects.filter(full_name__iexact=effective_name).first()

                created = False
                if not parent_obj:
                    parent_obj = Parent.objects.create(
                        title=effective_title,
                        full_name=effective_name or f"{profile.user.get_full_name() or profile.user.username} Guardian",
                        phone_number=effective_phone or f"080{profile.user.id:08d}",
                        whatsapp_number=effective_whatsapp or effective_phone,
                        email=effective_email,
                    )
                    created = True
                    parents_created += 1
                else:
                    changed = False
                    if not parent_obj.phone_number and effective_phone:
                        parent_obj.phone_number = effective_phone
                        changed = True
                    if not parent_obj.whatsapp_number and effective_whatsapp:
                        parent_obj.whatsapp_number = effective_whatsapp
                        changed = True
                    if not parent_obj.email and effective_email:
                        parent_obj.email = effective_email
                        changed = True
                    if parent_obj.title == 'Mr' and effective_title != 'Mr':
                        parent_obj.title = effective_title
                        changed = True
                    if changed:
                        parent_obj.save()

                # Link parent to profile
                if profile.parent_id != parent_obj.id or profile.relationship_to_parent != effective_rel:
                    profile.parent = parent_obj
                    profile.relationship_to_parent = effective_rel
                    profile.save(update_fields=['parent', 'relationship_to_parent'])
                    parents_linked += 1

                updated_roster.append({
                    "student_id": profile.external_attendance_id or student_id,
                    "student_name": profile.user.get_full_name() or profile.user.username,
                    "parent_name": parent_obj.full_name,
                    "parent_phone": parent_obj.phone_number,
                    "parent_email": parent_obj.email,
                    "relationship": effective_rel,
                    "created": created,
                })

            return {
                "success": True,
                "attendance_students_count": len(rows),
                "students_matched": students_matched,
                "parents_created": parents_created,
                "parents_linked": parents_linked,
                "updated_roster": updated_roster,
            }
        except Exception as exc:
            logger.error(f"Error syncing parents: {exc}")
            return {"success": False, "error": str(exc)}
        finally:
            if should_close and conn:
                try:
                    conn.close()
                except Exception:
                    pass

    @classmethod
    def sync_id_cards_and_photos(cls, db_path=None, connection=None):
        """
        Pulls student passport photographs, date of birth, and gender from the
        attendance system into CodeCampCore profiles, and marks
        profile.id_card_approved = True so their official CodeCamp ID Card is ready.
        """
        should_close = False
        conn = connection
        if conn is None:
            db_path = db_path or cls.get_attendance_db_path()
            if not db_path or not os.path.exists(db_path):
                return {"count": 0, "error": "Attendance database not found"}
            try:
                conn = sqlite3.connect(db_path, timeout=5)
                should_close = True
            except Exception as exc:
                return {"count": 0, "error": str(exc)}

        media_dir = cls.get_attendance_media_path(db_path)
        avatars_target_dir = os.path.join(settings.MEDIA_ROOT, "avatars")
        os.makedirs(avatars_target_dir, exist_ok=True)

        photos_synced = 0
        dob_synced = 0
        approved_count = 0
        students_matched = 0
        synced_students = []

        try:
            cursor = conn.cursor()
            query = """
                SELECT student_id, first_name, last_name, photo, qr_code, date_of_birth, gender
                FROM students_student
                ORDER BY id ASC
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for row in rows:
                if isinstance(row, dict):
                    student_id = row.get("student_id")
                    fn = row.get("first_name")
                    ln = row.get("last_name")
                    photo = row.get("photo")
                    qr_code = row.get("qr_code")
                    dob = row.get("date_of_birth")
                    gender = row.get("gender")
                else:
                    student_id, fn, ln, photo, qr_code, dob, gender = row

                fn = (fn or "").strip()
                ln = (ln or "").strip()
                student_id = (student_id or "").strip()

                q = Profile.objects.filter(role="student")
                profile = None

                if student_id:
                    profile = q.filter(external_attendance_id__iexact=student_id).first()

                if not profile and fn and ln:
                    profile = q.filter(user__first_name__iexact=fn, user__last_name__iexact=ln).first()

                if not profile and fn and ln:
                    normalized_user = f"{fn.lower()}.{ln.lower()}"
                    combo_user = f"{fn.lower()}{ln.lower()}"
                    profile = q.filter(user__username__in=[normalized_user, combo_user]).first()

                if not profile and fn:
                    for s in q.select_related("user"):
                        full_name = s.user.get_full_name().lower()
                        if fn.lower() in full_name and (not ln or ln.lower() in full_name):
                            profile = s
                            break

                if not profile:
                    profile, _ = cls._get_or_create_student_profile(
                        student_id=student_id,
                        first_name=fn,
                        last_name=ln,
                    )

                students_matched += 1
                updated_fields = []

                # 1. Sync Date of Birth
                if dob and not profile.date_of_birth:
                    try:
                        profile.date_of_birth = dob
                        updated_fields.append("date_of_birth")
                        dob_synced += 1
                    except Exception:
                        pass

                # 2. Sync Gender
                if gender and not profile.gender:
                    g_clean = gender.strip().capitalize()
                    if g_clean in ["Male", "Female"]:
                        profile.gender = g_clean
                        updated_fields.append("gender")

                # 3. Smart Photo Discovery & Sync
                photo_file = cls.find_student_photo_file(
                    student_id=student_id,
                    first_name=fn,
                    last_name=ln,
                    db_photo=photo,
                    db_path=db_path
                )
                photo_copied = False
                if photo_file and os.path.isfile(photo_file):
                    clean_sid = (profile.external_attendance_id or student_id or f"student_{profile.user.id}").replace("-", "_")
                    base_fname = os.path.basename(photo_file)
                    dest_name = f"{clean_sid}_{base_fname}"
                    dest_full = os.path.join(avatars_target_dir, dest_name)

                    try:
                        shutil.copy2(photo_file, dest_full)
                        profile.avatar = f"avatars/{dest_name}"
                        if not profile.id_card_approved:
                            profile.id_card_approved = True
                            approved_count += 1
                        updated_fields.extend(["avatar", "id_card_approved"])
                        photos_synced += 1
                        photo_copied = True
                    except Exception as copy_err:
                        logger.warning(f"Error copying student photo for {student_id}: {copy_err}")
                elif profile.has_custom_avatar:
                    if not profile.id_card_approved:
                        profile.id_card_approved = True
                        updated_fields.append("id_card_approved")
                        approved_count += 1
                else:
                    if profile.id_card_approved:
                        profile.id_card_approved = False
                        updated_fields.append("id_card_approved")

                if updated_fields:
                    profile.save(update_fields=list(set(updated_fields)))

                synced_students.append({
                    "student_id": profile.external_attendance_id or student_id,
                    "name": profile.user.get_full_name() or profile.user.username,
                    "photo_synced": photo_copied or profile.has_custom_avatar,
                    "photo_file": os.path.basename(photo_file) if photo_file else None,
                    "id_card_approved": profile.id_card_approved,
                    "date_of_birth": profile.date_of_birth,
                    "gender": profile.gender,
                })

            return {
                "success": True,
                "attendance_students_count": len(rows),
                "students_matched": students_matched,
                "photos_synced": photos_synced,
                "approved_count": approved_count,
                "dob_synced": dob_synced,
                "synced_students": synced_students,
            }
        except Exception as exc:
            logger.error(f"Error syncing ID cards/photos: {exc}")
            return {"success": False, "error": str(exc)}
        finally:
            if should_close and conn:
                try:
                    conn.close()
                except Exception:
                    pass

    @classmethod
    def sync_all(cls):
        """
        Runs comprehensive two-way synchronization:
        1. Syncs faculty tutors.
        2. Pulls official student IDs from attendance system into CodeCampCore.
        3. Pulls parent/guardian records and links them to students in CodeCampCore.
        4. Pulls student passport photos and enables ID cards.
        5. Pushes/registers any students in CodeCampCore missing CDCP- IDs into the attendance system.
        6. Updates class/active status details across both systems.
        """
        db_path = cls.get_attendance_db_path()
        tutor_res = cls.sync_tutors(db_path)
        pull_student_res = cls.sync_student_ids(db_path)
        parent_res = cls.sync_parents(db_path)
        id_card_res = cls.sync_id_cards_and_photos(db_path)

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
            "parents": parent_res,
            "id_cards": id_card_res,
            "pushed_students_count": pushed_count,
        }
