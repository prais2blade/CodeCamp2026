from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
from django.conf import settings
from decimal import Decimal
from apps.courses.models import Subject

ONBOARDING_STAGES = [
    ('email_pending', 'Email Pending'),
    ('welcome', 'Welcome'),
    ('onboarding_steps', 'Onboarding Steps'),
    ('complete_profile', 'Complete Profile'),
    ('finished', 'Finished'),
]


class Parent(models.Model):
    TITLE_CHOICES = [
        ('Mr', 'Mr.'),
        ('Mrs', 'Mrs.'),
        ('Ms', 'Ms.'),
        ('Dr', 'Dr.'),
        ('Engr', 'Engr.'),
        ('Chief', 'Chief'),
        ('Pastor', 'Pastor'),
        ('Alhaji', 'Alhaji'),
        ('Hajiya', 'Hajiya'),
    ]

    title = models.CharField(max_length=20, choices=TITLE_CHOICES, default='Mr', blank=True)
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=25, db_index=True)
    whatsapp_number = models.CharField(max_length=25, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name']
        verbose_name = 'Parent / Guardian'
        verbose_name_plural = 'Parents / Guardians'

    @property
    def name(self):
        return self.full_name

    @name.setter
    def name(self, val):
        self.full_name = val

    def __str__(self):
        title_prefix = f"{self.title} " if self.title else ""
        return f"{title_prefix}{self.full_name} ({self.phone_number})"


class Profile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('instructor', 'Instructor'),
        ('hod', 'Head of Department'),
        ('support', 'Support Staff'),
        ('accountant', 'Accountant'),
    ]

    STUDENT_STATUS_CHOICES = [
        ('inactive', 'Inactive / Pending Start'),
        ('active', 'Active Student'),
        ('alumni', 'Alumni / Completed'),
        ('completed', 'Completed / Graduated'),
        ('summer_alumni', 'Summer Alumni (Archived)'),
        ('withdrawn', 'Withdrawn'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    student_status = models.CharField(
        max_length=20,
        choices=STUDENT_STATUS_CHOICES,
        default='inactive',
        help_text="Student lifecycle status: Inactive, Active, or Alumni."
    )
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
    pending_course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pending_students',
        help_text="Course selected or requested by student awaiting admin approval."
    )
    batch = models.ForeignKey(
        'scheduling.Batch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    pending_batch = models.ForeignKey(
        'scheduling.Batch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pending_students',
        help_text="Cohort requested by student awaiting admin approval."
    )
    COURSE_APPROVAL_CHOICES = [
        ('none', 'None'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    course_approval_status = models.CharField(
        max_length=20,
        choices=COURSE_APPROVAL_CHOICES,
        default='none',
        help_text="Status of student course enrollment or change request."
    )
    course_change_requested_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of latest course selection/change request."
    )
    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Agreed tuition concession or scholarship discount."
    )
    discount_reason = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Reason for discount e.g. Sibling, Early Bird, Staff Child."
    )
    assigned_tutor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tutored_students',
        limit_choices_to={'profile__role__in': ['instructor', 'hod']},
        help_text="Assigned teacher or tutor for this student."
    )
    enrolled_subjects = models.ManyToManyField(
        'courses.Subject',
        blank=True,
        related_name='enrolled_students',
        help_text="Curriculum subjects this student is enrolled in."
    )

    RELATIONSHIP_CHOICES = [
        ('Father', 'Father'),
        ('Mother', 'Mother'),
        ('Guardian', 'Guardian'),
        ('Sponsor', 'Sponsor / Relative'),
        ('Self', 'Self (Independent Adult)'),
    ]

    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Prefer not to say'),
    ]

    # Parent relationship & Personal bio
    parent = models.ForeignKey(
        'Parent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        help_text="Parent or guardian of this student."
    )
    relationship_to_parent = models.CharField(
        max_length=30,
        choices=RELATIONSHIP_CHOICES,
        default='Guardian',
        blank=True
    )
    date_of_birth = models.DateField(null=True, blank=True, help_text="Student's date of birth.")
    gender = models.CharField(max_length=15, choices=GENDER_CHOICES, blank=True)
    id_card_approved = models.BooleanField(
        default=False,
        help_text="Whether the student's passport and parameters are approved for official ID Card generation."
    )

    @property
    def has_custom_avatar(self):
        if bool(self.avatar and self.avatar.name and not self.avatar.name.endswith('default.png')):
            return True
        # Automatic fallback: if staff took photo on attendance system, link it automatically
        if self.external_attendance_id:
            try:
                from apps.accounts.services.attendance_sync_service import AttendanceSyncService
                photo_file = AttendanceSyncService.find_student_photo_file(
                    student_id=self.external_attendance_id,
                    first_name=self.user.first_name if self.user else None,
                    last_name=self.user.last_name if self.user else None,
                )
                if photo_file and os.path.isfile(photo_file):
                    import shutil
                    avatars_target_dir = os.path.join(settings.MEDIA_ROOT, "avatars")
                    os.makedirs(avatars_target_dir, exist_ok=True)
                    clean_sid = self.external_attendance_id.replace("-", "_")
                    base_fname = os.path.basename(photo_file)
                    dest_name = f"{clean_sid}_{base_fname}"
                    dest_full = os.path.join(avatars_target_dir, dest_name)
                    if not os.path.exists(dest_full):
                        shutil.copy2(photo_file, dest_full)
                    self.avatar = f"avatars/{dest_name}"
                    self.id_card_approved = True
                    self.save(update_fields=['avatar', 'id_card_approved'])
                    return True
            except Exception:
                pass
        return False

    @property
    def parent_display(self):
        if self.parent:
            title_prefix = f"{self.parent.title} " if self.parent.title else ""
            return f"{title_prefix}{self.parent.full_name}".strip()
        return None

    def enroll_in_course_subjects(self, subject_ids=None):
        """Enrolls student in specified subjects and ensures all compulsory subjects are always included."""
        if self.course:
            compulsory_ids = set(self.course.subjects.filter(is_compulsory=True).values_list('id', flat=True))
            if subject_ids is not None:
                all_ids = compulsory_ids.union(set(int(sid) for sid in subject_ids if str(sid).isdigit()))
                self.enrolled_subjects.set(all_ids)
            else:
                self.enrolled_subjects.set(self.course.subjects.all())
        elif subject_ids is not None:
            self.enrolled_subjects.set(subject_ids)

    @property
    def tutor_display(self):
        if self.assigned_tutor:
            return self.assigned_tutor.get_full_name() or self.assigned_tutor.username
        if self.batch:
            session_inst = self.batch.sessions.filter(instructor__isnull=False).select_related('instructor').first()
            if session_inst and session_inst.instructor:
                return session_inst.instructor.get_full_name() or session_inst.instructor.username
        if self.course:
            subj_inst = self.course.subjects.filter(instructor__isnull=False).select_related('instructor').first()
            if subj_inst and subj_inst.instructor:
                return subj_inst.instructor.get_full_name() or subj_inst.instructor.username
        return None

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
        return f"{self.user.username} ({self.role} - {self.student_status})"


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
        'scheduling.Batch',
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
        unique_together = ('student', 'subject', 'date')

    def __str__(self):
        return f"{self.student.username} - {self.subject.name} - {self.status}"


