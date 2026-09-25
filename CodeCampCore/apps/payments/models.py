from django.db import models
from django.contrib.auth.models import User
from apps.accounts.models import Profile
from apps.courses.models import Course
from apps.scheduling.models import Batch
import uuid
from decimal import Decimal

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True)
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Tuition discount, concession or scholarship waiver.")
    discount_reason = models.CharField(max_length=255, blank=True, default='', help_text="Reason for discount e.g. Early Bird, Sibling, Negotiated Rate")
    monthly_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_approved = models.BooleanField(default=False, help_text="Approval by administrator/HOD before issuing receipt.")
    approved_at = models.DateTimeField(null=True, blank=True)
    billing_start_date = models.DateField(null=True, blank=True, help_text="Date when monthly billing commences.")
    next_due_date = models.DateField(null=True, blank=True, help_text="Next scheduled monthly tuition due date.")
    notes = models.TextField(blank=True, default='', help_text="Audit remarks or payment verification notes.")
    payment_ref = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_payments')

    def __str__(self):
        return f"{self.student.username} - {self.course.name if self.course else 'No Course'} ({self.status})"

    @property
    def net_amount_due(self):
        """Expected payment after subtracting any discount/scholarship."""
        return max(Decimal('0.00'), self.amount_due - (self.discount or Decimal('0.00')))

    def remaining_balance(self):
        """True outstanding balance against agreed net tuition."""
        return max(Decimal('0.00'), self.net_amount_due - self.amount_paid)

    def update_status(self):
        net = self.net_amount_due
        if self.amount_paid >= net and net > 0:
            self.status = 'paid'
        elif self.amount_paid > 0:
            self.status = 'partial'
        else:
            self.status = 'pending'
        self.save()
        try:
            profile = Profile.objects.get(user=self.student)
            profile.has_paid = self.status in ['partial', 'paid']
            profile.paid_amount = self.amount_paid
            profile.tuition_paid = (self.status == 'paid')
            update_fields = ['has_paid', 'paid_amount', 'tuition_paid']
            if profile.has_paid and profile.student_status == 'summer_alumni':
                profile.student_status = 'active'
                update_fields.append('student_status')
            profile.save(update_fields=update_fields)
        except Profile.DoesNotExist:
            pass

    def calculate_monthly_payment(self):
        """Divide net course fee by duration (weeks/4 ≈ months)."""
        duration = self.course.duration_weeks if self.course else 12
        months = max(1, duration // 4)
        self.monthly_payment = Decimal(self.net_amount_due / months).quantize(Decimal('0.01'))
        self.save()

class Receipt(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='receipts')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    issued_date = models.DateTimeField(auto_now_add=True)
    reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return f"Receipt {self.reference} - ₦{self.amount}"
