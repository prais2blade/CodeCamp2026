from decimal import Decimal
import secrets
import uuid

from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.utils import timezone


# ==========================================================
# Registration Status
# ==========================================================

REGISTRATION_STATUS = [
    ("PENDING", "Pending"),
    ("APPROVED", "Approved"),
    ("BATCH_ASSIGNED", "Batch Assigned"),
    ("SYNC_PENDING", "Sync Pending"),
    ("SYNCED", "Synced"),
    ("COMPLETED", "Completed"),
    ("WAITLIST", "Waiting List"),
    ("FAILED", "Failed"),
]


# ==========================================================
# Class Mode
# ==========================================================

CLASS_MODE = [
    ("PHYSICAL", "Physical Class"),
    ("VIRTUAL", "Virtual Class"),
]


# ==========================================================
# Parent Relationship
# ==========================================================

PARENT_RELATIONSHIP = [
    ("Father", "Father"),
    ("Mother", "Mother"),
    ("Guardian", "Guardian"),
    ("Other", "Other"),
]


# ==========================================================
# Pricing
# ==========================================================

STANDARD_PRICE = Decimal("30000.00")

DISCOUNT_RATE = Decimal("0.00")

EARLY_BIRD_LIMIT = 0


# ==========================================================
# Batch Constants
# ==========================================================

MAX_CAPACITY = 120

BATCH_SIZE = 30


# ==========================================================
# Upload Helpers
# ==========================================================

def receipt_upload_path(instance, filename):

    ext = filename.split(".")[-1]

    return f"camp/receipts/{uuid.uuid4().hex}.{ext}"


# ==========================================================
# Batch Model
# ==========================================================

class Batch(models.Model):
    """
    Represents one training batch.
    """

    code = models.CharField(
        max_length=20,
        unique=True,
    )

    name = models.CharField(
        max_length=100,
    )

    mode = models.CharField(
        max_length=10,
        choices=CLASS_MODE,
    )

    camp_year = models.PositiveIntegerField(
        default=timezone.now().year,
    )

    capacity = models.PositiveIntegerField(
        default=30,
    )

    current_size = models.PositiveIntegerField(
        default=0,
    )

    priority = models.PositiveIntegerField(
        default=1,
        help_text="Lower numbers are filled first."
    )

    accept_new_registrations = models.BooleanField(
        default=True,
    )
    
    reserved_for_existing_students = models.BooleanField(
        default=False,
        help_text=(
            "Reserve this batch for existing CodeCamp students. "
            "New public registrations will not be allocated here."
        ),
    )

    reporting_time = models.TimeField()

    start_date = models.DateField()

    end_date = models.DateField()

    is_active = models.BooleanField(
        default=True,
    )

    class_days = models.CharField(
        max_length=100,
        help_text="Example: Mon, Wed & Fri"
    )

    class Meta:

        ordering = [
            "priority",
            "code",
        ]

        unique_together = (
            "code",
            "camp_year",
        )

    def __str__(self):

        return (
            f"{self.name} "
            f"({self.camp_year})"
        )

    @property
    def remaining_seats(self):

        return max(
            0,
            self.capacity - self.current_size
        )

    @property
    def is_full(self):

        return (
            self.current_size >= self.capacity
        )
        
    # ======================================================
    # Batch Helpers
    # ======================================================

    def increment_size(self):
        """
        Increase current batch occupancy.
        """
        self.current_size += 1
        self.save(update_fields=["current_size"])

    def decrement_size(self):
        """
        Reduce current batch occupancy.
        """
        if self.current_size > 0:
            self.current_size -= 1
            self.save(update_fields=["current_size"])

    def can_accept_registration(self):
        """
        Returns True if this batch can receive
        another student.
        """
        return (
            self.is_active
            and self.accept_new_registrations
            and not self.is_full
        )
        



# ==========================================================
# Coding Camp Registration
# ==========================================================

