from teencamp.models import CodingCampRegistration
from teencamp.services.attendance_sync import AttendanceSyncService


class PendingAttendanceSyncService:
    """
    Retries synchronization for registrations
    that are waiting to be synchronized.
    """

    @classmethod
    def sync_all(cls):

        pending = CodingCampRegistration.objects.filter(
            payment_verified=True,
            attendance_synced=False,
        )

        success = 0
        failed = 0

        for registration in pending:

            try:

                result = AttendanceSyncService.sync(
                    registration
                )

                registration.sync_completed(
                    result["student_id"]
                )

                registration.save(
                    update_fields=[
                        "attendance_student_id",
                        "attendance_synced",
                        "attendance_sync_date",
                        "registration_status",
                    ]
                )

                success += 1

            except Exception as exc:

                print(
                    f"Failed Sync ({registration.reg_code}): {exc}"
                )

                registration.mark_sync_pending()

                registration.save(
                    update_fields=[
                        "registration_status",
                    ]
                )

                failed += 1

        return {
            "success": success,
            "failed": failed,
            "total": pending.count(),
        }