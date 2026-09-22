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
    monthly_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # 🆕
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_ref = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_payments')

    def __str__(self):
        return f"{self.student.username} - {self.course.name} ({self.status})"

    def remaining_balance(self):
        return self.amount_due - self.amount_paid

    def update_status(self):
        if self.amount_paid >= self.amount_due:
            self.status = 'paid'
        elif 0 < self.amount_paid < self.amount_due:
            self.status = 'partial'
        else:
            self.status = 'pending'
        self.save()
        try:
            profile = Profile.objects.get(user=self.student)
            profile.has_paid = self.status in ['partial', 'paid']
            profile.save(update_fields=['has_paid'])
        except Profile.DoesNotExist:
            pass

    def calculate_monthly_payment(self):
        """Divide total course fee by duration (weeks/4 ≈ months)."""
        months = max(1, self.course.duration_weeks // 4)
        self.monthly_payment = Decimal(self.amount_due / months).quantize(Decimal('0.01'))
        self.save()

class Receipt(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='receipts')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    issued_date = models.DateTimeField(auto_now_add=True)
    reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return f"Receipt {self.reference} - ₦{self.amount}"
