import secrets

from django.db import IntegrityError, models, transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.attendance.models import Attendance
from apps.notifications.onboarding import send_parent_onboarding_email
from apps.students.models import (
    Announcement,
    Parent,
    Student,
    StudentParent,
    TeachingClass,
)


class RegistrationIntegrationService:
    """
    Handles all student registrations regardless of source.

    Supported sources:

    - HTML Registration
    - Excel Import
    - CodeCamp Integration

    Responsibilities:

    - Validate payload
    - Create or reuse Parent
    - Synchronize Parent details
    - Create Student
    - Link Parent to Student

    Student remains responsible for:

    - Student ID generation
    - QR Code generation
    - Portal Token generation
    """

    REQUIRED_FIELDS = (
        "first_name",
        "last_name",
        "class_name",
        "parent_name",
        "parent_phone",
        "relationship",
    )

    @classmethod
    @transaction.atomic
    def register(cls, data):
        """
        Register a student from any supported source.

        Returns
        -------
        {
            "student": Student,
            "parent": Parent,
            "temporary_password": str | None,
            "parent_created": bool,
        }
        """

        data = cls.normalize_payload(data)

        cls.validate_payload(data)

        parent, temporary_password, parent_created = cls.get_or_create_parent(data)

        student, student_created = cls.get_or_create_student(
            data=data,
            parent=parent,
        )

        relationship = cls.link_parent(
            parent=parent,
            student=student,
            relationship=data["relationship"],
        )

        if parent_created and temporary_password:
            base_url = data.get("_base_url") or data.get("base_url")

            transaction.on_commit(
                lambda: send_parent_onboarding_email(
                    parent=parent,
                    temporary_password=temporary_password,
                    student=student,
                    base_url=base_url,
                )
            )

        return {
            "student": student,
            "parent": parent,
            "relationship": relationship,
            "temporary_password": temporary_password,
            "parent_created": parent_created,
            "student_created": student_created,
        }

    # =====================================================
    # Validation
    # =====================================================

    @classmethod
    def normalize_payload(cls, data):
        normalized = dict(data)

        for key, value in list(normalized.items()):
            if isinstance(value, str):
                normalized[key] = value.strip()

        if not normalized.get("class_name") and normalized.get("batch"):
            normalized["class_name"] = normalized["batch"]

        if not normalized.get("relationship"):
            normalized["relationship"] = "Guardian"

        if normalized.get("parent_phone"):
            normalized["parent_phone"] = cls.normalize_phone(
                normalized["parent_phone"]
            )

        integration_key = (
            normalized.get("integration_key")
            or normalized.get("registration_code")
            or normalized.get("external_id")
            or ""
        )
        normalized["integration_key"] = integration_key.strip() or None

        return normalized

    @staticmethod
    def normalize_phone(phone_number):
        return (
            str(phone_number)
            .strip()
            .replace(" ", "")
            .replace("-", "")
        )

    @classmethod
    def validate_payload(cls, data):
        missing = [field for field in cls.REQUIRED_FIELDS if not data.get(field)]

        if missing:
            raise ValueError(f"Missing required field(s): {', '.join(missing)}")

    # =====================================================
    # Parent
    # =====================================================

    @classmethod
    def get_or_create_parent(cls, data):
        parent = Parent.objects.filter(
            phone_number=data["parent_phone"],
        ).first()

        if parent:
            updated = False

            parent_title = data.get("parent_title", "")

            if parent_title and parent.title != parent_title:
                parent.title = parent_title
                updated = True

            if parent.full_name != data["parent_name"]:
                parent.full_name = data["parent_name"]
                updated = True

            whatsapp = data.get("parent_whatsapp", "")

            if parent.whatsapp_number != whatsapp:
                parent.whatsapp_number = whatsapp
                updated = True

            email = data.get("parent_email", "")

            if parent.email != email:
                parent.email = email
                updated = True

            if updated:
                parent.save(
                    update_fields=[
                        "title",
                        "full_name",
                        "whatsapp_number",
                        "email",
                    ]
                )

            return parent, None, False

        temporary_password = secrets.token_urlsafe(8)

        parent = Parent(
            title=data.get("parent_title", ""),
            full_name=data["parent_name"],
            phone_number=data["parent_phone"],
            whatsapp_number=data.get("parent_whatsapp", ""),
            email=data.get("parent_email", ""),
        )

        parent.set_password(temporary_password)
        parent.save()

        return parent, temporary_password, True

    # =====================================================
    # Student
    # =====================================================

    @classmethod
    def get_or_create_student(cls, data, parent):
        integration_key = data.get("integration_key")

        student = cls.find_existing_student(
            data=data,
            parent=parent,
            integration_key=integration_key,
        )

        if student:
            cls.sync_student_fields(
                student=student,
                data=data,
                parent=parent,
            )
            return student, False

        return cls.create_student(
            data=data,
            parent=parent,
        )

    @classmethod
    def find_existing_student(cls, data, parent, integration_key=None):
        if integration_key:
            student = (
                Student.objects.select_for_update()
                .filter(integration_key=integration_key)
                .first()
            )

            if student:
                return student

        candidates = (
            Student.objects.select_for_update()
            .filter(
                first_name__iexact=data["first_name"],
                last_name__iexact=data["last_name"],
                class_name__iexact=data["class_name"],
                parents__parent=parent,
            )
            .order_by("id")
        )

        date_of_birth = data.get("date_of_birth")

        if date_of_birth:
            candidates = candidates.filter(
                date_of_birth=date_of_birth,
            )

        return candidates.first()

    @classmethod
    def sync_student_fields(cls, student, data, parent):
        fields_to_update = []

        field_values = {
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "class_name": data["class_name"],
            "parent_name": parent.full_name,
        }

        integration_key = data.get("integration_key")

        if integration_key and student.integration_key != integration_key:
            field_values["integration_key"] = integration_key

        teaching_class = cls.get_teaching_class(data)

        if teaching_class and student.teaching_class_id != teaching_class.id:
            student.teaching_class = teaching_class
            fields_to_update.append("teaching_class")
            field_values["class_name"] = teaching_class.name

        for optional_field in (
            "date_of_birth",
            "gender",
        ):
            if optional_field in data:
                field_values[optional_field] = data.get(optional_field)

        if data.get("photo"):
            field_values["photo"] = data["photo"]

        for field, value in field_values.items():
            if getattr(student, field) != value:
                setattr(student, field, value)
                fields_to_update.append(field)

        if fields_to_update:
            student.save(
                update_fields=sorted(set(fields_to_update)),
            )

        return student

    @classmethod
    def create_student(cls, data, parent):
        """
        Create a new student.

        The Student model remains responsible for:

        - Student ID generation
        - QR Code generation
        - Portal Token generation
        """

        student = Student(
            first_name=data["first_name"],
            last_name=data["last_name"],
            class_name=data["class_name"],
            parent_name=parent.full_name,
            integration_key=data.get("integration_key"),
        )

        teaching_class = cls.get_teaching_class(data)

        if teaching_class:
            student.teaching_class = teaching_class
            student.class_name = teaching_class.name

        if "date_of_birth" in data:
            student.date_of_birth = data.get("date_of_birth")

        if "gender" in data:
            student.gender = data.get("gender", "")

        if data.get("photo"):
            student.photo = data["photo"]

        created = True

        try:
            with transaction.atomic():
                student.save()
        except IntegrityError:
            if not data.get("integration_key"):
                raise

            student = Student.objects.select_for_update().get(
                integration_key=data["integration_key"],
            )
            cls.sync_student_fields(
                student=student,
                data=data,
                parent=parent,
            )
            created = False

        return student, created

    @classmethod
    def get_teaching_class(cls, data):
        teaching_class = data.get("teaching_class")

        if teaching_class:
            return teaching_class

        return TeachingClass.objects.filter(
            name__iexact=data["class_name"],
            is_active=True,
        ).first()

    # =====================================================
    # Relationship
    # =====================================================

    @classmethod
    def link_parent(
        cls,
        parent,
        student,
        relationship,
    ):
        """
        Create the Parent to Student relationship.

        This operation is idempotent. If the relationship
        already exists, it is updated when necessary.
        """

        relation = StudentParent.objects.filter(
            parent=parent,
            student=student,
        ).order_by("id").first()

        if not relation:
            relation = StudentParent.objects.filter(
                student=student,
            ).order_by("id").first()

        if not relation:
            relation = StudentParent(
                parent=parent,
                student=student,
            )

        fields_to_update = []

        if relation.parent_id != parent.id:
            relation.parent = parent
            fields_to_update.append("parent")

        if relation.relationship != relationship:
            relation.relationship = relationship
            fields_to_update.append("relationship")

        if relation.teaching_class_id != getattr(student, "teaching_class_id", None):
            relation.teaching_class = student.teaching_class
            fields_to_update.append("teaching_class")

        if relation.pk:
            if fields_to_update:
                relation.save(
                    update_fields=fields_to_update,
                )
        else:
            relation.save()

        StudentParent.objects.filter(
            student=student,
        ).exclude(pk=relation.pk).delete()

        student_updates = []

        if student.parent_name != parent.full_name:
            student.parent_name = parent.full_name
            student_updates.append("parent_name")

        if student_updates:
            student.save(
                update_fields=student_updates,
            )

        return relation

    @classmethod
    def sync_parent_for_student(cls, student, data):
        data = cls.normalize_payload(data)

        if not data.get("parent_name") and not data.get("parent_phone"):
            return None

        parent, _, _ = cls.get_or_create_parent(data)

        return cls.link_parent(
            parent=parent,
            student=student,
            relationship=data.get("relationship") or "Guardian",
        )


