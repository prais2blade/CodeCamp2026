from django.utils import timezone
from apps.assessments.models import (
    PracticalSubmission,
    DefenseSession,
    DefenseQuestion,
    FinalPracticalGrade
)
from .ast_analyzer import DefenseQuestionGenerator


class CodeDefenseEngine:
    """
    Orchestrates the Code Defense verification workflow:
    - Automatically analyzes submitted solution syntax and structure
    - Generates 3 contextual defense challenges (Explain, Predict, Modify)
    - Records and scores student defense answers in real time
    - Detects cheating anomalies (paste velocity + defense-practical mismatches)
    - Computes FinalPracticalGrade combining practical test score + defense score
    """

    @classmethod
    def initialize_session_for_submission(cls, submission: PracticalSubmission) -> DefenseSession:
        session, created = DefenseSession.objects.get_or_create(
            submission=submission,
            defaults={
                'student': submission.student,
                'status': 'active',
                'started_at': timezone.now(),
            }
        )

        # If freshly created or has no questions, generate them now
        if not session.questions.exists():
            generated_qs = DefenseQuestionGenerator.generate_defense_questions(
                code=submission.submitted_code,
                language=submission.language
            )

            for item in generated_qs:
                DefenseQuestion.objects.create(
                    session=session,
                    order=item.get("order", 1),
                    category=item.get("category", "explain"),
                    prompt=item.get("prompt"),
                    target_code_snippet=item.get("target_code_snippet", ""),
                    options=item.get("options", []),
                    correct_answer=item.get("correct_answer", ""),
                    time_limit_sec=item.get("time_limit_sec", 90),
                    ai_evaluation_notes=item.get("rubric_notes", "")
                )

        return session

    @classmethod
    def submit_answer(
        cls,
        question: DefenseQuestion,
        student_answer: str,
        time_spent_sec: int = 0
    ) -> DefenseQuestion:
        session = question.session
        clean_ans = (student_answer or "").strip()
        expected = (question.correct_answer or "").strip()

        question.student_answer = clean_ans
        question.time_spent_sec = time_spent_sec
        question.answered_at = timezone.now()

        # Grade response
        is_match = (clean_ans.upper() == expected.upper())
        question.is_correct = is_match

        if is_match:
            # Full marks
            question.score = 100.0
            question.ai_evaluation_notes += " Correctly validated by assessment engine."
        else:
            question.score = 0.0
            question.ai_evaluation_notes += f" Incorrect answer '{clean_ans}'. Expected '{expected}'."

        question.save()

        # Check if all questions for this session have been answered
        all_qs = session.questions.all()
        answered_count = all_qs.filter(answered_at__isnull=False).count()
        total_count = all_qs.count()

        if answered_count >= total_count:
            session.status = 'completed'
            session.completed_at = timezone.now()
            session.calculate_defense_score()
            cls.evaluate_integrity_and_finalize_grade(session)

        session.save()
        return question

    @classmethod
    def evaluate_integrity_and_finalize_grade(cls, session: DefenseSession) -> FinalPracticalGrade:
        submission = session.submission
        practical_score = submission.practical_score
        defense_score = session.total_defense_score

        # Calculate Cheating Risk Score (0.0 to 1.0)
        risk = 0.0
        reasons = []

        # 1. Telemetry Paste Flag (+0.35)
        if submission.telemetry_paste_detected:
            risk += 0.35
            reasons.append(f"High paste velocity: {submission.telemetry_paste_chars} chars pasted instantaneously.")

        # 2. Score Mismatch (+0.50)
        # Passed 100% of tests, but scored very poorly on defense
        if practical_score >= 80 and defense_score < 40:
            risk += 0.50
            reasons.append(f"Significant comprehension mismatch: Practical tests ({practical_score}%) vs Defense score ({defense_score}%).")

        # 3. Suspiciously fast answers across defense questions
        avg_time = 0
        qs = session.questions.all()
        if qs.exists():
            avg_time = sum(q.time_spent_sec for q in qs) / qs.count()
            if avg_time < 4.0:
                risk += 0.20
                reasons.append("Defense questions answered in under 4 seconds per question (potential random guessing).")

        session.cheating_risk_score = min(1.0, round(risk, 2))
        session.cheating_risk_reason = " | ".join(reasons) if reasons else "No anomalous activity detected."

        if session.cheating_risk_score >= 0.70:
            session.status = 'flagged'

        session.save()

        # Update or create FinalPracticalGrade
        final_grade, _ = FinalPracticalGrade.objects.get_or_create(
            student=session.student,
            problem=submission.problem,
            defaults={
                'submission': submission,
                'defense_session': session,
                'practical_score': practical_score,
                'defense_score': defense_score
            }
        )

        final_grade.submission = submission
        final_grade.defense_session = session
        final_grade.practical_score = practical_score
        final_grade.defense_score = defense_score
        final_grade.compute_composite_score()
        final_grade.save()

        # Mark submission as completed
        submission.status = 'completed'
        submission.save()

        return final_grade
