from django.core.management.base import BaseCommand
from django.db.models import Q

from teencamp.models import CodingCampRegistration
from teencamp.services.sync_dispatcher import SyncDispatcher


class Command(BaseCommand):
    help = "Retries synchronization for all pending or failed registrations to Attendance System and CodeCampCore."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum number of pending records to process.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        pending_qs = CodingCampRegistration.objects.filter(
            Q(registration_status__in=["SYNC_PENDING", "APPROVED"]) | Q(attendance_synced=False),
            payment_verified=True,
        ).order_by("created_at")[:limit]

        total = pending_qs.count()
        self.stdout.write(self.style.NOTICE(f"Found {total} registrations requiring sync."))

        success_count = 0
        failed_count = 0

        for reg in pending_qs:
            self.stdout.write(f"Syncing [{reg.reg_code}] {reg.first_name} {reg.last_name}...")
            result = SyncDispatcher.dispatch_all(reg)

            if result["all_synced"]:
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ Fully synced {reg.reg_code}"))
            else:
                failed_count += 1
                errors = []
                if not result["attendance"].get("success"):
                    errors.append(f"Attendance: {result['attendance'].get('error')}")
                if not result["core"].get("success"):
                    errors.append(f"Core: {result['core'].get('error')}")
                self.stdout.write(self.style.WARNING(f"  ⚠ Partial/Pending {reg.reg_code}: {'; '.join(errors)}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nRetry sync completed. Total: {total}, Successful: {success_count}, Failed/Pending: {failed_count}"
            )
        )
