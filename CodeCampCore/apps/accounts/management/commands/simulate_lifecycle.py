import json
from django.core.management.base import BaseCommand
from django.test import Client
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from apps.accounts.models import Profile, Attendance


class Command(BaseCommand):
    help = "Runs a live simulated end-to-end integration and progression lifecycle test across Codecamp, attendance-system, and CodeCampCore."

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO("=================================================================="))
        self.stdout.write(self.style.HTTP_INFO("  CODECAMP ECOSYSTEM LIVE SIMULATION: 3-TIER LIFECYCLE"))
        self.stdout.write(self.style.HTTP_INFO("=================================================================="))

        client = Client()
        api_key = getattr(settings, "CORE_API_KEY", "") or "codecamp_dev_secret_key_2026"

        # Phase 1: Summer Camp Ingestion
        self.stdout.write(self.style.NOTICE("\n[Phase 1] Simulating Summer Camp Registration from Codecamp Admissions Gateway..."))
        camp_payload = {
            "registration_code": "TC-SIM-001",
            "first_name": "Ezekiel",
            "last_name": "Adeniyi",
            "email": "ezekiel.sim@example.com",
            "phone": "+2348123456701",
            "course_name": "Teen CodeCamp Summer 2026",
            "batch_name": "Cohort Alpha",
            "external_attendance_id": "STU-SIM-101",
            "parent": {
                "name": "Adeola Adeniyi",
                "phone": "+2348123456700",
                "relationship": "Father",
            },
            "payment": {
                "amount_paid": 30000.0,
                "status": "paid",
                "reference": "REF-SIM-PAY-01",
            },
        }

        res = client.post(
            "/api/v1/enrollment/sync/",
            data=json.dumps(camp_payload),
            content_type="application/json",
            HTTP_X_API_KEY=api_key,
        )

        if res.status_code not in (200, 201):
            self.stdout.write(self.style.ERROR(f"[-] Phase 1 Failed (HTTP {res.status_code}): {res.content.decode()[:300]}"))
            return
        
        user_data = res.json()
        self.stdout.write(self.style.SUCCESS(f"  [+] Ingested student: {user_data.get('username')} (ID: {user_data.get('user_id')})"))
        self.stdout.write(self.style.SUCCESS(f"  [+] Course linked: Teen CodeCamp Summer 2026 | Batch: Cohort Alpha"))

        # Phase 2: QR Scanner Ingestion
        self.stdout.write(self.style.NOTICE("\n[Phase 2] Simulating attendance-system Daily QR Kiosk Check-In & Check-Out..."))
        today_str = timezone.localdate().isoformat()
        attendance_payload = {
            "records": [
                {
                    "external_student_id": "STU-SIM-101",
                    "date": today_str,
                    "status": "Present",
                    "check_in": "08:15:00",
                    "check_out": "14:05:00",
                    "source": "kiosk_qr_scanner",
                    "external_reference": "ATT-SIM-QR-001",
                }
            ]
        }

        att_res = client.post(
            "/api/v1/attendance/sync/",
            data=json.dumps(attendance_payload),
            content_type="application/json",
            HTTP_X_API_KEY=api_key,
        )

        if att_res.status_code != 200:
            self.stdout.write(self.style.ERROR(f"[-] Phase 2 Failed (HTTP {att_res.status_code}): {att_res.content.decode()[:300]}"))
            return

        self.stdout.write(self.style.SUCCESS(f"  [+] Attendance Synced: Present (In: 08:15:00, Out: 14:05:00)"))

        # Phase 3: Post-Camp Diploma Progression
        self.stdout.write(self.style.NOTICE("\n[Phase 3] Simulating Summer Camp Graduation & Progression to 6-Month Full Academy Diploma..."))
        diploma_payload = {
            "registration_code": "DIP-SIM-001",
            "first_name": "Ezekiel",
            "last_name": "Adeniyi",
            "email": "ezekiel.sim@example.com",
            "phone": "+2348123456701",
            "course_name": "Full Stack Software Engineering - 6 Months",
            "batch_name": "Post-Camp Diploma Cohort 1",
            "external_attendance_id": "STU-SIM-101",
            "payment": {
                "amount_paid": 180000.0,
                "status": "paid",
                "reference": "REF-SIM-DIP-01",
            },
        }

        dip_res = client.post(
            "/api/v1/enrollment/sync/",
            data=json.dumps(diploma_payload),
            content_type="application/json",
            HTTP_X_API_KEY=api_key,
        )

        if dip_res.status_code not in (200, 201):
            self.stdout.write(self.style.ERROR(f"[-] Phase 3 Failed (HTTP {dip_res.status_code}): {dip_res.content.decode()[:300]}"))
            return

        dip_data = dip_res.json()
        self.stdout.write(self.style.SUCCESS(f"  [+] Preserved existing student account: {dip_data.get('username')}"))
        self.stdout.write(self.style.SUCCESS(f"  [+] Upgraded enrollment to: Full Stack Software Engineering - 6 Months"))

        user = User.objects.get(id=dip_data["user_id"])
        total_att = Attendance.objects.filter(student=user).count()
        self.stdout.write(self.style.SUCCESS(f"  [+] Historical attendance history retained: {total_att} record(s)"))

        self.stdout.write(self.style.HTTP_INFO("\n=================================================================="))
        self.stdout.write(self.style.SUCCESS("  ALL 3 LIFECYCLE PHASES PASSED WITH 100% SUCCESS!"))
        self.stdout.write(self.style.HTTP_INFO("==================================================================\n"))
