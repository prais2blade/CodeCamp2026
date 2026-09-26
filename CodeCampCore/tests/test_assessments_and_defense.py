import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from apps.assessments.models import (
    PracticalProblem,
    TestCase as ProblemTestCase,
    PracticalSubmission,
    DefenseSession,
    DefenseQuestion,
    FinalPracticalGrade
)
from apps.assessments.runner import SubprocessSandboxRunner
from apps.assessments.defense import PythonASTAnalyzer, DefenseQuestionGenerator, CodeDefenseEngine


class PracticalAssessmentAndDefenseTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            username='student_coder',
            password='password123',
            first_name='Alex',
            last_name='Dev'
        )
        self.staff_user = User.objects.create_superuser(
            username='tutor_chief',
            password='password123',
            email='tutor@codecamp.org'
        )

        # Create a sample problem
        self.problem = PracticalProblem.objects.create(
            title="Two Sum Target Finder",
            difficulty="easy",
            language="python",
            description="Given an array of integers and a target integer, return the indices of two numbers that add up to target.",
            starter_code="def two_sum(nums, target):\n    # Return indices\n    pass\n",
            time_limit_sec=2.0,
            memory_limit_mb=128,
            weight_practical_pct=70,
            weight_defense_pct=30
        )

        # Visible test case
        self.tc_visible = ProblemTestCase.objects.create(
            problem=self.problem,
            title="Standard Case",
            input_data="[2, 7, 11, 15]\n9",
            expected_output="0 1",
            is_hidden=False,
            points=10,
            order=1
        )

        # Hidden test case
        self.tc_hidden = ProblemTestCase.objects.create(
            problem=self.problem,
            title="Edge Case Zero",
            input_data="[0, 4, 3, 0]\n0",
            expected_output="0 3",
            is_hidden=True,
            points=10,
            order=2
        )

    def test_runner_python_execution_and_security(self):
        """Verifies safe execution, timeout guard, and blocked security operations."""
        runner = SubprocessSandboxRunner()

        # 1. Normal execution
        safe_code = """
import sys
data = sys.stdin.read().splitlines()
nums = eval(data[0])
target = int(data[1])

mapping = {}
for i, n in enumerate(nums):
    diff = target - n
    if diff in mapping:
        print(f"{mapping[diff]} {i}")
        break
    mapping[n] = i
"""
        res = runner.execute(safe_code, language='python', input_data="[2, 7, 11, 15]\n9", timeout_sec=2.0)
        self.assertTrue(res.is_success)
        self.assertEqual(res.stdout.strip(), "0 1")

        # 2. Security restriction: dangerous imports should be blocked
        malicious_code = """
import subprocess
print("Should be blocked")
"""
        res_blocked = runner.execute(malicious_code, language='python', timeout_sec=2.0)
        self.assertFalse(res_blocked.is_success)
        self.assertEqual(res_blocked.error_type, "SecurityViolation")

        # 3. Timeout guard
        infinite_code = """
while True:
    pass
"""
        res_timeout = runner.execute(infinite_code, language='python', timeout_sec=0.5)
        self.assertTrue(res_timeout.timed_out)
        self.assertEqual(res_timeout.error_type, "TimeLimitExceeded")

    def test_ast_analysis_and_defense_generation(self):
        """Verifies AST extraction of functions, loops, and generation of 3 defense questions."""
        sample_code = """
def find_pairs(nums, target):
    seen = {}
    for idx, val in enumerate(nums):
        complement = target - val
        if complement in seen:
            return [seen[complement], idx]
        seen[val] = idx
    return []
"""
        insights = PythonASTAnalyzer.analyze(sample_code)
        self.assertIn("find_pairs", insights.functions)
        self.assertIn("seen", insights.variables)
        self.assertEqual(insights.loops_count, 1)

        questions = DefenseQuestionGenerator.generate_defense_questions(sample_code, language='python')
        self.assertEqual(len(questions), 3)

        categories = [q['category'] for q in questions]
        self.assertIn('explain', categories)
        self.assertIn('predict', categories)
        self.assertIn('modify', categories)

    def test_submission_and_defense_session_workflow(self):
        """Verifies full end-to-end evaluation, defense session creation, answer grading, and composite score."""
        student_code = """
import sys
lines = sys.stdin.read().splitlines()
nums = eval(lines[0])
target = int(lines[1])
seen = {}
for i, n in enumerate(nums):
    diff = target - n
    if diff in seen:
        print(f"{seen[diff]} {i}")
        break
    seen[n] = i
"""
        runner = SubprocessSandboxRunner()
        evaluations = runner.evaluate_test_cases(
            code=student_code,
            language='python',
            test_cases=list(self.problem.all_test_cases)
        )
        self.assertEqual(len(evaluations), 2)
        self.assertTrue(all(e.passed for e in evaluations))

        # Record PracticalSubmission
        submission = PracticalSubmission.objects.create(
            problem=self.problem,
            student=self.student,
            submitted_code=student_code,
            language='python',
            status='defense_pending',
            practical_score=100.0,
            tests_passed=2,
            tests_total=2,
            telemetry_paste_detected=False
        )

        # Initialize Defense Session
        session = CodeDefenseEngine.initialize_session_for_submission(submission)
        self.assertEqual(session.questions.count(), 3)

        # Answer question 1 correctly
        q1 = session.questions.first()
        CodeDefenseEngine.submit_answer(q1, student_answer=q1.correct_answer, time_spent_sec=15)
        q1.refresh_from_db()
        self.assertTrue(q1.is_correct)
        self.assertEqual(q1.score, 100.0)

        # Answer other questions
        for q in session.questions.filter(answered_at__isnull=True):
            CodeDefenseEngine.submit_answer(q, student_answer=q.correct_answer, time_spent_sec=20)

        session.refresh_from_db()
        self.assertEqual(session.status, 'completed')
        self.assertEqual(session.total_defense_score, 100.0)

        # Verify FinalPracticalGrade composite
        final_grade = FinalPracticalGrade.objects.get(student=self.student, problem=self.problem)
        self.assertEqual(final_grade.final_score, 100.0)
        self.assertEqual(final_grade.status, 'Distinction')

    def test_cheating_telemetry_and_mismatch_flag(self):
        """Verifies that high paste velocity + defense failure flags submission for tutor review."""
        submission = PracticalSubmission.objects.create(
            problem=self.problem,
            student=self.student,
            submitted_code="# pasted solution\nprint('hello')",
            language='python',
            status='defense_pending',
            practical_score=100.0,
            tests_passed=2,
            tests_total=2,
            telemetry_paste_detected=True,
            telemetry_paste_chars=250
        )

        session = CodeDefenseEngine.initialize_session_for_submission(submission)

        # Student fails all defense questions
        for q in session.questions.all():
            CodeDefenseEngine.submit_answer(q, student_answer="WRONG", time_spent_sec=2)

        session.refresh_from_db()
        self.assertEqual(session.status, 'flagged')
        self.assertGreaterEqual(session.cheating_risk_score, 0.70)

        final_grade = FinalPracticalGrade.objects.get(student=self.student, problem=self.problem)
        self.assertEqual(final_grade.status, 'Review Needed')

    def test_api_run_and_defense_endpoints(self):
        """Tests the REST API endpoints."""
        self.client.force_login(self.student)

        # 1. API: List problems
        res = self.client.get('/assessments/api/problems/')
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.json()), 1)

        # 2. API: Run code (sample tests only)
        code = "print('0 1')"
        payload = {
            "problem_id": self.problem.id,
            "code": code,
            "language": "python",
            "is_submission": False
        }
        res_run = self.client.post(
            '/assessments/api/run/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res_run.status_code, 200)
        data = res_run.json()
        self.assertFalse(data['is_submission'])
        self.assertEqual(len(data['results']), 1)  # only sample visible test
