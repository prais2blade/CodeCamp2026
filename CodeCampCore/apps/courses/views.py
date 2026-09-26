from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Course, Subject, Assignment, Submission
from .forms import CourseForm, SubjectForm
from apps.accounts.decorators import role_required, payment_required
from apps.accounts.models import Profile, Attendance
from apps.scheduling.models import Batch
from django.db.models import Q, Avg, Count
from django.utils import timezone



@login_required
@role_required('student')
def choose_course(request):
    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        if course_id:
            request.user.profile.course_id = course_id
            request.user.profile.save()
            messages.success(request, "Course selected.")
            return redirect('choose_batch')
    courses = Course.objects.filter(is_published=True)   # ✅ only published
    return render(request, 'courses/choose_course.html', {'courses': courses})


@login_required
@role_required('student')
@payment_required
def student_course(request):
    course = request.user.profile.course
    if not course:
        messages.info(request, "You haven't chosen a course yet.")
        return redirect('choose_course')
    subjects = course.subjects.all()
    return render(request, 'courses/student_course.html', {'course': course, 'subjects': subjects})


@login_required
def manage_courses(request):
    if not (request.user.is_superuser or request.user.profile.role == 'hod'):
        messages.error(request, "Access denied.")
        return redirect('login')

    courses = Course.objects.all().order_by('-created_at')

    return render(request, 'courses/manage_courses.html', {
        'courses': courses
    })


@login_required
def toggle_course_status(request, course_id):
    if not request.user.is_superuser:
        messages.error(request, "Only admin can change course status.")
        return redirect('manage_courses')

    course = Course.objects.get(id=course_id)
    course.is_published = not course.is_published
    course.save()

    state = "published" if course.is_published else "deactivated"
    messages.success(request, f"Course '{course.name}' {state}.")

    return redirect('manage_courses')


@login_required
def course_create(request):
    if not request.user.is_superuser:
        messages.error(request, "Only admin can create courses.")
        return redirect('manage_courses')

    if request.method == "POST":
        form = CourseForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Course created successfully.")
            return redirect('manage_courses')
    else:
        form = CourseForm()

    return render(request, 'courses/course_form.html', {
        'form': form,
        'title': 'Create Course'
    })


@login_required
def course_edit(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Only admin can edit courses.")
        return redirect('manage_courses')

    course = Course.objects.get(pk=pk)

    if request.method == "POST":
        form = CourseForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, "Course updated successfully.")
            return redirect('manage_courses')
    else:
        form = CourseForm(instance=course)

    return render(request, 'courses/course_form.html', {
        'form': form,
        'title': 'Edit Course'
    })


@login_required
def manage_subjects(request, course_id):
    if not (request.user.is_superuser or request.user.profile.role == 'hod'):
        messages.error(request, "Access denied.")
        return redirect('manage_courses')

    course = Course.objects.get(id=course_id)
    subjects = course.subjects.all()

    return render(request, 'courses/manage_subjects.html', {
        'course': course,
        'subjects': subjects
    })
    
@login_required
def create_subject(request, course_id):
    if not (request.user.is_superuser or request.user.profile.role == 'hod'):
        messages.error(request, "Access denied.")
        return redirect('manage_courses')

    course = Course.objects.get(id=course_id)

    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            subject = form.save(commit=False)
            subject.course = course
            subject.save()

            messages.success(request, "Subject created successfully.")
            return redirect('manage_subjects', course_id=course.id)
    else:
        form = SubjectForm()

    return render(request, 'courses/subject_form.html', {
        'form': form,
        'title': 'Create Subject',
        'course': course
    })
    
@login_required
def edit_subject(request, pk):
    subject = Subject.objects.get(pk=pk)

    if not (request.user.is_superuser or request.user.profile.role == 'hod'):
        messages.error(request, "Access denied.")
        return redirect('manage_courses')

    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, "Subject updated.")
            return redirect('manage_subjects', course_id=subject.course.id)
    else:
        form = SubjectForm(instance=subject)

    return render(request, 'courses/subject_form.html', {
        'form': form,
        'title': 'Edit Subject',
        'course': subject.course
    })
    
    
