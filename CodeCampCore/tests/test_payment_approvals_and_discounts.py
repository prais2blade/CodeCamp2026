from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from apps.courses.models import Course
from apps.scheduling.models import Batch
from apps.payments.models import Payment, Receipt


class PaymentApprovalsAndDiscountsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser('adminuser', 'admin@codecamp.com', 'password123')
        self.student_user = User.objects.create_user('johnstudent', 'john@codecamp.com', 'password123')

        self.course = Course.objects.create(
            name="Robotics & Automation",
            fee=Decimal('180000.00'),
            duration_weeks=12
        )
        self.batch = Batch.objects.create(
            name="Weekend Cohort",
            course=self.course,
            mode='onsite',
            batch_type='weekends',
            session_period='morning',
            days_pattern='weekend',
            start_date='2026-10-01',
            end_date='2026-12-20'
        )
        self.payment = Payment.objects.create(
            student=self.student_user,
            course=self.course,
            batch=self.batch,
            amount_due=Decimal('180000.00'),
            amount_paid=Decimal('0.00'),
            discount=Decimal('0.00')
        )

    def test_schedule_display(self):
        """Batch schedule_display should cleanly format delivery slot."""
        display = self.batch.schedule_display
        self.assertIn("Weekend", display)
        self.assertIn("Morning", display)
        self.assertIn("Onsite", display)

    def test_discount_and_net_amount_due(self):
        """Applying discount should adjust net_amount_due and remaining_balance."""
        self.payment.discount = Decimal('60000.00')
        self.assertEqual(self.payment.net_amount_due, Decimal('120000.00'))
        self.assertEqual(self.payment.remaining_balance(), Decimal('120000.00'))

        # Partially pay
        self.payment.amount_paid = Decimal('50000.00')
        self.payment.update_status()
        self.assertEqual(self.payment.status, 'partial')
        self.assertEqual(self.payment.remaining_balance(), Decimal('70000.00'))

        # Complete payment against net due
        self.payment.amount_paid = Decimal('120000.00')
        self.payment.update_status()
        self.assertEqual(self.payment.status, 'paid')
        self.assertEqual(self.payment.remaining_balance(), Decimal('0.00'))

    def test_approve_payment_generates_receipt(self):
        """Approving payment should verify amount, apply discount, and issue receipt."""
        self.client.login(username='adminuser', password='password123')
        approve_url = reverse('approve_payment', kwargs={'payment_id': self.payment.id})

        response = self.client.post(approve_url, {
            'amount_paid': '35000.00',
            'discount': '5000.00',
            'discount_reason': 'Early Bird',
            'issue_receipt': 'on'
        })
        self.assertEqual(response.status_code, 302)

        self.payment.refresh_from_db()
        self.assertTrue(self.payment.is_approved)
        self.assertEqual(self.payment.amount_paid, Decimal('35000.00'))
        self.assertEqual(self.payment.discount, Decimal('5000.00'))
        self.assertEqual(self.payment.discount_reason, 'Early Bird')
        self.assertEqual(self.payment.receipts.count(), 1)
        receipt = self.payment.receipts.first()
        self.assertEqual(receipt.amount, Decimal('35000.00'))

    def test_bulk_cohort_discount(self):
        """Bulk applying discount by cohort should update all student payments in batch."""
        self.client.login(username='adminuser', password='password123')
        bulk_url = reverse('bulk_apply_discount')

        response = self.client.post(bulk_url, {
            'mode': 'cohort',
            'batch_id': self.batch.id,
            'discount_type': 'agreed_fee',
            'amount': '100000.00',
            'reason': 'Cohort Concession'
        })
        self.assertEqual(response.status_code, 302)

        self.payment.refresh_from_db()
        # Original fee 180,000 - agreed 100,000 = discount 80,000
        self.assertEqual(self.payment.discount, Decimal('80000.00'))
        self.assertEqual(self.payment.net_amount_due, Decimal('100000.00'))
        self.assertEqual(self.payment.discount_reason, 'Cohort Concession')

    def test_student_submit_payment_proof_and_approval_flow(self):
        """Student submits bank payment proof for September 2026, accountant approves with bank date."""
        self.client.login(username='johnstudent', password='password123')
        submit_url = reverse('submit_payment_proof')

        import io
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_slip = SimpleUploadedFile("teller.png", b"file_content", content_type="image/png")

        resp = self.client.post(submit_url, {
            'billing_month': 'September 2026',
            'amount': '35000.00',
            'bank_payment_date': '2026-09-24',
            'notes': 'GTBank / NIP Ref: 829104',
            'payment_proof': fake_slip
        })
        self.assertEqual(resp.status_code, 302)

        # Student payment created or updated, pending approval
        sept_p = Payment.objects.get(student=self.student_user, billing_month='September 2026')
        self.assertEqual(sept_p.amount_paid, Decimal('35000.00'))
        self.assertFalse(sept_p.is_approved)
        self.assertEqual(str(sept_p.bank_payment_date), '2026-09-24')
        self.assertTrue(bool(sept_p.payment_proof))

        # Accountant logs in and approves
        self.client.login(username='adminuser', password='password123')
        approve_url = reverse('approve_payment', kwargs={'payment_id': sept_p.id})
        resp = self.client.post(approve_url, {
            'billing_month': 'September 2026',
            'bank_payment_date': '2026-09-24',
            'amount_paid': '35000.00',
            'discount': '0.00',
            'issue_receipt': 'on'
        })
        self.assertEqual(resp.status_code, 302)

        sept_p.refresh_from_db()
        self.assertTrue(sept_p.is_approved)
        self.assertEqual(sept_p.receipts.count(), 1)
        receipt = sept_p.receipts.first()
        self.assertEqual(receipt.billing_month, 'September 2026')
        self.assertEqual(str(receipt.bank_payment_date), '2026-09-24')

    def test_search_by_month_september(self):
        """Searching 'september' in manage_payments returns all September payments."""
        self.client.login(username='adminuser', password='password123')
        url = reverse('manage_payments') + "?q=September"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "September")

    def test_progressive_receipt_calculation_feb_to_august(self):
        """
        If agreed monthly rate is 20k and student started in Feb, by August (6 months):
        Total due to date: 120k. Amount paid: 60k. Outstanding to date: 60k.
        Full scary course fee is not shown.
        """
        import datetime
        from apps.accounts.models import Profile

        profile, _ = Profile.objects.get_or_create(user=self.student_user)
        profile.start_date = datetime.date(2026, 2, 1)
        profile.save()

        # Monthly payment with agreed rate of ₦20,000 (standard 35k minus 15k discount or net 20k)
        payment = Payment.objects.create(
            student=self.student_user,
            course=self.course,
            amount_due=Decimal('35000.00'),
            discount=Decimal('15000.00'),  # net_amount_due = 20000
            amount_paid=Decimal('60000.00'),
            billing_month='August 2026 (Summer Lump Sum)',
            bank_payment_date=datetime.date(2026, 8, 15),
            is_approved=True
        )
        receipt = Receipt.objects.create(
            payment=payment,
            amount=Decimal('60000.00'),
            billing_month='August 2026 (Summer Lump Sum)',
            bank_payment_date=datetime.date(2026, 8, 15)
        )

        self.client.login(username='adminuser', password='password123')
        url = reverse('view_receipt', kwargs={'receipt_id': receipt.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        # Context checks
        self.assertEqual(resp.context['months_elapsed'], 6)
        self.assertEqual(resp.context['monthly_rate'], Decimal('20000.00'))
        self.assertEqual(resp.context['total_due_to_date'], Decimal('120000.00'))
        self.assertEqual(resp.context['total_paid_to_date'], Decimal('60000.00'))
        self.assertEqual(resp.context['outstanding_to_date'], Decimal('60000.00'))

        # Template HTML checks
        self.assertContains(resp, "120,000")
        self.assertContains(resp, "60,000")
        self.assertContains(resp, "6 Months")
        self.assertContains(resp, "Current Outstanding Balance")

