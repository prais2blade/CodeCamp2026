from django.db import models
from django.conf import settings
import json
import qrcode
from io import BytesIO
from django.core.files import File
import secrets
from django.contrib.auth.hashers import make_password, check_password



def generate_student_id():

    last_student = Student.objects.order_by(
        "-id"
    ).first()

    if not last_student:
        return "CDCP-000001"

    last_number = int(
        last_student.student_id.split("-")[1]
    )

    next_number = last_number + 1

    return f"CDCP-{next_number:06d}"


class Student(models.Model):

    student_id = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
    )

    integration_key = models.CharField(
        max_length=120,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "External registration key used to prevent duplicate "
            "students from integration retries."
        ),
    )

    first_name = models.CharField(
        max_length=100,
    )

    last_name = models.CharField(
        max_length=100
    )

    date_of_birth = models.DateField(
        blank=True,
        null=True
    )

    gender = models.CharField(
        max_length=10,
        blank=True,
    )

    class_name = models.CharField(
        max_length=100,
        blank=True,
    )

    teaching_class = models.ForeignKey(
        "TeachingClass",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )

    parent_name = models.CharField(
        max_length=200,
        blank=True,
    )

    photo = models.ImageField(
        upload_to='students/photos/',
        blank=True,
        null=True
    )

    qr_code = models.ImageField(
        upload_to='students/qrcodes/',
        blank=True,
        null=True
    )

    portal_token = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def generate_qr_code(self):

        qr_data = {
            "student_id": self.student_id
        }

        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=5,
        )

        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)

        img = qr.make_image(
            fill_color="black",
            back_color="white"
        )

        buffer = BytesIO()

        img.save(buffer, format="PNG")
        buffer.seek(0)

        filename = f"{self.student_id}.png"

        self.qr_code.save(
            filename,
            File(buffer),
            save=False
        )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):

        is_new = self.pk is None

        if not self.portal_token:
            self.portal_token = secrets.token_urlsafe(16)

        if not self.student_id:
            self.student_id = generate_student_id()

        super().save(*args, **kwargs)

        if is_new and not self.qr_code:
            self.generate_qr_code()

            super().save(
                update_fields=["qr_code"]
            )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class Parent(models.Model):
    title = models.CharField(
        max_length=20,
    )

    full_name = models.CharField(
        max_length=255,
    )

    phone_number = models.CharField(
        max_length=20,
        unique=True,
    )

    whatsapp_number = models.CharField(
        max_length=20,
        blank=True,
    )

    email = models.EmailField(
        blank=True,
    )

    receive_email = models.BooleanField(
        default=True,
    )

    receive_whatsapp = models.BooleanField(
        default=True,
    )

    password = models.CharField(
        max_length=255,
    )

    must_change_password = models.BooleanField(
        default=True,
        help_text=(
            "Require the parent to change "
            "their password after first login."
        ),
    )

    last_login_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    last_password_change = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "full_name",
        ]
        indexes = [
            models.Index(
                fields=[
                    "phone_number",
                ]
            ),
            models.Index(
                fields=[
                    "full_name",
                ]
            ),
        ]

    def set_password(self, raw_password):
        self.password = make_password(
            raw_password
        )

    def check_password(self, raw_password):
        return check_password(
            raw_password,
            self.password,
        )

    def mark_password_changed(self):
        from django.utils import timezone

        self.must_change_password = False
        self.last_password_change = (
            timezone.now()
        )

        self.save(
            update_fields=[
                "must_change_password",
                "last_password_change",
            ]
        )

    def update_last_login(self):
        from django.utils import timezone

        self.last_login_at = (
            timezone.now()
        )

        self.save(
            update_fields=[
                "last_login_at",
            ]
        )

    def __str__(self):
        return self.full_name
    
    
    
class StudentParent(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="parents"
    )

    parent = models.ForeignKey(
        Parent,
        on_delete=models.CASCADE,
        related_name="students"
    )

    relationship = models.CharField(
        max_length=50,
        default="Guardian"
    )
    
    teaching_class = models.ForeignKey(
        "TeachingClass",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_parent_links",
    )

    def __str__(self):

        return (

            f"{self.student} - "

            f"{self.parent}"

        )


