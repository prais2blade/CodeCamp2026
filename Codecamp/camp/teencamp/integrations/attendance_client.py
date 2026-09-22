import requests

from django.conf import settings


class AttendanceClient:
    """
    Client for communicating with the
    Attendance System Integration API.
    """

    ENDPOINT = "/api/integration/register-student/"

    @classmethod
    def register_student(cls, registration):

        payload = {

            "first_name": registration.first_name,

            "last_name": registration.last_name,

            "parent_name": registration.parent_name,

            "parent_phone": registration.parent_phone,

            "parent_whatsapp": registration.parent_whatsapp,

            "parent_email": registration.parent_email,

            "relationship": registration.relationship,

            "mode": registration.mode,

            "batch": (
                registration.batch.code
                if registration.batch
                else None
            ),

            "camp_year": registration.camp_year,
        }

        response = requests.post(

            f"{settings.ATTENDANCE_API_URL}{cls.ENDPOINT}",

            json=payload,

            headers={

                "Authorization":
                    f"Bearer {settings.ATTENDANCE_API_KEY}",

                "Content-Type":
                    "application/json",
            },

            timeout=30,
        )

        response.raise_for_status()

        return response.json()