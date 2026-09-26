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



DEFAULT_RUBRIC = [
    {"key": "functionality", "name": "Functionality & Logic", "weight": 40, "description": "Solves problem, handles edge cases, zero fatal bugs."},
    {"key": "code_quality", "name": "Code Quality & Architecture", "weight": 25, "description": "Clean, readable, modular structure, good naming."},
    {"key": "ui_ux", "name": "UI/UX & Presentation", "weight": 20, "description": "Visual aesthetics, responsiveness, documentation/README."},
    {"key": "best_practices", "name": "Best Practices & Timeliness", "weight": 15, "description": "Git commit cleanliness and on-time submission."}
]


class Assignment(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assignments')
    batch = models.ForeignKey('scheduling.Batch', on_delete=models.SET_NULL, null=True, blank=True, related_name='assignments')
    week_number = models.PositiveIntegerField(default=1, help_text="Curriculum week number (e.g. 1, 2, 3...)")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    max_score = models.PositiveIntegerField(default=100)
    rubric_template = models.JSONField(default=list, blank=True, help_text="Rubric criteria definition")
    file = models.FileField(upload_to='assignments/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['week_number', 'due_date']

    def __str__(self):
        return f"Week {self.week_number}: {self.title} ({self.subject.name})"

    def get_rubric(self):
        if self.rubric_template and isinstance(self.rubric_template, list) and len(self.rubric_template) > 0:
            return self.rubric_template
        return DEFAULT_RUBRIC


class Submission(models.Model):
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('graded', 'Graded'),
        ('revision_requested', 'Revision Requested'),
    ]

    GRADE_CHOICES = [
        ('Distinction', 'Distinction / Excellent'),
        ('Merit', 'Merit / Very Good'),
        ('Credit', 'Credit / Good'),
        ('Pass', 'Pass'),
        ('Needs Revision', 'Needs Revision'),
    ]

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='course_submissions')
    file = models.FileField(upload_to='submissions/', blank=True, null=True)
    repo_url = models.URLField(max_length=300, blank=True, help_text="GitHub or source repository link")
    live_demo_url = models.URLField(max_length=300, blank=True, help_text="Live URL or deployment link")
    notes = models.TextField(blank=True, help_text="Student remarks / self-reflection")
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='submitted')
    rubric_scores = models.JSONField(default=dict, blank=True, help_text="Points awarded per rubric pillar")
    total_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    letter_grade = models.CharField(max_length=50, blank=True, choices=GRADE_CHOICES)
    
    grade = models.CharField(max_length=20, blank=True, null=True) # backward compat
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_submissions')
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']
        unique_together = ('assignment', 'student')

    def __str__(self):
        return f"{self.student.username} - {self.assignment.title} ({self.status})"

    def calculate_letter_grade(self):
        if self.total_score is None:
            return None
        score = float(self.total_score)
        if score >= 90:
            return 'Distinction'
        elif score >= 75:
            return 'Merit'
        elif score >= 60:
            return 'Credit'
        elif score >= 50:
            return 'Pass'
        else:
            return 'Needs Revision'

