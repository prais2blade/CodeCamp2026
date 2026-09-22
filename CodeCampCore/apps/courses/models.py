from django.db import models
from django.contrib.auth.models import User

from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User

class Course(models.Model):
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='courses',
        help_text="Academy tenant offering this course."
    )
    # Core fields
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)

    duration_weeks = models.PositiveIntegerField(default=6)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Website + LMS media
    image = models.ImageField(upload_to="courses/images/", blank=True, null=True)
    brochure = models.FileField(upload_to="courses/brochures/", blank=True, null=True)

    # Publishing
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "✅" if self.is_published else "❌"
        return f"{self.name} {status}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)



class Subject(models.Model):
    course = models.ForeignKey(Course, related_name='subjects', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    instructor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={'profile__role': 'instructor'})

    def __str__(self):
        return f"{self.name} ({self.course.name})"



class Assignment(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    file = models.FileField(upload_to='assignments/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.subject.name})"


class Submission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to='submissions/')
    submitted_at = models.DateTimeField(auto_now_add=True)
    grade = models.CharField(max_length=10, blank=True, null=True)
    feedback = models.TextField(blank=True)

    def __str__(self):
        return f"{self.student.username} - {self.assignment.title}"