@login_required
def instructor_subjects(request):
    if request.user.profile.role != 'instructor':
        messages.error(request, "Access denied.")
        return redirect('login')

    subjects = Subject.objects.filter(instructor=request.user)

    return render(request, 'courses/instructor_subjects.html', {
        'subjects': subjects
    })
    


@login_required
def mark_attendance(request, subject_id):
    if request.user.profile.role != 'instructor':
        messages.error(request, "Only instructors can mark attendance.")
        return redirect('login')

    subject = Subject.objects.get(id=subject_id)

    # Get students in this course
    students = Profile.objects.filter(
        role='student',
        course=subject.course
    )

    if request.method == "POST":
        for student in students:
            status = request.POST.get(f"status_{student.user.id}")

            Attendance.objects.update_or_create(
                student=student.user,
                subject=subject,
                date=timezone.now().date(),
                defaults={
                    "status": status,
                    "marked_by": request.user,
                    "batch": student.batch,
                    "source": "manual",
                }
            )

        messages.success(request, "Attendance marked successfully.")
        return redirect('instructor_subjects')

    return render(request, 'courses/mark_attendance.html', {
        'subject': subject,
        'students': students
    })
    
    
@login_required
def instructor_assignments(request):
    """
    Instructor & Faculty Hub for managing assignments, cohorts, and rubrics.
    """
    user_role = getattr(getattr(request.user, 'profile', None), 'role', '')
    if not (request.user.is_superuser or user_role in ['hod', 'instructor']):
        messages.error(request, "Access restricted to instructors and faculty.")
        return redirect('login')

    if request.user.is_superuser or user_role == 'hod':
        assignments_qs = Assignment.objects.all().select_related('subject__course', 'batch', 'created_by')
        subjects_qs = Subject.objects.all().select_related('course').order_by('course__name', 'name')
    else:
        assignments_qs = Assignment.objects.filter(
            Q(subject__instructor=request.user) | Q(created_by=request.user)
        ).select_related('subject__course', 'batch', 'created_by')
        subjects_qs = Subject.objects.filter(instructor=request.user).select_related('course').order_by('course__name', 'name')

    subject_filter = request.GET.get('subject_id')
    batch_filter = request.GET.get('batch_id')
    if subject_filter:
        assignments_qs = assignments_qs.filter(subject_id=subject_filter)
    if batch_filter:
        assignments_qs = assignments_qs.filter(batch_id=batch_filter)

    assignments_list = []
    total_submissions = 0
    total_graded = 0
    total_pending = 0

    for a in assignments_qs.order_by('week_number', 'due_date'):
        subs = a.submissions.all()
        a.total_subs = subs.count()
        a.graded_subs = subs.filter(status='graded').count()
        a.pending_subs = subs.filter(status__in=['submitted', 'revision_requested']).count()
        
        total_submissions += a.total_subs
        total_graded += a.graded_subs
        total_pending += a.pending_subs
        assignments_list.append(a)

    all_batches = Batch.objects.all().select_related('course').order_by('course__name', 'name')

    context = {
        'assignments': assignments_list,
        'subjects': subjects_qs,
        'batches': all_batches,
        'total_assignments': len(assignments_list),
        'total_submissions': total_submissions,
        'total_graded': total_graded,
        'total_pending': total_pending,
        'selected_subject': subject_filter,
        'selected_batch': batch_filter,
    }
    return render(request, 'courses/instructor_assignments.html', context)


@login_required
def manage_assignments(request, subject_id):
    return redirect(f"/courses/instructor/assignments/?subject_id={subject_id}")


