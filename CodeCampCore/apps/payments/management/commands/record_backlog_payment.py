import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from apps.accounts.models import Profile
from apps.payments.models import Payment, Receipt


class Command(BaseCommand):
    help = "Records a historical tuition payment or backlog lump sum for students before September 2026."

    def add_arguments(self, parser):
        parser.add_argument(
            "--student",
            type=str,
            default=None,
            help="Username, email, student ID (CDCP-XXXXXX), or full name of the student",
        )
        parser.add_argument(
            "--amount",
            type=float,
            default=None,
            help="Payment amount in NGN (e.g. 150000)",
        )
        parser.add_argument(
            "--amount-due",
            type=float,
            default=None,
            help="Total agreed tuition due for this backlog period (optional, defaults to amount paid)",
        )
        parser.add_argument(
            "--period",
            type=str,
            default="Feb - Aug 2026 (Backlog Lump Sum)",
            help="Billing period/month label (default: 'Feb - Aug 2026 (Backlog Lump Sum)')",
        )
        parser.add_argument(
            "--bank-date",
            type=str,
            default=None,
            help="Actual date funds were received in bank (YYYY-MM-DD, e.g. 2026-08-15)",
        )
        parser.add_argument(
            "--method",
            type=str,
            default="Bank Transfer",
            help="Payment channel: 'Bank Transfer', 'Bank Deposit', 'Cash', 'POS Terminal'",
        )
        parser.add_argument(
            "--notes",
            type=str,
            default="Tuition backlog payment covering February to August 2026",
            help="Audit remarks or bank reference memo",
        )
        parser.add_argument(
            "--interactive",
            action="store_true",
            help="Launch interactive terminal prompt to search student and record backlog payment",
        )

    def _find_student(self, query):
        if not query:
            return None
        query = query.strip()
        # 1. Exact CDCP- ID match
        profile = Profile.objects.filter(external_attendance_id__iexact=query).first()
        if profile:
            return profile.user

        # 2. Exact username
        user = User.objects.filter(username__iexact=query).first()
        if user:
            return user

        # 3. Email
        user = User.objects.filter(email__iexact=query).first()
        if user:
            return user

        # 4. First name & last name match
        parts = query.split()
        if len(parts) >= 2:
            fn, ln = parts[0], " ".join(parts[1:])
            user = User.objects.filter(first_name__iexact=fn, last_name__iexact=ln).first()
            if user:
                return user

        # 5. Case-insensitive substring match in name or username
        user = User.objects.filter(first_name__icontains=query).first()
        if user:
            return user
        user = User.objects.filter(last_name__icontains=query).first()
        if user:
            return user
        user = User.objects.filter(username__icontains=query).first()
        return user

    def handle(self, *args, **options):
        student_query = options.get("student")
        amount = options.get("amount")
        amount_due = options.get("amount_due")
        period = options.get("period") or "Feb - Aug 2026 (Backlog Lump Sum)"
        bank_date_raw = options.get("bank_date")
        method = options.get("method") or "Bank Transfer"
        notes = options.get("notes") or "Tuition backlog payment covering February to August 2026"
        interactive = options.get("interactive", False)

        self.stdout.write(self.style.MIGRATE_HEADING("=== CodeCamp Tuition Backlog Payment Manager ==="))

        if interactive or not student_query:
            if not student_query:
                student_query = input("Enter student name, username, or Student ID (CDCP-XXXXXX): ").strip()

            user = self._find_student(student_query)
            if not user:
                self.stderr.write(self.style.ERROR(f"[ERROR] Could not find any student matching '{student_query}'."))
                return

            self.stdout.write(self.style.SUCCESS(f"Selected Student: {user.get_full_name() or user.username} ({user.email})"))
            profile = getattr(user, "profile", None)
            if profile and profile.course:
                self.stdout.write(f"Course: {profile.course.name} | Batch: {getattr(profile.batch, 'name', 'N/A')}")

            if amount is None:
                amount_str = input("Enter payment amount in NGN (e.g. 150000): ").strip()
                try:
                    amount = float(amount_str)
                except ValueError:
                    self.stderr.write(self.style.ERROR("[ERROR] Invalid numeric amount entered."))
                    return

            period_input = input(f"Billing Period [{period}]: ").strip()
            if period_input:
                period = period_input

            bank_date_input = input("Bank Payment Date YYYY-MM-DD (leave blank for today): ").strip()
            if bank_date_input:
                bank_date_raw = bank_date_input

            notes_input = input(f"Audit Notes / Memo [{notes}]: ").strip()
            if notes_input:
                notes = notes_input
        else:
            user = self._find_student(student_query)
            if not user:
                self.stderr.write(self.style.ERROR(f"[ERROR] Could not find any student matching '{student_query}'."))
                return

        if amount is None or amount <= 0:
            self.stderr.write(self.style.ERROR("[ERROR] A positive payment amount is required."))
            return

        amount_decimal = Decimal(str(amount))
        due_decimal = Decimal(str(amount_due)) if amount_due is not None else amount_decimal

        bank_date = timezone.localdate()
        if bank_date_raw:
            try:
                bank_date = datetime.date.fromisoformat(bank_date_raw)
            except ValueError:
                self.stderr.write(self.style.WARNING(f"Could not parse bank date '{bank_date_raw}', using today."))

        profile = getattr(user, "profile", None)
        course = getattr(profile, "course", None)
        batch = getattr(profile, "batch", None)

        # 1. Locate or create Payment for this period
        payment = Payment.objects.filter(student=user, billing_month=period).first()
        created = False
        if not payment:
            payment = Payment.objects.create(
                student=user,
                course=course,
                batch=batch,
                amount_due=due_decimal,
                amount_paid=Decimal("0.00"),
                billing_month=period,
                notes=notes,
            )
            created = True
        else:
            if amount_due is not None:
                payment.amount_due = due_decimal
            elif payment.amount_paid + amount_decimal > payment.amount_due:
                payment.amount_due = payment.amount_paid + amount_decimal

        # Credit payment
        payment.amount_paid += amount_decimal
        payment.bank_payment_date = bank_date
        payment.is_approved = True
        payment.approved_at = timezone.now()
        admin_user = User.objects.filter(is_superuser=True).first()
        payment.verified_by = admin_user

        audit_entry = f"[{timezone.now().strftime('%d-%b-%Y %H:%M')}] Logged backlog lump sum ₦{amount_decimal:,.2f} for {period} via {method}."
        if notes:
            audit_entry += f" Memo: {notes}"
        payment.notes = f"{payment.notes}\n{audit_entry}".strip() if payment.notes else audit_entry

        payment.update_status()
        payment.save()

        # 2. Issue official digital Receipt
        receipt = Receipt.objects.create(
            payment=payment,
            amount=amount_decimal,
            billing_month=period,
            bank_payment_date=bank_date,
        )

        # 3. Ensure profile is activated and updated
        if profile:
            profile.paid_amount = payment.amount_paid
            profile.has_paid = True
            profile.tuition_paid = (payment.status == "paid")
            if profile.student_status in ["summer_alumni", "suspended", "pending"]:
                profile.student_status = "active"
            profile.save(update_fields=["paid_amount", "has_paid", "tuition_paid", "student_status"])

        receipt_ref = str(receipt.reference)[:8].upper()
        self.stdout.write(self.style.SUCCESS(
            f"\n[OK] Backlog Payment Successfully Recorded!\n"
            f" - Student:       {user.get_full_name() or user.username} ({user.username})\n"
            f" - Period:        {period}\n"
            f" - Amount Paid:   ₦{amount_decimal:,.2f}\n"
            f" - Total Due:     ₦{payment.amount_due:,.2f}\n"
            f" - Balance Left:  ₦{payment.remaining_balance():,.2f}\n"
            f" - Status:        {payment.status.upper()}\n"
            f" - Bank Date:     {bank_date}\n"
            f" - Receipt #:     #{receipt_ref}\n"
            f" - Portal Status: {profile.student_status.upper() if profile else 'ACTIVE'}\n"
        ))
