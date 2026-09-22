from django.db import transaction

from teencamp.models import CodingCampRegistration
from teencamp.services.attendance_sync import AttendanceSyncService


class RegistrationSyncService:
    """
    Synchronizes approved registrations that have not yet
    been synchronized with the Attendance System.
    """

    @classmethod
    @transaction.atomic
    def sync_pending(cls):

        pending = CodingCampRegistration.objects.filter(
            payment_verified=True,
            attendance_synced=False,
        ).select_related("batch")

        result = {
            "total": pending.count(),
            "success": 0,
            "failed": 0,
            "errors": [],
        }

        for registration in pending:

            try:

                response = AttendanceSyncService.sync(
                    registration
                )

                registration.sync_completed(
                    response["student_id"]
                )

                registration.save(
                    update_fields=[
                        "attendance_student_id",
                        "attendance_synced",
                        "attendance_sync_date",
                        "registration_status",
                    ]
                )

                result["success"] += 1

            except Exception as exc:

                registration.mark_sync_pending()

                registration.save(
                    update_fields=[
                        "registration_status",
                    ]
                )

                result["failed"] += 1

                result["errors"].append(
                    {
                        "registration": registration.reg_code,
                        "error": str(exc),
                    }
                )

        return result