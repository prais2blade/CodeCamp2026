import uuid
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone


class PracticalProblem(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    LANGUAGE_CHOICES = [
        ('python', 'Python 3'),
        ('javascript', 'JavaScript (Node.js)'),
        ('sql', 'SQL (SQLite)'),
    ]

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='practical_problems',
        help_text="Academy tenant offering this assessment."
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='practical_problems'
    )
    batch = models.ForeignKey(
        'scheduling.Batch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='practical_problems'
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='medium')
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='python')
    description = models.TextField(help_text="Problem statement and requirements in Markdown")
    starter_code = models.TextField(blank=True, help_text="Default boilerplate code for student editor")
    solution_template = models.TextField(blank=True, help_text="Reference solution code for verification")
    
    time_limit_sec = models.FloatField(default=2.0, help_text="Max execution time in seconds per test case")
    memory_limit_mb = models.IntegerField(default=128, help_text="RAM limit in Megabytes")
    
    weight_practical_pct = models.IntegerField(default=70, help_text="Percentage weight of unit tests (e.g. 70%)")
    weight_defense_pct = models.IntegerField(default=30, help_text="Percentage weight of code defense (e.g. 30%)")
    
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_problems'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_difficulty_display()}] {self.title} ({self.get_language_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title) or 'problem'
            unique_suffix = uuid.uuid4().hex[:6]
            self.slug = f"{base_slug}-{unique_suffix}"
        super().save(*args, **kwargs)

    @property
    def sample_test_cases(self):
        return self.test_cases.filter(is_hidden=False).order_by('order', 'id')

    @property
    def all_test_cases(self):
        return self.test_cases.all().order_by('order', 'id')


class TestCase(models.Model):
    problem = models.ForeignKey(
        PracticalProblem,
        on_delete=models.CASCADE,
        related_name='test_cases'
    )
    title = models.CharField(max_length=150, blank=True, default='Test Case')
    input_data = models.TextField(blank=True, help_text="Input data (stdin or arguments representation)")
    expected_output = models.TextField(help_text="Expected stdout or return value")
    is_hidden = models.BooleanField(
        default=False,
        help_text="If True, hidden from students during practice; evaluated upon submission"
    )
    points = models.IntegerField(default=10, help_text="Points allocated to this test case")
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        badge = "🔒 Hidden" if self.is_hidden else "👁️ Sample"
        return f"{self.problem.title} - {self.title} [{badge}]"


class PracticalSubmission(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft / In Progress'),
        ('running', 'Running Tests'),
        ('passed', 'All Tests Passed'),
        ('partial', 'Partially Passed'),
        ('failed', 'Tests Failed'),
        ('error', 'Execution Error / Timeout'),
        ('defense_pending', 'Defense Pending'),
        ('completed', 'Completed & Graded'),
    ]

    problem = models.ForeignKey(
        PracticalProblem,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='practical_submissions'
    )
    submitted_code = models.TextField()
    language = models.CharField(max_length=20, default='python')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    
    practical_score = models.FloatField(default=0.0, help_text="0-100 calculated from test cases")
    tests_passed = models.IntegerField(default=0)
    tests_total = models.IntegerField(default=0)
    execution_time_ms = models.FloatField(default=0.0)
    memory_used_kb = models.FloatField(default=0.0)

    # Telemetry and anti-cheat tracking
    telemetry_paste_detected = models.BooleanField(
        default=False,
        help_text="True if a large code block was pasted instantaneously"
    )
    telemetry_paste_chars = models.IntegerField(default=0)
    telemetry_keystrokes = models.IntegerField(default=0)
    telemetry_duration_sec = models.IntegerField(default=0)

    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.student.username} - {self.problem.title} ({self.status}: {self.practical_score}%)"

    @property
    def has_defense(self):
        return hasattr(self, 'defense_session')


class TestCaseResult(models.Model):
    submission = models.ForeignKey(
        PracticalSubmission,
        on_delete=models.CASCADE,
        related_name='case_results'
    )
    test_case = models.ForeignKey(
        TestCase,
        on_delete=models.CASCADE,
        related_name='results'
    )
    passed = models.BooleanField(default=False)
    actual_output = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    execution_time_ms = models.FloatField(default=0.0)

    def __str__(self):
        result = "PASSED" if self.passed else "FAILED"
        return f"Result {self.id}: {self.test_case.title} - {result}"


