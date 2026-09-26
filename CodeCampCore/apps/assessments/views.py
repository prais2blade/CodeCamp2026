from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes

from .models import (
    PracticalProblem,
    TestCase,
    PracticalSubmission,
    TestCaseResult,
    DefenseSession,
    DefenseQuestion,
    FinalPracticalGrade
)
from .serializers import (
    PracticalProblemListSerializer,
    PracticalProblemDetailSerializer,
    RunCodeRequestSerializer,
    DefenseQuestionSerializer,
    DefenseAnswerRequestSerializer,
    DefenseSessionSerializer,
    FinalPracticalGradeSerializer
)
from .runner import get_code_runner
from .defense import CodeDefenseEngine


# ============================================================================
# REST API ENDPOINTS
# ============================================================================

class PracticalProblemListAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        problems = PracticalProblem.objects.filter(is_active=True)
        difficulty = request.query_params.get('difficulty')
        language = request.query_params.get('language')
        if difficulty:
            problems = problems.filter(difficulty=difficulty)
        if language:
            problems = problems.filter(language=language)
            
        serializer = PracticalProblemListSerializer(problems, many=True)
        return Response(serializer.data)


class PracticalProblemDetailAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        problem = get_object_or_404(PracticalProblem, slug=slug, is_active=True)
        serializer = PracticalProblemDetailSerializer(problem)
        return Response(serializer.data)


class RunCodeAPIView(APIView):
    """
    Executes student code using the isolated runner.
    If is_submission=False: runs ONLY against non-hidden sample test cases.
    If is_submission=True: runs against ALL test cases (including hidden),
    saves the PracticalSubmission, and prepares the Code Defense session.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = RunCodeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        problem = get_object_or_404(PracticalProblem, id=data['problem_id'], is_active=True)
        code = data['code']
        language = data.get('language', problem.language)
        is_submission = data.get('is_submission', False)

        test_cases = problem.all_test_cases if is_submission else problem.sample_test_cases
        if not test_cases.exists():
            return Response(
                {"error": "No test cases configured for this problem."},
                status=status.HTTP_400_BAD_REQUEST
            )

        runner = get_code_runner()
        evaluations = runner.evaluate_test_cases(
            code=code,
            language=language,
            test_cases=list(test_cases),
            timeout_sec=problem.time_limit_sec,
            memory_limit_mb=problem.memory_limit_mb
        )

        passed_count = sum(1 for e in evaluations if e.passed)
        total_count = len(evaluations)
        total_points_awarded = sum(e.points_awarded for e in evaluations)
        total_possible = sum(e.points_possible for e in evaluations)
        practical_score = round((total_points_awarded / max(total_possible, 1)) * 100, 2)
        total_time_ms = sum(e.execution_time_ms for e in evaluations)

        # Prepare evaluation response format
        results_data = []
        for e in evaluations:
            # If hidden test case and not a staff user, mask the input/output details
            is_staff = request.user.is_staff
            results_data.append({
                "test_case_id": e.test_case_id,
                "title": e.title,
                "passed": e.passed,
                "input_data": e.input_data if (not e.is_hidden or is_staff) else "🔒 Hidden Test Input",
                "expected_output": e.expected_output if (not e.is_hidden or is_staff) else "🔒 Hidden",
                "actual_output": e.actual_output if (not e.is_hidden or is_staff) else ("Matches expected" if e.passed else "Mismatch"),
                "error_message": e.error_message,
                "execution_time_ms": e.execution_time_ms,
                "is_hidden": e.is_hidden,
                "points_awarded": e.points_awarded,
                "points_possible": e.points_possible
            })

        response_data = {
            "is_submission": is_submission,
            "tests_passed": passed_count,
            "tests_total": total_count,
            "practical_score": practical_score,
            "total_execution_time_ms": total_time_ms,
            "results": results_data,
        }

        # If full submission, record PracticalSubmission in database
        if is_submission:
            sub_status = 'passed' if passed_count == total_count else ('partial' if passed_count > 0 else 'failed')
            submission = PracticalSubmission.objects.create(
                problem=problem,
                student=request.user,
                submitted_code=code,
                language=language,
                status='defense_pending' if passed_count > 0 else sub_status,
                practical_score=practical_score,
                tests_passed=passed_count,
                tests_total=total_count,
                execution_time_ms=total_time_ms,
                telemetry_paste_detected=data.get('paste_detected', False),
                telemetry_paste_chars=data.get('paste_chars', 0),
                telemetry_keystrokes=data.get('keystrokes', 0),
                telemetry_duration_sec=data.get('duration_sec', 0),
            )

            # Record individual test case results
            for e in evaluations:
                tc_obj = TestCase.objects.filter(id=e.test_case_id).first()
                if tc_obj:
                    TestCaseResult.objects.create(
                        submission=submission,
                        test_case=tc_obj,
                        passed=e.passed,
                        actual_output=e.actual_output,
                        error_message=e.error_message,
                        execution_time_ms=e.execution_time_ms
                    )

            # Auto-initialize Code Defense Session
            session = CodeDefenseEngine.initialize_session_for_submission(submission)
            response_data["submission_id"] = submission.id
            response_data["defense_session_id"] = session.id
            response_data["defense_status"] = session.status

        return Response(response_data)


class DefenseSessionAPIView(APIView):
    """
    Retrieve or start defense session for a submission.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(DefenseSession, id=session_id)
        if session.student != request.user and not request.user.is_staff:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        serializer = DefenseSessionSerializer(session)
        return Response(serializer.data)