class ParentLoginService:
    """
    Handles Parent authentication.

    Responsibilities:

    - Authenticate Parent
    - Verify Password
    - Generate JWT Tokens
    - Update Last Login
    """

    @classmethod
    def login(cls, phone_number, password):
        parent = cls.get_parent(phone_number)

        cls.validate_parent(parent)
        cls.validate_password(parent, password)

        parent.update_last_login()

        refresh = RefreshToken()
        refresh["parent_id"] = parent.id
        refresh["phone"] = parent.phone_number

        return {
            "parent": parent,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "must_change_password": parent.must_change_password,
        }

    # ==========================================
    # Parent
    # ==========================================

    @classmethod
    def get_parent(cls, phone_number):
        return Parent.objects.filter(
            phone_number=phone_number,
        ).first()

    @classmethod
    def validate_parent(cls, parent):
        if parent is None:
            raise ValueError("Invalid phone number or password.")

        if not parent.is_active:
            raise ValueError("Parent account has been disabled.")

    # ==========================================
    # Password
    # ==========================================

    @classmethod
    def validate_password(cls, parent, password):
        if not parent.check_password(password):
            raise ValueError("Invalid phone number or password.")


class ParentPasswordService:
    """
    Handles parent password management.

    Responsibilities:

    - Verify current password
    - Validate new password
    - Update password
    - Clear first-login requirement
    """

    MIN_PASSWORD_LENGTH = 8

    @classmethod
    @transaction.atomic
    def change_password(
        cls,
        parent,
        current_password,
        new_password,
        confirm_password,
    ):
        cls.validate_current_password(
            parent,
            current_password,
        )

        cls.validate_new_password(
            new_password,
            confirm_password,
        )

        parent.set_password(new_password)
        parent.must_change_password = False
        parent.last_password_change = timezone.now()

        parent.save(
            update_fields=[
                "password",
                "must_change_password",
                "last_password_change",
            ]
        )

        return parent

    # ==========================================
    # Validation
    # ==========================================

    @classmethod
    def validate_current_password(
        cls,
        parent,
        current_password,
    ):
        if not parent.check_password(current_password):
            raise ValueError("Current password is incorrect.")

    @classmethod
    def validate_new_password(
        cls,
        new_password,
        confirm_password,
    ):
        if new_password != confirm_password:
            raise ValueError("Passwords do not match.")

        if len(new_password) < cls.MIN_PASSWORD_LENGTH:
            raise ValueError("Password must contain at least 8 characters.")

        if new_password.strip() == "":
            raise ValueError("Password cannot be empty.")


