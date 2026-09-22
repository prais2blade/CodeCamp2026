import requests

from django.conf import settings
from django.utils import timezone


class AttendanceSyncService:
    """
    Synchronizes a CodeCamp registration with
    the Attendance System.
    """

    ENDPOINT = "/api/integration/register-student/"

    @classmethod
    def sync(cls, registration):

        payload = cls.build_payload(registration)

        response = requests.post(
            f"{settings.ATTENDANCE_API_URL}{cls.ENDPOINT}",
            json=payload,
            headers={
                "Authorization": (
                    f"Bearer {settings.ATTENDANCE_API_KEY}"
                ),
                "Content-Type": "application/json",
            },
            timeout=30,
        )

        response.raise_for_status()

        return response.json()

    @classmethod
    def build_payload(cls, registration):

        return {

            "registration_code": registration.reg_code,

            "first_name": registration.first_name,

            "last_name": registration.last_name,

            "parent_name": registration.parent_name,

            "parent_phone": registration.parent_phone,

            "parent_whatsapp": registration.parent_whatsapp,

            "parent_email": registration.parent_email,

            "relationship": registration.relationship,

            "class_name": registration.batch.name,

            "mode": registration.mode,

            "camp_year": registration.camp_year,

            "program": "Teen CodeCamp",
        }