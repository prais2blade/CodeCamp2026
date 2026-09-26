from rest_framework import serializers
from .models import (
    PracticalProblem,
    TestCase,
    PracticalSubmission,
    TestCaseResult,
    DefenseSession,
    DefenseQuestion,
    FinalPracticalGrade
)


class TestCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestCase
        fields = ['id', 'title', 'input_data', 'expected_output', 'is_hidden', 'points', 'order']


class PracticalProblemListSerializer(serializers.ModelSerializer):
    test_cases_count = serializers.IntegerField(source='test_cases.count', read_only=True)
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)
    language_display = serializers.CharField(source='get_language_display', read_only=True)

    class Meta:
        model = PracticalProblem
        fields = [
            'id', 'title', 'slug', 'difficulty', 'difficulty_display',
            'language', 'language_display', 'time_limit_sec', 'memory_limit_mb',
            'weight_practical_pct', 'weight_defense_pct', 'test_cases_count',
            'created_at'
        ]


class PracticalProblemDetailSerializer(serializers.ModelSerializer):
    sample_test_cases = serializers.SerializerMethodField()
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)
    language_display = serializers.CharField(source='get_language_display', read_only=True)

    class Meta:
        model = PracticalProblem
        fields = [
            'id', 'title', 'slug', 'difficulty', 'difficulty_display',
            'language', 'language_display', 'description', 'starter_code',
            'time_limit_sec', 'memory_limit_mb', 'weight_practical_pct',
            'weight_defense_pct', 'sample_test_cases', 'created_at'
        ]

    def get_sample_test_cases(self, obj):
        # Expose only non-hidden sample test cases to students
        samples = obj.sample_test_cases
        return TestCaseSerializer(samples, many=True).data


class RunCodeRequestSerializer(serializers.Serializer):
    problem_id = serializers.IntegerField()
    code = serializers.CharField(allow_blank=False)
    language = serializers.CharField(default='python')
    is_submission = serializers.BooleanField(default=False)
    
    # Telemetry
    paste_detected = serializers.BooleanField(default=False)
    paste_chars = serializers.IntegerField(default=0)
    keystrokes = serializers.IntegerField(default=0)
    duration_sec = serializers.IntegerField(default=0)


class DefenseQuestionSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = DefenseQuestion
        fields = [
            'id', 'order', 'category', 'category_display', 'prompt',
            'target_code_snippet', 'options', 'time_limit_sec',
            'student_answer', 'is_correct', 'score', 'answered_at'
        ]


class DefenseAnswerRequestSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    student_answer = serializers.CharField(allow_blank=False)
    time_spent_sec = serializers.IntegerField(default=0)


class DefenseSessionSerializer(serializers.ModelSerializer):
    questions = DefenseQuestionSerializer(many=True, read_only=True)
    student_username = serializers.CharField(source='student.username', read_only=True)
    problem_title = serializers.CharField(source='submission.problem.title', read_only=True)

    class Meta:
        model = DefenseSession
        fields = [
            'id', 'status', 'student_username', 'problem_title',
            'started_at', 'completed_at', 'total_defense_score',
            'tutor_reviewed', 'tutor_review_notes', 'tutor_override_score',
            'cheating_risk_score', 'cheating_risk_reason', 'questions'
        ]


class FinalPracticalGradeSerializer(serializers.ModelSerializer):
    student_username = serializers.CharField(source='student.username', read_only=True)
    problem_title = serializers.CharField(source='problem.title', read_only=True)

    class Meta:
        model = FinalPracticalGrade
        fields = [
            'id', 'student_username', 'problem_title', 'practical_score',
            'defense_score', 'final_score', 'status', 'certificate_recommendation',
            'calculated_at'
        ]
