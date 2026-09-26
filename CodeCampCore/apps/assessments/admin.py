from django.contrib import admin
from .models import (
    PracticalProblem,
    TestCase,
    PracticalSubmission,
    TestCaseResult,
    DefenseSession,
    DefenseQuestion,
    FinalPracticalGrade
)


class TestCaseInline(admin.TabularInline):
    model = TestCase
    extra = 1
    fields = ('order', 'title', 'is_hidden', 'points', 'input_data', 'expected_output')


@admin.register(PracticalProblem)
class PracticalProblemAdmin(admin.ModelAdmin):
    list_display = ('title', 'difficulty', 'language', 'weight_practical_pct', 'weight_defense_pct', 'is_active', 'created_at')
    list_filter = ('difficulty', 'language', 'is_active')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [TestCaseInline]


class TestCaseResultInline(admin.TabularInline):
    model = TestCaseResult
    extra = 0
    readonly_fields = ('test_case', 'passed', 'execution_time_ms', 'actual_output', 'error_message')
    can_delete = False


@admin.register(PracticalSubmission)
class PracticalSubmissionAdmin(admin.ModelAdmin):
    list_display = ('student', 'problem', 'status', 'practical_score', 'tests_passed', 'tests_total', 'telemetry_paste_detected', 'submitted_at')
    list_filter = ('status', 'telemetry_paste_detected', 'language')
    search_fields = ('student__username', 'problem__title')
    readonly_fields = ('submitted_at', 'execution_time_ms')
    inlines = [TestCaseResultInline]


class DefenseQuestionInline(admin.StackedInline):
    model = DefenseQuestion
    extra = 0
    fields = ('order', 'category', 'prompt', 'student_answer', 'is_correct', 'score', 'time_spent_sec', 'ai_evaluation_notes')


@admin.register(DefenseSession)
class DefenseSessionAdmin(admin.ModelAdmin):
    list_display = ('student', 'submission', 'status', 'total_defense_score', 'cheating_risk_score', 'tutor_reviewed', 'started_at')
    list_filter = ('status', 'tutor_reviewed')
    search_fields = ('student__username', 'submission__problem__title')
    inlines = [DefenseQuestionInline]


@admin.register(FinalPracticalGrade)
class FinalPracticalGradeAdmin(admin.ModelAdmin):
    list_display = ('student', 'problem', 'practical_score', 'defense_score', 'final_score', 'status', 'certificate_recommendation', 'calculated_at')
    list_filter = ('status',)
    search_fields = ('student__username', 'problem__title')
