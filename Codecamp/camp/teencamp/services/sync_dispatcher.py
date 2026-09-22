import logging
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("teencamp.sync")


class SyncDispatcher:
    """
    Coordinates outbound synchronization of student registrations
    to satellite/core systems (attendance-system and CodeCampCore).
    """

    ATTENDANCE_ENDPOINT = "/api/integration/register-student/"
    CORE_ENROLLMENT_ENDPOINT = "/api/v1/enrollment/sync/"

    @classmethod
    def sync_to_attendance(cls, registration):
        """Pushes student to attendance-system for QR code & kiosk generation."""
        api_url = getattr(settings, "ATTENDANCE_API_URL", "").rstrip("/")
        api_key = getattr(settings, "ATTENDANCE_API_KEY", "")

        if not api_url or not api_key:
            return {
                "success": False,
                "skipped": True,
                "error": "ATTENDANCE_API_URL or ATTENDANCE_API_KEY is not configured.",
            }

        payload = {
            "registration_code": registration.reg_code,
            "first_name": registration.first_name,
            "last_name": registration.last_name,
            "parent_name": registration.parent_name,
            "parent_phone": registration.parent_phone,
            "parent_whatsapp": registration.parent_whatsapp,
            "parent_email": registration.parent_email,
            "relationship": registration.relationship,
            "class_name": registration.batch.name if registration.batch else "Unassigned",
            "mode": registration.mode,
            "camp_year": registration.camp_year,
            "program": "Teen CodeCamp",
        }

        try:
            response = requests.post(
                f"{api_url}{cls.ATTENDANCE_ENDPOINT}",
                json=payload,
                headers={
                    "X-API-KEY": api_key,
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return {
                "success": True,
                "student_id": data.get("student_id") or data.get("id"),
                "raw": data,
            }
        except Exception as exc:
            logger.warning(f"Attendance sync failed for {registration.reg_code}: {exc}")
            return {
                "success": False,
                "error": str(exc),
            }

    @classmethod
    def sync_to_core_erp(cls, registration):
        """Pushes student to CodeCampCore master academy portal."""
        api_url = getattr(settings, "CORE_API_URL", "").rstrip("/")
        api_key = getattr(settings, "CORE_API_KEY", "") or getattr(settings, "REGISTRATION_API_KEY", "")

        if not api_url or not api_key:
            return {
                "success": False,
                "skipped": True,
                "error": "CORE_API_URL or CORE_API_KEY is not configured.",
            }

        payload = {
            "registration_code": registration.reg_code,
            "first_name": registration.first_name,
            "last_name": registration.last_name,
            "email": registration.parent_email,
            "phone": registration.parent_phone,
            "course_name": "Teen CodeCamp",
            "batch_name": registration.batch.name if registration.batch else None,
            "external_attendance_id": registration.attendance_student_id or registration.reg_code,
            "parent": {
                "name": registration.parent_name,
                "phone": registration.parent_phone,
                "whatsapp": registration.parent_whatsapp,
                "email": registration.parent_email,
                "relationship": registration.relationship,
            },
            "payment": {
                "amount_paid": float(registration.price_paid),
                "status": "paid" if registration.payment_verified else "pending",
                "reference": registration.reference,
            },
        }

        try:
            response = requests.post(
                f"{api_url}{cls.CORE_ENROLLMENT_ENDPOINT}",
                json=payload,
                headers={
                    "X-API-KEY": api_key,
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return {
                "success": True,
                "user_id": data.get("user_id"),
                "profile_id": data.get("profile_id"),
                "raw": data,
            }
        except Exception as exc:
            logger.warning(f"CodeCampCore sync failed for {registration.reg_code}: {exc}")
            return {
                "success": False,
                "error": str(exc),
            }

    @classmethod
    def dispatch_all(cls, registration):
        """
        Dispatches registration data to all integrated systems.
        Updates registration sync flags safely.
        """
        attendance_res = cls.sync_to_attendance(registration)
        if attendance_res.get("success") and attendance_res.get("student_id"):
            registration.attendance_student_id = str(attendance_res["student_id"])
            registration.attendance_synced = True
            registration.attendance_sync_date = timezone.now()

        core_res = cls.sync_to_core_erp(registration)

        all_synced = attendance_res.get("success") and core_res.get("success")
        if all_synced:
            registration.registration_status = "COMPLETED"
        elif attendance_res.get("success") or core_res.get("success"):
            registration.registration_status = "SYNC_PENDING"
        else:
            registration.registration_status = "SYNC_PENDING"

        registration.save(
            update_fields=[
                "attendance_student_id",
                "attendance_synced",
                "attendance_sync_date",
                "registration_status",
            ]
        )

        return {
            "attendance": attendance_res,
            "core": core_res,
            "all_synced": all_synced,
        }