class CodingCampRegistration(models.Model):

    # ======================================================
    # Student Information
    # ======================================================

    first_name = models.CharField(
        max_length=80
    )

    last_name = models.CharField(
        max_length=80
    )

    age = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(8),
            MaxValueValidator(18),
        ]
    )

    mode = models.CharField(
        max_length=10,
        choices=CLASS_MODE,
        default="PHYSICAL",
    )

    # ======================================================
    # Parent / Guardian Information
    # ======================================================

    parent_name = models.CharField(
        max_length=150
    )

    relationship = models.CharField(
        max_length=20,
        choices=PARENT_RELATIONSHIP,
        default="Guardian",
    )

    parent_phone = models.CharField(
        max_length=20
    )

    parent_whatsapp = models.CharField(
        max_length=20,
        blank=True,
    )

    parent_email = models.EmailField()

    # ======================================================
    # Payment Information
    # ======================================================

    discount_applied = models.BooleanField(
        default=False
    )

    price_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    receipt = models.FileField(
        upload_to=receipt_upload_path,
        validators=[
            FileExtensionValidator(
                ["jpg", "jpeg", "png", "pdf"]
            )
        ],
        blank=True,
        null=True,
    )

    payment_verified = models.BooleanField(
        default=False
    )

    # ======================================================
    # Registration Information
    # ======================================================

    registration_status = models.CharField(
        max_length=20,
        choices=REGISTRATION_STATUS,
        default="PENDING",
    )

    batch = models.ForeignKey(
        Batch,
        on_delete=models.SET_NULL,
        related_name="registrations",
        null=True,
        blank=True,
    )

    camp_year = models.PositiveIntegerField(
        default=timezone.now().year,
    )

    reference = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
    )

    reg_code = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
    )

    # ======================================================
    # Attendance Synchronization
    # ======================================================

    attendance_synced = models.BooleanField(
        default=False
    )

    attendance_student_id = models.CharField(
        max_length=30,
        blank=True,
    )

    attendance_sync_date = models.DateTimeField(
        blank=True,
        null=True,
    )

    # ======================================================
    # Metadata
    # ======================================================

    created_at = models.DateTimeField(
        default=timezone.now
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:

        ordering = [
            "-created_at"
        ]

        constraints = [

            models.UniqueConstraint(

                fields=[
                    "first_name",
                    "last_name",
                    "parent_phone",
                    "camp_year",
                ],

                name="unique_child_registration"
            )

        ]

        verbose_name = "Camp Registration"

        verbose_name_plural = "Camp Registrations"

    @property
    def full_name(self):

        return f"{self.first_name} {self.last_name}"
    
    
    def sync_completed(self, attendance_student_id):

        self.attendance_student_id = attendance_student_id

        self.attendance_synced = True

        self.attendance_sync_date = timezone.now()

        self.registration_status = "COMPLETED"
    
    # ======================================================
    # Model Helpers
    # ======================================================

    @property
    def parent_contact(self):
        """
        Preferred parent contact number.
        """
        return self.parent_whatsapp or self.parent_phone

    @property
    def is_completed(self):
        return self.registration_status == "COMPLETED"

    @property
    def requires_sync(self):
        return (
            self.payment_verified
            and not self.attendance_synced
        )

    # ======================================================
    # Registration Number Generator
    # ======================================================

    def generate_reference(self):

        if not self.reference:
            self.reference = secrets.token_hex(6).upper()

    def generate_registration_code(self):

        if self.reg_code:
            return

        year = str(self.camp_year)[-2:]

        last_registration = (
            CodingCampRegistration.objects
            .filter(camp_year=self.camp_year)
            .exclude(pk=self.pk)
            .order_by("-id")
            .first()
        )

        if last_registration:
            try:
                last_number = int(
                    last_registration.reg_code.split("-")[-1]
                )
            except (ValueError, IndexError):
                last_number = 0
        else:
            last_number = 0

        next_number = last_number + 1

        self.reg_code = (
            f"CC{self.camp_year}-{next_number:05d}"
        )

    # ======================================================
    # Save
    # ======================================================

    def save(self, *args, **kwargs):

        if not self.reference:
            self.generate_reference()

        if not self.reg_code:
            self.generate_registration_code()

        super().save(*args, **kwargs)

    # ======================================================
    # Email
    # ======================================================

    def send_confirmation_email(self):

        subject = "CodeCamp Registration Confirmed 🎉"

        batch_name = (
            self.batch.name
            if self.batch
            else "To Be Assigned"
        )

        message = f"""
Dear {self.parent_name},

Congratulations!

Your child's registration has been confirmed.

----------------------------------------

Student:
{self.full_name}

Registration Code:
{self.reg_code}

Class Mode:
{self.mode.title()}

Batch:
{batch_name}

Amount Paid:
₦{self.price_paid:,.2f}

----------------------------------------

Further information will be sent before classes begin.

Thank you for choosing CodeCamp.

Regards,

CodeCamp Team
        """.strip()

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [self.parent_email],
            fail_silently=False,
        )

    # ======================================================
    # String Representation
    # ======================================================

    def __str__(self):

        return (
            f"{self.reg_code} - "
            f"{self.full_name}"
        )
        
    # ======================================================
    # Registration Helpers
    # ======================================================

    def approve_payment(self):
        """
        Mark payment as verified.
        """
        self.payment_verified = True
        self.registration_status = "APPROVED"

    def assign_batch(self, batch):
        """
        Assign registration to a batch.
        """
        self.batch = batch
        self.registration_status = "BATCH_ASSIGNED"

    def mark_sync_pending(self):
        self.registration_status = "SYNC_PENDING"

    def sync_completed(self, attendance_student_id):

        self.attendance_student_id = attendance_student_id

        self.attendance_synced = True

        self.attendance_sync_date = timezone.now()

        self.registration_status = "COMPLETED"

    def mark_completed(self):

        self.registration_status = "COMPLETED"

    def move_to_waitlist(self):

        self.registration_status = "WAITLIST"

    def mark_failed(self):

        self.registration_status = "FAILED"