@login_required
def create_assignment(request, subject_id=None):
    """
    Creates an assignment with week number, due date, max score, and default rubric.
    """
    user_role = getattr(getattr(request.user, 'profile', None), 'role', '')
    if not (request.user.is_superuser or user_role in ['hod', 'instructor']):
        messages.error(request, "Permission denied.")
        return redirect('instructor_assignments')

    if request.method == "POST":
        subj_id = request.POST.get('subject_id') or subject_id
        subject = get_object_or_404(Subject, id=subj_id)
        batch_id = request.POST.get('batch_id')
        batch = Batch.objects.filter(id=batch_id).first() if batch_id else None

        title = request.POST.get('title')
        description = request.POST.get('description', '')
        week_number = int(request.POST.get('week_number', 1) or 1)
        due_date = request.POST.get('due_date')
        max_score = int(request.POST.get('max_score', 100) or 100)
        file = request.FILES.get('file')

        Assignment.objects.create(
            subject=subject,
            batch=batch,
            week_number=week_number,
            title=title,
            description=description,
            due_date=due_date,
            max_score=max_score,
            file=file,
            created_by=request.user
        )

        messages.success(request, f"🎉 Assignment 'Week {week_number}: {title}' published successfully!")
        return redirect('instructor_assignments')

    return redirect('instructor_assignments')


@login_required
def assignment_submissions(request, assignment_id):
    """
    Instructor view to review and grade submissions for a specific assignment using rubric.
    """
    user_role = getattr(getattr(request.user, 'profile', None), 'role', '')
    if not (request.user.is_superuser or user_role in ['hod', 'instructor']):
        messages.error(request, "Permission denied.")
        return redirect('login')

    assignment = get_object_or_404(Assignment, id=assignment_id)
    submissions = assignment.submissions.all().select_related('student', 'graded_by').order_by('-submitted_at')

    enrolled_profiles = Profile.objects.filter(role='student', course=assignment.subject.course).select_related('user')
    if assignment.batch:
        enrolled_profiles = enrolled_profiles.filter(batch=assignment.batch)
        
    submitted_student_ids = set(submissions.values_list('student_id', flat=True))
    missing_students = [p for p in enrolled_profiles if p.user_id not in submitted_student_ids]

    context = {
        'assignment': assignment,
        'submissions': submissions,
        'missing_students': missing_students,
        'rubric': assignment.get_rubric(),
    }
    return render(request, 'courses/assignment_submissions.html', context)


@login_required
def grade_submission(request, submission_id):
    """
    Scores student submission based on the 4-pillar marking rubric:
    1. Functionality & Logic (40)
    2. Code Quality & Architecture (25)
    3. UI/UX & Output Presentation (20)
    4. Best Practices & Timeliness (15)
    """
    user_role = getattr(getattr(request.user, 'profile', None), 'role', '')
    if not (request.user.is_superuser or user_role in ['hod', 'instructor']):
        messages.error(request, "Permission denied.")
        return redirect('login')

    submission = get_object_or_404(Submission, id=submission_id)

    if request.method == "POST":
        try:
            func_score = float(request.POST.get('rubric_functionality', 0) or 0)
            code_score = float(request.POST.get('rubric_code_quality', 0) or 0)
            ui_score = float(request.POST.get('rubric_ui_ux', 0) or 0)
            best_score = float(request.POST.get('rubric_best_practices', 0) or 0)
            feedback = request.POST.get('feedback', '').strip()
            status = request.POST.get('status', 'graded')

            total_score = min(100.0, max(0.0, func_score + code_score + ui_score + best_score))

            submission.rubric_scores = {
                'functionality': func_score,
                'code_quality': code_score,
                'ui_ux': ui_score,
                'best_practices': best_score,
            }
            submission.total_score = total_score
            submission.letter_grade = submission.calculate_letter_grade()
            submission.feedback = feedback
            submission.status = status
            submission.graded_by = request.user
            submission.graded_at = timezone.now()
            submission.save()

            messages.success(
                request,
                f"✅ Evaluated {submission.student.get_full_name() or submission.student.username}: "
                f"{total_score}% ({submission.letter_grade})!"
            )
        except Exception as e:
            messages.error(request, f"Error saving evaluation: {e}")

        return redirect('assignment_submissions', assignment_id=submission.assignment.id)

    return redirect('instructor_assignments')


