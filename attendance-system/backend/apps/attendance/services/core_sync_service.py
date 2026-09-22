import json
import logging
import urllib.error
import urllib.request
from django.conf import settings

logger = logging.getLogger("attendance.core_sync")


class CoreAttendanceSyncService:
    """
    Synchronizes recorded check-ins and check-outs with CodeCampCore master ERP.
    Uses standard library urllib with zero external dependencies for maximum resilience.
    """

    CORE_ENDPOINT = "/api/v1/attendance/sync/"

    @classmethod
    def _send_payload(cls, payload, timeout=8):
        api_url = getattr(settings, "CORE_API_URL", "").rstrip("/")
        api_key = getattr(settings, "CORE_API_KEY", "") or getattr(settings, "ATTENDANCE_API_KEY", "")

        if not api_url or not api_key:
            return {
                "success": False,
                "skipped": True,
                "error": "CORE_API_URL or CORE_API_KEY is not configured.",
            }

        url = f"{api_url}{cls.CORE_ENDPOINT}"
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={
                "X-API-KEY": api_key,
                "Content-Type": "application/json",
                "User-Agent": "AttendanceSystem-SyncService/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body) if res_body else {}
                return {"success": True, "response": res_json}
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8") if exc.fp else str(exc)
            logger.warning(f"HTTP Error syncing attendance to Core ERP ({exc.code}): {err_body}")
            return {"success": False, "error": f"HTTP {exc.code}: {err_body}"}
        except Exception as exc:
            logger.warning(f"Failed to sync attendance to Core ERP: {exc}")
            return {"success": False, "error": str(exc)}

    @classmethod
    def sync_record(cls, attendance):
        """Pushes a single Attendance model instance to CodeCampCore."""
        student = attendance.student
        status = "Present"
        if not attendance.check_in and not attendance.check_out:
            status = "Absent"

        payload = {
            "records": [
                {
                    "external_student_id": student.student_id,
                    "student_username": student.student_id.lower(),
                    "date": attendance.date.isoformat(),
                    "status": status,
                    "check_in": attendance.check_in.strftime("%H:%M:%S") if attendance.check_in else None,
                    "check_out": attendance.check_out.strftime("%H:%M:%S") if attendance.check_out else None,
                    "source": "kiosk_qr_scanner",
                    "external_reference": f"ATT-{attendance.id}",
                }
            ]
        }
        return cls._send_payload(payload, timeout=5)

    @classmethod
    def bulk_sync(cls, queryset):
        """Pushes a queryset of Attendance records to CodeCampCore."""
        records = []
        for att in queryset.select_related("student"):
            records.append({
                "external_student_id": att.student.student_id,
                "date": att.date.isoformat(),
                "status": "Present" if att.check_in else "Absent",
                "check_in": att.check_in.strftime("%H:%M:%S") if att.check_in else None,
                "check_out": att.check_out.strftime("%H:%M:%S") if att.check_out else None,
                "source": "bulk_attendance_sync",
                "external_reference": f"ATT-{att.id}",
            })

        if not records:
            return {"success": True, "count": 0}

        res = cls._send_payload({"records": records}, timeout=15)
        if res.get("success"):
            res["count"] = len(records)
        return res