class Foundation(models.Model):
    name = models.CharField(
        max_length=255,
        unique=True,
    )

    contact_person = models.CharField(
        max_length=255,
        blank=True,
    )

    email = models.EmailField(
        unique=True,
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
    )

    password = models.CharField(
        max_length=255,
    )

    must_change_password = models.BooleanField(
        default=True,
    )

    last_login_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    last_password_change = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "name",
        ]
        indexes = [
            models.Index(
                fields=[
                    "email",
                ]
            ),
            models.Index(
                fields=[
                    "name",
                ]
            ),
        ]

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def update_last_login(self):
        from django.utils import timezone

        self.last_login_at = timezone.now()
        self.save(
            update_fields=[
                "last_login_at",
            ]
        )

    def mark_password_changed(self):
        from django.utils import timezone

        self.must_change_password = False
        self.last_password_change = timezone.now()
        self.save(
            update_fields=[
                "must_change_password",
                "last_password_change",
            ]
        )

    def __str__(self):
        return self.name


class StudentFoundation(models.Model):
    foundation = models.ForeignKey(
        Foundation,
        on_delete=models.CASCADE,
        related_name="student_links",
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="foundation_links",
    )

    sponsorship_note = models.CharField(
        max_length=255,
        blank=True,
    )

    start_date = models.DateField(
        null=True,
        blank=True,
    )

    end_date = models.DateField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "student__first_name",
            "student__last_name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "foundation",
                    "student",
                ],
                name="unique_foundation_student_link",
            )
        ]

    def __str__(self):
        return f"{self.foundation} - {self.student}"



class Announcement(models.Model):
    """
    Summer announcements displayed on the
    Parent Portal timeline.
    """

    TARGET_ALL = "ALL"
    TARGET_CLASS = "CLASS"

    TARGET_CHOICES = [
        (TARGET_ALL, "All Students"),
        (TARGET_CLASS, "Specific Class"),
    ]

    title = models.CharField(
        max_length=200,
    )

    message = models.TextField()

    target = models.CharField(
        max_length=20,
        choices=TARGET_CHOICES,
        default=TARGET_ALL,
    )

    class_name = models.CharField(
        max_length=100,
        blank=True,
    )

    teaching_class = models.ForeignKey(
        "TeachingClass",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements",
    )

    attachment = models.FileField(
        upload_to="announcements/",
        blank=True,
        null=True,
    )

    publish_at = models.DateTimeField(
        auto_now_add=True,
    )

    expires_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_by = models.CharField(
        max_length=150,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-publish_at",
        ]

    def __str__(self):
        return self.title
    
class Tutor(models.Model):
    """
    Tutors responsible for teaching one or
    more classes.
    """

    first_name = models.CharField(
        max_length=100,
    )

    last_name = models.CharField(
        max_length=100,
    )

    email = models.EmailField(
        unique=True,
    )

    phone_number = models.CharField(
        max_length=20,
        unique=True,
    )

    password = models.CharField(
        max_length=255,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "first_name",
            "last_name",
        ]

    @property
    def full_name(self):
        return (
            f"{self.first_name} "
            f"{self.last_name}"
        )

    def set_password(self, raw_password):
        self.password = make_password(
            raw_password
        )

    def check_password(self, raw_password):
        return check_password(
            raw_password,
            self.password,
        )

    def __str__(self):
        return self.full_name
    

class TeachingClass(models.Model):
    """
    Operational teaching class.

    Used by Attendance,
    Parent Portal and Tutor Dashboard.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
    )

    description = models.TextField(
        blank=True,
    )

    tutor = models.ForeignKey(
        Tutor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="classes",
    )

    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teaching_classes",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "name",
        ]

    def __str__(self):
        return self.name


class Assignment(models.Model):
    title = models.CharField(
        max_length=200,
    )

    description = models.TextField()

    teaching_class = models.ForeignKey(
        TeachingClass,
        on_delete=models.CASCADE,
        related_name="assignments",
    )

    due_date = models.DateField(
        null=True,
        blank=True,
    )

    attachment = models.FileField(
        upload_to="assignments/",
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]

    def __str__(self):
        return self.title


class PerformanceRecord(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="performance_records",
    )

    teaching_class = models.ForeignKey(
        TeachingClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performance_records",
    )

    title = models.CharField(
        max_length=200,
    )

    subject = models.CharField(
        max_length=120,
        blank=True,
    )

    term = models.CharField(
        max_length=120,
        blank=True,
    )

    score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )

    max_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )

    grade = models.CharField(
        max_length=30,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    attachment = models.FileField(
        upload_to="performance/",
        null=True,
        blank=True,
    )

    visible_to_foundations = models.BooleanField(
        default=True,
    )

    recorded_at = models.DateField(
        null=True,
        blank=True,
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_performance_records",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-recorded_at",
            "-created_at",
        ]

    @property
    def percentage(self):
        if self.score is None or not self.max_score:
            return None

        return round((self.score / self.max_score) * 100, 2)

    def save(self, *args, **kwargs):
        if self.student and self.student.teaching_class_id:
            self.teaching_class = self.student.teaching_class

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} - {self.title}"
