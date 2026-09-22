from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Course, Subject, Assignment, Submission
from .forms import CourseForm, SubjectForm
from apps.accounts.decorators import role_required, payment_required
from apps.accounts.models import Profile, Attendance
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
def manage_assignments(request, subject_id):
    subject = Subject.objects.get(id=subject_id)
    assignments = subject.assignments.all()

    return render(request, 'courses/manage_assignments.html', {
        'subject': subject,
        'assignments': assignments
    })


@login_required
def create_assignment(request, subject_id):
    subject = Subject.objects.get(id=subject_id)

    if request.method == "POST":
        title = request.POST.get('title')
        due_date = request.POST.get('due_date')
        file = request.FILES.get('file')

        Assignment.objects.create(
            subject=subject,
            title=title,
            due_date=due_date,
            file=file,
            created_by=request.user
        )

        messages.success(request, "Assignment created.")
        return redirect('manage_assignments', subject_id=subject.id)

    return render(request, 'courses/create_assignment.html', {'subject': subject})    


@login_required
def submit_assignment(request, assignment_id):
    assignment = Assignment.objects.get(id=assignment_id)

    # Only students can submit
    if request.user.profile.role != 'student':
        messages.error(request, "Only students can submit assignments.")
        return redirect('login')

    # Ensure student belongs to the course
    if request.user.profile.course != assignment.subject.course:
        messages.error(request, "You are not assigned to this course.")
        return redirect('student_dashboard')

    # Check if already submitted
    existing = Submission.objects.filter(
        assignment=assignment,
        student=request.user
    ).first()

    if request.method == "POST":
        file = request.FILES.get('file')

        if existing:
            # Update submission
            existing.file = file
            existing.save()
            messages.success(request, "Submission updated.")
        else:
            Submission.objects.create(
                assignment=assignment,
                student=request.user,
                file=file
            )
            messages.success(request, "Assignment submitted.")

        return redirect('student_dashboard')

    return render(request, 'courses/submit_assignment.html', {
        'assignment': assignment,
        'existing': existing
    })
    

@login_required
def student_assignments(request):
    if request.user.profile.role != 'student':
        messages.error(request, "Access denied.")
        return redirect('login')

    course = request.user.profile.course

    assignments = Assignment.objects.filter(
        subject__course=course
    ).order_by('-created_at')

    return render(request, 'courses/student_assignments.html', {
        'assignments': assignments
    })