class SummerCertificate(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='summer_certificates'
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    title = models.CharField(max_length=255, default='Certificate of Completion - Summer CodeCamp')
    certificate_file = models.FileField(upload_to='certificates/summer/', null=True, blank=True)
    issue_date = models.DateField(default=timezone.localdate)
    reference_id = models.CharField(max_length=60, unique=True, default=uuid.uuid4)
    remarks = models.CharField(max_length=255, blank=True, default='Outstanding participation in Summer Boot Camp')
    grade_or_score = models.CharField(max_length=50, blank=True, default='Distinction')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_certificates'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Summer Certificate'
        verbose_name_plural = 'Summer Certificates'
        ordering = ['-issue_date']

    def __str__(self):
        return f"{self.student.username} - {self.title}"


class Certificate(models.Model):
    GRADE_CHOICES = [
        ('Distinction', 'Distinction / Excellent'),
        ('Merit', 'Merit / Very Good'),
        ('Credit', 'Credit / Good'),
        ('Pass', 'Pass'),
        ('Participation', 'Certificate of Participation'),
    ]

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificates'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='certificates'
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificates'
    )
    batch = models.ForeignKey(
        'scheduling.Batch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificates'
    )
    title = models.CharField(max_length=255, default='Certificate of Completion')
    grade = models.CharField(max_length=50, choices=GRADE_CHOICES, default='Merit')
    certificate_file = models.FileField(upload_to='certificates/official/', null=True, blank=True)
    issue_date = models.DateField(default=timezone.localdate)
    completion_date = models.DateField(default=timezone.localdate)
    reference_id = models.CharField(max_length=60, unique=True, default=uuid.uuid4)
    remarks = models.CharField(max_length=255, blank=True, default='Outstanding completion of all training modules and practical benchmarks.')
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_official_certificates'
    )
    is_revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Certificate'
        verbose_name_plural = 'Certificates'
        ordering = ['-issue_date', '-created_at']

    def __str__(self):
        return f"{self.student.username} - {self.title} ({self.grade})"

    @property
    def formatted_ref(self):
        return f"CC-{str(self.reference_id)[:8].upper()}"

