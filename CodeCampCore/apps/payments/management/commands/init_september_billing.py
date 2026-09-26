import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.accounts.models import Profile
from apps.payments.models import Payment, Receipt

class Command(BaseCommand):
    help = "Initializes September 2026 monthly billing with 0 payments, and sets prior payments to August 2026 lump sum."

    def handle(self, *args, **options):
        # 1. Update existing payment and receipt records that don't have a custom month to August 2026
        prior_payments = Payment.objects.filter(billing_month='September 2026', amount_paid__gt=0)
        updated_prior = 0
        for p in prior_payments:
            p.billing_month = 'August 2026 (Summer Lump Sum)'
            p.save(update_fields=['billing_month'])
            updated_prior += 1
            for r in p.receipts.all():
                r.billing_month = 'August 2026 (Summer Lump Sum)'
                r.save(update_fields=['billing_month'])

        self.stdout.write(self.style.SUCCESS(f"Tagged {updated_prior} prior payment(s) as 'August 2026 (Summer Lump Sum)'."))

        # 2. For every student enrolled in a course, initialize a fresh September 2026 payment at ₦0.00
        students = Profile.objects.filter(role='student')
        september_created = 0
        for profile in students:
            user = profile.user
            course = profile.course
            batch = profile.batch

            # Check if September 2026 record already exists
            sept_payment = Payment.objects.filter(student=user, billing_month='September 2026').first()
            if not sept_payment:
                course_fee = getattr(course, 'fee', Decimal('35000.00')) or Decimal('35000.00')
                Payment.objects.create(
                    student=user,
                    course=course,
                    batch=batch,
                    amount_due=course_fee,
                    amount_paid=Decimal('0.00'),
                    discount=Decimal('0.00'),
                    status='pending',
                    is_approved=False,
                    billing_month='September 2026',
                    notes="September 2026 Term Billing - Awaiting bank transfer / proof verification.",
                )
                september_created += 1

        self.stdout.write(self.style.SUCCESS(f"Initialized {september_created} fresh September 2026 payment records at NGN 0.00."))