class SubmitDefenseAnswerAPIView(APIView):
    """
    Submits student's response to an individual defense question.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = DefenseAnswerRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        question = get_object_or_404(DefenseQuestion, id=data['question_id'])
        if question.session.student != request.user and not request.user.is_staff:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        updated_q = CodeDefenseEngine.submit_answer(
            question=question,
            student_answer=data['student_answer'],
            time_spent_sec=data.get('time_spent_sec', 0)
        )

        session = updated_q.session
        return Response({
            "question_id": updated_q.id,
            "is_correct": updated_q.is_correct,
            "score": updated_q.score,
            "session_status": session.status,
            "total_defense_score": session.total_defense_score,
            "cheating_risk_score": session.cheating_risk_score
        })


class TutorDefenseReviewAPIView(APIView):
    """
    Allows instructors/tutors to inspect flagged sessions, override defense scores,
    and approve final practical marks.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        flagged_sessions = DefenseSession.objects.filter(
            Q(status='flagged') | Q(cheating_risk_score__gte=0.50)
        ).select_related('student', 'submission__problem').order_by('-started_at')
        serializer = DefenseSessionSerializer(flagged_sessions, many=True)
        return Response(serializer.data)

    def post(self, request, session_id):
        session = get_object_or_404(DefenseSession, id=session_id)
        override_score = request.data.get('override_score')
        tutor_notes = request.data.get('tutor_notes', '')

        if override_score is not None:
            try:
                session.tutor_override_score = float(override_score)
            except ValueError:
                return Response({"error": "Invalid override score"}, status=status.HTTP_400_BAD_REQUEST)

        session.tutor_reviewed = True
        session.tutor_review_notes = tutor_notes
        session.status = 'completed'
        session.save()

        # Re-compute FinalPracticalGrade
        final_grade = CodeDefenseEngine.evaluate_integrity_and_finalize_grade(session)
        final_grade.save()

        return Response({
            "message": "Review recorded successfully",
            "final_score": final_grade.final_score,
            "status": final_grade.status,
            "certificate_recommendation": final_grade.certificate_recommendation
        })


# ============================================================================
# TEMPLATE-BASED WEB VIEWS (Monaco Workspace, Review Queue, Student Hub)
# ============================================================================

@login_required
def student_assessment_hub(request):
    """
    Student assessment hub showing available practical coding problems,
    their personal submission records, and defense pass badges.
    """
    problems = PracticalProblem.objects.filter(is_active=True).order_by('difficulty', '-created_at')
    user_grades = FinalPracticalGrade.objects.filter(student=request.user).select_related('problem')
    grade_map = {g.problem_id: g for g in user_grades}

    problem_list = []
    for p in problems:
        grade = grade_map.get(p.id)
        problem_list.append({
            'problem': p,
            'grade': grade,
            'is_completed': grade and grade.status in ('Distinction', 'Merit', 'Credit', 'Pass')
        })

    context = {
        'problems': problem_list,
        'completed_count': sum(1 for item in problem_list if item['is_completed']),
        'total_count': len(problem_list),
    }
    return render(request, 'assessments/student_hub.html', context)


@login_required
def problem_workspace(request, slug):
    """
    Full Monaco-based code development environment:
    - Split-pane problem description (Markdown) and live code editor
    - Run Sample Tests button with live test result card
    - Submit Solution & Enter Code Defense button
    - Timed defense challenge modal with AST-derived questions
    """
    problem = get_object_or_404(PracticalProblem, slug=slug, is_active=True)
    sample_tests = problem.sample_test_cases
    latest_grade = FinalPracticalGrade.objects.filter(student=request.user, problem=problem).first()

    context = {
        'problem': problem,
        'sample_tests': sample_tests,
        'latest_grade': latest_grade,
    }
    return render(request, 'assessments/problem_workspace.html', context)


@login_required
def tutor_defense_queue(request):
    """
    Instructor/Tutor Review Center:
    - Lists all flagged student submissions (mismatches between practical and defense)
    - High paste velocity alerts
    - Score override sliders with 1-click approval
    """
    if not (request.user.is_staff or getattr(request.user, 'profile', None) and request.user.profile.role in ('instructor', 'admin')):
        messages.error(request, "Access restricted to instructors and administrators.")
        return redirect('dashboard')

    sessions = DefenseSession.objects.select_related(
        'student', 'submission__problem'
    ).prefetch_related('questions').order_by('-cheating_risk_score', '-started_at')

    context = {
        'sessions': sessions,
        'flagged_count': sessions.filter(status='flagged').count(),
    }
    return render(request, 'assessments/tutor_review_queue.html', context)