class DefenseSession(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Not Started'),
        ('active', 'In Progress'),
        ('completed', 'Completed'),
        ('expired', 'Expired / Timed Out'),
        ('flagged', 'Flagged for Tutor Review'),
    ]

    submission = models.OneToOneField(
        PracticalSubmission,
        on_delete=models.CASCADE,
        related_name='defense_session'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='defense_sessions'
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    total_defense_score = models.FloatField(default=0.0, help_text="0-100 average defense score")
    tutor_reviewed = models.BooleanField(default=False)
    tutor_review_notes = models.TextField(blank=True)
    tutor_override_score = models.FloatField(null=True, blank=True)
    
    cheating_risk_score = models.FloatField(
        default=0.0,
        help_text="0.0 (low risk) to 1.0 (high risk), evaluated from paste velocity + defense-practical mismatch"
    )
    cheating_risk_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Defense: {self.student.username} on {self.submission.problem.title} ({self.status})"

    def calculate_defense_score(self):
        questions = self.questions.all()
        if not questions.exists():
            return 0.0
        scores = [q.score for q in questions if q.score is not None]
        if not scores:
            return 0.0
        avg = sum(scores) / len(scores)
        self.total_defense_score = round(avg, 2)
        return self.total_defense_score


class DefenseQuestion(models.Model):
    CATEGORY_CHOICES = [
        ('explain', 'Code Explanation & Complexity'),
        ('predict', 'Predict Output on Mutant Input'),
        ('modify', 'Modify Edge Case / Refactor'),
    ]

    session = models.ForeignKey(
        DefenseSession,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    order = models.IntegerField(default=1)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='explain')
    prompt = models.TextField(help_text="The defense question posed to the student")
    target_code_snippet = models.TextField(
        blank=True,
        help_text="Student code lines or construct referenced by this question"
    )
    options = models.JSONField(
        default=list,
        blank=True,
        help_text="Multiple-choice options if applicable: [{'key': 'A', 'text': '...'}, ...]"
    )
    correct_answer = models.TextField(blank=True, help_text="Expected key or rubric answer")
    student_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    score = models.FloatField(default=0.0, help_text="Question score (0-100)")
    ai_evaluation_notes = models.TextField(blank=True)
    
    time_limit_sec = models.IntegerField(default=90, help_text="Time limit in seconds for this question")
    time_spent_sec = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Q{self.order} [{self.get_category_display()}] - {self.session.student.username}"


class FinalPracticalGrade(models.Model):
    STATUS_CHOICES = [
        ('Distinction', 'Distinction (>= 85%)'),
        ('Merit', 'Merit (70% - 84%)'),
        ('Credit', 'Credit (60% - 69%)'),
        ('Pass', 'Pass (50% - 59%)'),
        ('Fail', 'Fail (< 50%)'),
        ('Review Needed', 'Flagged / Tutor Review Needed'),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='final_practical_grades'
    )
    problem = models.ForeignKey(
        PracticalProblem,
        on_delete=models.CASCADE,
        related_name='final_grades'
    )
    submission = models.ForeignKey(
        PracticalSubmission,
        on_delete=models.CASCADE,
        related_name='final_grade'
    )
    defense_session = models.ForeignKey(
        DefenseSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='final_grade'
    )
    practical_score = models.FloatField(default=0.0)
    defense_score = models.FloatField(default=0.0)
    final_score = models.FloatField(default=0.0, help_text="Composite weighted score")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Pass')
    certificate_recommendation = models.CharField(max_length=50, blank=True)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-calculated_at']
        unique_together = ('student', 'problem')

    def __str__(self):
        return f"{self.student.username} - {self.problem.title}: {self.final_score}% ({self.status})"

    def compute_composite_score(self):
        p_weight = self.problem.weight_practical_pct / 100.0
        d_weight = self.problem.weight_defense_pct / 100.0
        
        # If tutor has overridden defense score, use that
        effective_defense = self.defense_score
        if self.defense_session and self.defense_session.tutor_override_score is not None:
            effective_defense = self.defense_session.tutor_override_score

        self.final_score = round((self.practical_score * p_weight) + (effective_defense * d_weight), 2)

        # Flag for review if high mismatch (e.g. 100% practical but < 35% defense)
        if self.practical_score >= 80 and effective_defense < 40:
            self.status = 'Review Needed'
            self.certificate_recommendation = 'On Hold (Defense Mismatch)'
            if self.defense_session:
                self.defense_session.cheating_risk_score = 0.85
                self.defense_session.cheating_risk_reason = "High practical test score with low code defense comprehension."
                self.defense_session.status = 'flagged'
                self.defense_session.save()
        elif self.final_score >= 85:
            self.status = 'Distinction'
            self.certificate_recommendation = 'Distinction / Excellent'
        elif self.final_score >= 70:
            self.status = 'Merit'
            self.certificate_recommendation = 'Merit / Very Good'
        elif self.final_score >= 60:
            self.status = 'Credit'
            self.certificate_recommendation = 'Credit / Good'
        elif self.final_score >= 50:
            self.status = 'Pass'
            self.certificate_recommendation = 'Pass'
        else:
            self.status = 'Fail'
            self.certificate_recommendation = 'Needs Retake'

        return self.final_score
