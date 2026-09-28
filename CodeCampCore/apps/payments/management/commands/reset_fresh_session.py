import sys
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.accounts.models import Profile
from apps.payments.models import Payment, Receipt


class Command(BaseCommand):
    help = "Wipes all previous payment/receipt records, resets balances to NGN 0, and deactivates all students to Inactive."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirmation flag to execute the database wipe and deactivation.",
        )
        parser.add_argument(
            "--preserve-courses",
            action="store_true",
            help="Keep students' assigned courses intact while deactivating status and wiping payments.",
        )

    def handle(self, *args, **options):
        confirm = options.get("confirm", False)
        preserve_courses = options.get("preserve_courses", True)

        self.stdout.write(self.style.MIGRATE_HEADING("=== CodeCamp Fresh Session Reset Utility ==="))

        if not confirm:
            self.stdout.write(self.style.WARNING(
                "\n[WARNING] This action will:\n"
                " 1. Permanently DELETE ALL tuition Payment and Receipt records in the database.\n"
                " 2. Reset student balances (paid_amount=0, has_paid=False, tuition_paid=False).\n"
                " 3. Set ALL student accounts to 'inactive' status (hidden from Billing until activated).\n"
                " 4. Students will remain in the Student Directory ready for admin review & activation.\n"
            ))
            choice = input("Type 'RESET' to confirm and proceed: ").strip()
            if choice != "RESET":
                self.stderr.write(self.style.ERROR("[ABORTED] Reset cancelled. No data was modified."))
                return

        # 1. Clear Receipts
        receipt_count, _ = Receipt.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"[OK] Deleted {receipt_count} historical receipt records."))

        # 2. Clear Payments
        payment_count, _ = Payment.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"[OK] Deleted {payment_count} historical payment records."))

        # 3. Update Profile records
        profiles_qs = Profile.objects.filter(role="student")
        total_students = profiles_qs.count()

        update_kwargs = {
            "student_status": "inactive",
            "paid_amount": Decimal("0.00"),
            "has_paid": False,
            "tuition_paid": False,
            "course_approval_status": "none",
            "pending_course": None,
            "pending_batch": None,
        }
        if not preserve_courses:
            update_kwargs["course"] = None
            update_kwargs["batch"] = None

        updated = profiles_qs.update(**update_kwargs)

        self.stdout.write(self.style.SUCCESS(f"[OK] Deactivated {updated} student profiles to 'inactive' status."))
        self.stdout.write(self.style.SUCCESS(
            "\n[SUCCESS] Fresh Session Reset Complete!\n"
            f" - Total Payments Wiped: {payment_count}\n"
            f" - Total Receipts Wiped: {receipt_count}\n"
            f" - Students Deactivated: {updated} of {total_students}\n"
            " - Billing Ledger Status: Clean (0 active debtors)\n"
            "\nYou can now activate students one-by-one from the Student Directory as they start classes.\n"
        ))
