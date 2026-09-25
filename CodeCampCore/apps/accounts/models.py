from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
from django.conf import settings
from apps.courses.models import Subject

ONBOARDING_STAGES = [
    ('email_pending', 'Email Pending'),
    ('welcome', 'Welcome'),
    ('onboarding_steps', 'Onboarding Steps'),
    ('complete_profile', 'Complete Profile'),
    ('finished', 'Finished'),
]


class Profile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('instructor', 'Instructor'),
        ('hod', 'Head of Department'),
        ('support', 'Support Staff'),
        ('accountant', 'Accountant'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    phone = models.CharField(max_length=20, blank=True)
    external_attendance_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Optional ID used by an external attendance system.",
    )
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png')
    is_approved = models.BooleanField(default=False)  # For instructors/HODs

    # Email verification
    is_verified = models.BooleanField(default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False)

    # Relationships
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='profiles',
        help_text="Academy tenant this user belongs to.",
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    batch = models.ForeignKey(
        'scheduling.Batch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    onboarding_stage = models.CharField(
        max_length=30,
        choices=ONBOARDING_STAGES,
        default='email_pending'
    )

    # Progression tracking
    start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Official cohort or program start date."
    )
    has_paid = models.BooleanField(default=False)
    registration_paid = models.BooleanField(default=False)
    tuition_paid = models.BooleanField(default=False)
    total_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Attendance(models.Model):
    STATUS_CHOICES = [
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Late', 'Late'),
        ('Excused', 'Excused'),
    ]

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attendance_records',
        help_text="Academy tenant where attendance occurred.",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    batch = models.ForeignKey(
        'scheduling.Batch',  # ✅ safely reference Batch via string
        on_delete=models.CASCADE,
        related_name='attendance_records',
        null=True,
        blank=True
    )
    date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marked_attendance'
    )
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)
    source = models.CharField(max_length=50, default='manual')
    external_reference = models.CharField(max_length=100, blank=True, db_index=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Attendance'
        verbose_name_plural = 'Attendance Records'
        ordering = ['-date']
        unique_together = ('student', 'subject', 'date')  # prevents duplicates

    def __str__(self):
        return f"{self.student.username} - {self.subject.name} - {self.status}"