class ParentDashboardService:
    """
    Builds the Parent Dashboard.

    Responsibilities:

    - Parent Profile
    - Children
    - Today's Attendance
    - Attendance Summary
    """

    @classmethod
    def get_dashboard(cls, parent):
        today = timezone.localdate()

        relationships = (
            StudentParent.objects.select_related("student")
            .filter(parent=parent)
        )

        children = []
        present_today = 0
        absent_today = 0

        for relation in relationships:
            student = relation.student

            attendance = Attendance.objects.filter(
                student=student,
                date=today,
            ).first()

            is_present = attendance is not None

            if is_present:
                present_today += 1
            else:
                absent_today += 1

            children.append(
                {
                    "id": student.id,
                    "student_id": student.student_id,
                    "first_name": student.first_name,
                    "last_name": student.last_name,
                    "class_name": student.class_name,
                    "relationship": relation.relationship,
                    "present_today": is_present,
                }
            )

        return {
            "parent": {
                "id": parent.id,
                "title": parent.title,
                "full_name": parent.full_name,
                "phone_number": parent.phone_number,
                "email": parent.email,
            },
            "summary": {
                "children": len(children),
                "present_today": present_today,
                "absent_today": absent_today,
            },
            "children": children,
        }


class ParentChildService:
    """
    Handles Parent access to child information.

    Responsibilities:

    - Verify ownership
    - Student profile
    - Attendance history
    - Attendance statistics
    """

    @classmethod
    def get_child(
        cls,
        parent,
        student_id,
    ):
        """
        Return a complete child profile for the authenticated parent.
        """

        relationship = (
            StudentParent.objects.select_related("student")
            .filter(
                parent=parent,
                student__student_id=student_id,
            )
            .first()
        )

        if relationship is None:
            raise ValueError("Student not found.")

        student = relationship.student

        attendance_history = Attendance.objects.filter(
            student=student,
        ).order_by(
            "-date",
            "-check_in",
        )

        total_days = attendance_history.count()
        present_days = attendance_history.filter(check_in__isnull=False).count()
        absent_days = 0
        late_days = 0

        attendance_rate = 0

        if total_days:
            attendance_rate = round(
                (present_days / total_days) * 100,
                2,
            )

        return {
            "student": {
                "id": student.id,
                "student_id": student.student_id,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "photo": student.photo.url if student.photo else None,
                "class_name": student.class_name,
                "gender": student.gender,
                "date_of_birth": student.date_of_birth,
                "relationship": relationship.relationship,
            },
            "statistics": {
                "attendance_rate": attendance_rate,
                "total_days": total_days,
                "present_days": present_days,
                "absent_days": absent_days,
                "late_days": late_days,
            },
            "attendance_history": attendance_history,
            "student": student,
            "relationship": relationship,
            "statistics": {
                "total_days": total_days,
                "present_days": present_days,
                "absent_days": absent_days,
                "attendance_rate": attendance_rate,
            },
        }


