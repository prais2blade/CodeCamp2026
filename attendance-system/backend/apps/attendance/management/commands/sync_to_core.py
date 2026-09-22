from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.attendance.models import Attendance
from apps.attendance.services.core_sync_service import CoreAttendanceSyncService


class Command(BaseCommand):
    help = "Syncs recorded attendance from attendance-system to CodeCampCore ERP."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Number of past days to sync (default: 7).",
        )

    def handle(self, *args, **options):
        days = options["days"]
        cutoff = timezone.localdate() - timedelta(days=days)
        qs = Attendance.objects.filter(date__gte=cutoff)

        total = qs.count()
        self.stdout.write(self.style.NOTICE(f"Syncing {total} attendance records from the last {days} days..."))

        result = CoreAttendanceSyncService.bulk_sync(qs)
        if result.get("success"):
            self.stdout.write(self.style.SUCCESS(f"✓ Successfully synced {result.get('count', total)} records to CodeCampCore."))
        else:
            self.stdout.write(self.style.ERROR(f"✗ Attendance sync to Core failed: {result.get('error')}"))
