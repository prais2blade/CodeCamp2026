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