class ParentProfileService:
    """
    Handles Parent profile operations.

    Responsibilities:

    - View profile
    - Update profile
    - Notification preferences
    """

    EDITABLE_FIELDS = (
        "title",
        "full_name",
        "email",
        "whatsapp_number",
        "receive_email",
        "receive_whatsapp",
    )

    @classmethod
    def get_profile(cls, parent):
        """
        Return the authenticated parent's profile.
        """

        return {
            "id": parent.id,
            "title": parent.title,
            "full_name": parent.full_name,
            "phone_number": parent.phone_number,
            "email": parent.email,
            "whatsapp_number": parent.whatsapp_number,
            "receive_email": parent.receive_email,
            "receive_whatsapp": parent.receive_whatsapp,
            "must_change_password": parent.must_change_password,
            "last_login_at": parent.last_login_at,
            "last_password_change": parent.last_password_change,
        }

    @classmethod
    def update_profile(
        cls,
        parent,
        data,
    ):
        """
        Update editable profile fields.
        """

        for field in cls.EDITABLE_FIELDS:
            if field in data:
                setattr(
                    parent,
                    field,
                    data[field],
                )

        parent.save(
            update_fields=list(cls.EDITABLE_FIELDS)
        )

        return parent


class TimelineService:
    """
    Build the parent timeline by aggregating events from different modules.
    """

    @classmethod
    def get_timeline(
        cls,
        parent,
        limit=50,
    ):
        events = []

        events.extend(
            cls.get_attendance_events(
                parent,
            )
        )

        events.extend(
            cls.get_announcement_events(
                parent,
            )
        )

        events.sort(
            key=lambda event: event["timestamp"],
            reverse=True,
        )

        return events[:limit]

    # ==========================================
    # Attendance
    # ==========================================

    @classmethod
    def get_attendance_events(
        cls,
        parent,
    ):
        events = []

        relationships = (
            StudentParent.objects.select_related("student")
            .filter(parent=parent)
        )

        for relationship in relationships:
            attendances = Attendance.objects.filter(
                student=relationship.student,
            ).order_by(
                "-date",
                "-check_in",
            )[:20]

            for attendance in attendances:
                student = relationship.student

                events.append(
                    {
                        "type": "ATTENDANCE",
                        "timestamp": attendance.date,
                        "student": (
                            student.full_name
                            if hasattr(student, "full_name")
                            else f"{student.first_name} {student.last_name}".strip()
                        ),
                        "title": "Attendance Recorded",
                        "description": (
                            f"{student.first_name} was marked {attendance.status}."
                        ),
                    }
                )

        return events

    # ==========================================
    # Announcements
    # ==========================================

    @classmethod
    def get_announcement_events(
        cls,
        parent,
    ):
        today = timezone.now()

        announcements = (
            Announcement.objects.filter(
                is_active=True,
            )
            .filter(
                models.Q(
                    expires_at__isnull=True,
                )
                | models.Q(
                    expires_at__gte=today,
                )
            )
            .order_by(
                "-publish_at",
            )
        )

        events = []

        for announcement in announcements:
            events.append(
                {
                    "type": "ANNOUNCEMENT",
                    "timestamp": announcement.publish_at,
                    "title": announcement.title,
                    "description": announcement.message,
                    "attachment": (
                        announcement.attachment.url
                        if announcement.attachment
                        else None
                    ),
                }
            )

        return events
