from django.db import models
from django.contrib.auth.models import User
from apps.courses.models import Course, Subject
from apps.mailing.tasks import send_new_session_announcement
from apps.mailing.tasks import send_new_session_announcement


class Batch(models.Model):
    MODE_CHOICES = [
        ('online', 'Online'),
        ('onsite', 'Onsite'),
    ]
    TYPE_CHOICES = [
        ('weekdays', 'Weekdays'),
        ('weekends', 'Weekends'),
    ]
    TIME_CHOICES = [
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
    ]
    DAYS_CHOICES = [
        ('mon_wed_fri', 'Mon / Wed / Fri'),
        ('tue_thu_fri', 'Tue / Thu / Fri'),
        ('tue_thu_sat', 'Tue / Thu / Sat'),
        ('weekend', 'Weekend (Fri & Sat)'),
        ('fri_sat', 'Fri (4-6pm) & Sat (9am-3pm)'),
        ('saturday_only', 'Saturday Only'),
    ]

    name = models.CharField(max_length=100)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='batches',
        help_text="Academy tenant running this batch."
    )
    course = models.ForeignKey(
        Course,
        related_name='batches',
        on_delete=models.CASCADE
    )
    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    batch_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    session_period = models.CharField(max_length=10, choices=TIME_CHOICES)
    days_pattern = models.CharField(max_length=20, choices=DAYS_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    duration_weeks = models.PositiveIntegerField(default=6)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'profile__role': 'hod'}
    )

    max_students = models.PositiveIntegerField(default=20)
    is_published = models.BooleanField(default=False)
    is_full = models.BooleanField(default=False)  # persistent flag for filled batches

    @property
    def schedule_display(self):
        """Clean human-readable schedule description without repeating the course name."""
        days = self.get_days_pattern_display() or self.days_pattern
        time_slot = self.get_session_period_display() or self.session_period
        mode = self.get_mode_display() or self.mode
        return f"{days} • {time_slot.title()} ({mode.title()})"

    def __str__(self):
        status = "✅" if self.is_published else "❌"
        full_flag = " (Full)" if self.is_full else ""
        return f"{self.course.name} / {self.schedule_display}{full_flag} {status}"

    @property
    def current_students(self):
        """Count enrolled students."""
        return self.profile_set.count()

    def check_capacity(self):
        """Auto-update batch capacity and publish status."""
        was_full = self.is_full
        self.is_full = self.current_students >= self.max_students
        if self.is_full:
            self.is_published = False  # auto unpublish full batch
        if was_full != self.is_full:
            self.save(update_fields=['is_full', 'is_published'])

    def save(self, *args, **kwargs):
        newly_published = self.pk and not Batch.objects.get(pk=self.pk).is_published and self.is_published
        super().save(*args, **kwargs)
        if newly_published:
            send_new_session_announcement(self.course.name, self.start_date)



class ClassSession(models.Model):
    DAY_CHOICES = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
    ]
    TIME_CHOICES = [
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
    ]

    batch = models.ForeignKey(
        Batch,
        related_name='sessions',
        on_delete=models.CASCADE
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE
    )
    instructor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'profile__role': 'instructor'}
    )
    day = models.CharField(max_length=10, choices=DAY_CHOICES)
    time_period = models.CharField(max_length=10, choices=TIME_CHOICES)
    duration_hours = models.PositiveIntegerField(default=3)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    class Meta:
        unique_together = ('batch', 'day', 'time_period')

    def __str__(self):
        return f"{self.batch.name} - {self.subject.name} ({self.day})"