@login_required
@role_required('student')
def student_weekly_gradebook(request):
    """
    Student view: Week-by-week progress timeline, assignment submissions, rubric feedback,
    and cumulative standing calculation.
    """
    user = request.user
    profile = user.profile
    course = profile.course

    if not course:
        messages.info(request, "Please enroll in a course to view assignments.")
        return redirect('choose_course')

    assignments = Assignment.objects.filter(subject__course=course).select_related('subject', 'batch').order_by('week_number', 'due_date')
    if profile.batch:
        assignments = assignments.filter(Q(batch=profile.batch) | Q(batch__isnull=True))

    submissions_map = {
        s.assignment_id: s
        for s in Submission.objects.filter(student=user, assignment__in=assignments).select_related('graded_by')
    }

    # Group assignments by week
    weeks_dict = {}
    total_score_sum = 0
    graded_count = 0
    submitted_count = 0

    for a in assignments:
        sub = submissions_map.get(a.id)
        a.submission = sub
        if sub:
            submitted_count += 1
            if sub.total_score is not None:
                total_score_sum += float(sub.total_score)
                graded_count += 1

        week_key = a.week_number
        if week_key not in weeks_dict:
            weeks_dict[week_key] = []
        weeks_dict[week_key].append(a)

    total_assignments = assignments.count()
    completion_pct = round((submitted_count / total_assignments * 100), 1) if total_assignments > 0 else 0
    cumulative_avg = round((total_score_sum / graded_count), 1) if graded_count > 0 else None

    # Determine Academic Standing
    if cumulative_avg is not None:
        if cumulative_avg >= 90:
            academic_standing = "Distinction / Excellent"
            standing_badge = "badge-warning"
        elif cumulative_avg >= 75:
            academic_standing = "Merit / Very Good"
            standing_badge = "badge-primary"
        elif cumulative_avg >= 60:
            academic_standing = "Credit / Good"
            standing_badge = "badge-info"
        elif cumulative_avg >= 50:
            academic_standing = "Pass"
            standing_badge = "badge-secondary"
        else:
            academic_standing = "Needs Revision"
            standing_badge = "badge-danger"
    else:
        academic_standing = "In Progress"
        standing_badge = "badge-light"

    context = {
        'course': course,
        'profile': profile,
        'weeks_dict': weeks_dict,
        'total_assignments': total_assignments,
        'submitted_count': submitted_count,
        'graded_count': graded_count,
        'completion_pct': completion_pct,
        'cumulative_avg': cumulative_avg,
        'academic_standing': academic_standing,
        'standing_badge': standing_badge,
    }
    return render(request, 'courses/student_weekly_gradebook.html', context)


@login_required
@role_required('student')
def submit_assignment(request, assignment_id):
    """
    Student submits files, GitHub repository links, or live demo URLs for an assignment.
    """
    assignment = get_object_or_404(Assignment, id=assignment_id)

    if request.user.profile.course != assignment.subject.course:
        messages.error(request, "You are not enrolled in this course track.")
        return redirect('student_weekly_gradebook')

    existing = Submission.objects.filter(assignment=assignment, student=request.user).first()

    if request.method == "POST":
        file = request.FILES.get('file')
        repo_url = request.POST.get('repo_url', '').strip()
        live_demo_url = request.POST.get('live_demo_url', '').strip()
        notes = request.POST.get('notes', '').strip()

        if not (file or repo_url or live_demo_url or (existing and existing.file)):
            messages.warning(request, "Please attach a project file or enter a GitHub repository / live demo link.")
            return redirect('student_weekly_gradebook')

        if existing:
            if file:
                existing.file = file
            existing.repo_url = repo_url
            existing.live_demo_url = live_demo_url
            existing.notes = notes
            existing.status = 'submitted'
            existing.submitted_at = timezone.now()
            existing.save()
            messages.success(request, f"🎉 Submission for '{assignment.title}' updated successfully!")
        else:
            Submission.objects.create(
                assignment=assignment,
                student=request.user,
                file=file,
                repo_url=repo_url,
                live_demo_url=live_demo_url,
                notes=notes,
                status='submitted'
            )
            messages.success(request, f"🚀 Assignment '{assignment.title}' submitted! Your tutor will evaluate your work.")

        return redirect('student_weekly_gradebook')

    return render(request, 'courses/submit_assignment.html', {
        'assignment': assignment,
        'existing': existing,
        'rubric': assignment.get_rubric(),
    })


@login_required
def student_assignments(request):
    return redirect('student_weekly_gradebook')


