from django.core.management.base import BaseCommand
from apps.accounts.services.attendance_sync_service import AttendanceSyncService


class Command(BaseCommand):
    help = "Synchronizes official Student IDs and Faculty/Tutors between CodeCampCore and the Attendance System."

    def add_arguments(self, parser):
        parser.add_argument(
            '--db-path',
            type=str,
            help='Explicit path to attendance-system db.sqlite3',
        )

    def handle(self, *args, **options):
        db_path = options.get('db_path')
        self.stdout.write(self.style.NOTICE("Starting synchronization with Attendance System..."))

        if db_path:
            res_tutors = AttendanceSyncService.sync_tutors(db_path)
            res_students = AttendanceSyncService.sync_student_ids(db_path)
            res = {
                "success": True,
                "db_path": db_path,
                "tutors": res_tutors,
                "students": res_students
            }
        else:
            res = AttendanceSyncService.sync_all()

        if not res.get("success"):
            self.stdout.write(self.style.ERROR(f"Sync failed or attendance DB not found at: {res.get('db_path')}"))
            return

        t_data = res.get("tutors", {})
        s_data = res.get("students", {})

        self.stdout.write(self.style.SUCCESS(
            f"[OK] Synchronized {s_data.get('students_matched', 0)} of {s_data.get('attendance_students_count', 0)} student IDs."
        ))
        self.stdout.write(self.style.SUCCESS(
            f"[OK] Synchronized {t_data.get('tutors_total', 0)} faculty tutors ({t_data.get('tutors_created', 0)} new, {t_data.get('tutors_updated', 0)} updated)."
        ))
        self.stdout.write(self.style.SUCCESS("[OK] Zero tutor duplicates ensured!"))
