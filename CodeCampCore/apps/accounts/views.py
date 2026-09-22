from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.conf import settings

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

import json
from datetime import timedelta
from decimal import Decimal

from .models import Attendance, Profile
from .decorators import role_required
from apps.accounts.utils import get_dashboard_url_name, get_next_onboarding_url
from apps.courses.models import Subject
from apps.payments.models import Payment
from apps.notifications.models import NotificationLog
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count
from django.db.models.functions import TruncDay
from django.shortcuts import render, redirect

from apps.tasks.models import Task
from django.db.models import Count, Q






# ---------------------------------------------------------
# HOME
# ---------------------------------------------------------

def home(request):
    return render(request, 'accounts/login.html')


# ---------------------------------------------------------
# REGISTER
# ---------------------------------------------------------

def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # Validation
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return redirect('register')

        # Create User
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # 🔒 Ensure profile exists and is correct
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={
                'is_verified': False,
                'onboarding_stage': 'email_pending'
            }
        )

        # Build verification URL safely
        verification_url = request.build_absolute_uri(
            f"/account/verify/{profile.verification_token}/"
        )

        # Email template
        html_content = render_to_string(
            "accounts/verify_email.html",
            {
                "user": user,
                "verification_url": verification_url,
                "year": timezone.now().year,
            }
        )
        text_content = strip_tags(html_content)

        # Send Email
        msg = EmailMultiAlternatives(
            subject="Verify your CodeCamp account",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()

        messages.success(
            request,
            "Account created successfully. Please check your email to verify your account."
        )

        # ✅ CORRECT REDIRECT
        return redirect('verify_email_sent')

    return render(request, 'accounts/register.html')


# ---------------------------------------------------------
# LOGIN WITH ROLE-BASED ACCESS + ONBOARDING + ADMIN CONTROL
# ---------------------------------------------------------

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.utils.safestring import mark_safe

from .models import Profile
from .utils import get_next_onboarding_url, get_dashboard_url_name


def login_view(request):
    if request.method == 'POST':
        print("LOGIN ATTEMPT")

        username = request.POST.get('username', '').strip()
        password = request.POST.get('password')

        print("USERNAME INPUT:", username)
        print("PASSWORD INPUT:", password)

        user = authenticate(request, username=username, password=password)

        print("AUTH RESULT:", user)

        # ❌ Invalid login
        if not user:
            print("AUTH FAILED")
            messages.error(request, "Invalid username or password.")
            return redirect('login')

        # 🔥 SUPERUSER BYPASS (CEO / ADMIN CONTROL)
        if user.is_superuser:
            login(request, user)
            print("SUPERUSER LOGIN → ADMIN DASHBOARD")
            return redirect('admin_dashboard')

        # ✅ Ensure profile exists
        profile, _ = Profile.objects.get_or_create(user=user)

        print("PROFILE:", profile)
        print("ROLE:", profile.role)
        print("VERIFIED:", profile.is_verified)
        print("APPROVED:", getattr(profile, "is_approved", None))
        print("STAGE:", profile.onboarding_stage)

        # 🔒 EMAIL VERIFICATION (STUDENTS ONLY)
        if profile.role == 'student' and not profile.is_verified:
            print("NOT VERIFIED")
            messages.warning(
                request,
                mark_safe(
                    "Email not verified. "
                    "<a href='/account/resend-verification/'>Resend verification email</a>"
                )
            )
            return redirect('login')

        # 🔒 STAFF / INSTRUCTOR / HOD APPROVAL CHECK
        if profile.role in ['staff', 'instructor', 'hod']:
            if not getattr(profile, "is_approved", False):
                print("NOT APPROVED")
                messages.warning(
                    request,
                    "Your account is awaiting admin approval."
                )
                return redirect('login')

        # ✅ LOGIN USER
        login(request, user)
        print("LOGIN SUCCESS")

        # 🎯 ROLE-BASED ROUTING (NON-STUDENTS)
        if profile.role == 'instructor':
            print("REDIRECT → INSTRUCTOR DASHBOARD")
            return redirect('instructor_dashboard')

        elif profile.role == 'hod':
            print("REDIRECT → HOD DASHBOARD")
            return redirect('hod_dashboard')

        elif profile.role == 'staff':
            print("REDIRECT → STAFF DASHBOARD")
            return redirect('staff_dashboard')  # create later

        # 👇 STUDENT FLOW ONLY
        if profile.onboarding_stage != 'finished':
            next_stage = get_next_onboarding_url(profile)
            print("NEXT STAGE:", next_stage)

            if next_stage:
                return redirect(next_stage)

        # ✅ FINAL DESTINATION
        dashboard = get_dashboard_url_name(profile)
        print("REDIRECT ->", dashboard)

        return redirect(dashboard)

    return render(request, 'accounts/login.html')


# ---------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------

def logout_user(request):
    logout(request)
    return redirect('login')


# ---------------------------------------------------------
# EMAIL VERIFICATION
# ---------------------------------------------------------

def verify_email(request, token):
    try:
        profile = Profile.objects.get(verification_token=token)

        # Prevent double verification
        if profile.is_verified:
            messages.info(request, "Your email is already verified. Please log in.")
            return redirect('login')

        # Mark email as verified
        profile.is_verified = True

        # ✅ Correct onboarding transition
        profile.onboarding_stage = 'welcome'

        profile.save()

        messages.success(
            request,
            "Your email has been verified successfully. Please log in to continue."
        )
        return redirect('login')

    except Profile.DoesNotExist:
        messages.error(
            request,
            "Invalid or expired verification link. Please request a new one."
        )
        return redirect('login')



def verify_email_sent(request):
    return render(request, 'accounts/verify_email_sent.html')


# ---------------------------------------------------------
# RESEND VERIFICATION EMAIL
# ---------------------------------------------------------

def resend_verification_email(request):
    if request.method == 'POST':
        email = request.POST.get('email')

        user = User.objects.filter(email=email).first()
        if not user:
            messages.error(request, "No account found with this email.")
            return redirect('resend_verification')

        if user.profile.is_verified:
            messages.info(request, "This email is already verified.")
            return redirect('login')

        verification_url = request.build_absolute_uri(
            f"/account/verify/{user.profile.verification_token}/"
        )

        html_content = render_to_string("accounts/verify_email.html", {
            "user": user,
            "verification_url": verification_url,
            "year": timezone.now().year,
        })

        text_content = strip_tags(html_content)

        email_obj = EmailMultiAlternatives(
            subject="Resend Verification – CodeCamp",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        email_obj.attach_alternative(html_content, "text/html")
        email_obj.send()

        messages.success(request, "Verification email sent again! Please check your inbox.")
        return redirect('login')

    return render(request, "accounts/resend_verification.html")


# ---------------------------------------------------------
# STUDENT DASHBOARD
# ---------------------------------------------------------

@login_required
@role_required('student')
def student_dashboard(request):
    user = request.user
    profile = user.profile

    # Payment summary
    payment = Payment.objects.filter(student=user).select_related('course').first()
    summary = None
    if payment:
        completion = 0
        if payment.amount_due > 0:
            completion = (payment.amount_paid / payment.amount_due) * 100

        summary = {
            'course_name': payment.course.name,
            'amount_due': payment.amount_due,
            'amount_paid': payment.amount_paid,
            'balance': payment.remaining_balance(),
            'status': payment.status,
            'monthly_payment': payment.monthly_payment,
            'completion': round(completion, 1),
        }

    # Attendance analytics
    subjects = Subject.objects.filter(course=profile.course)
    attendance_qs = Attendance.objects.filter(student=user)

    subject_names = []
    data_present = []
    data_absent = []
    attendance_present = attendance_qs.filter(status='Present').count()
    attendance_absent = attendance_qs.filter(status='Absent').count()

    for subject in subjects:
        subject_names.append(subject.name)
        data_present.append(attendance_qs.filter(subject=subject, status='Present').count())
        data_absent.append(attendance_qs.filter(subject=subject, status='Absent').count())

    context = {
        "summary": summary,
        "subject_name": json.dumps(subject_names),
        "data_present": json.dumps(data_present),
        "data_absent": json.dumps(data_absent),
        "total_attendance": attendance_qs.count(),
        "attendance_present": attendance_present,
        "attendance_absent": attendance_absent,
        "total_subjects": subjects.count(),
    }

    return render(request, "accounts/student_dashboard.html", context)

# ---------------------------------------------------------
# STAFF onboarding and management
# ---------------------------------------------------------

@login_required
def create_staff(request):
    if not (request.user.is_superuser or request.user.profile.role == 'hod'):
        messages.error(request, "Access denied.")
        return redirect('admin_dashboard')

    if request.method == "POST":
        username = request.POST.get('username')
        email = request.POST.get('email')
        role = request.POST.get('role')

        user = User.objects.create_user(username=username, email=email, password="default123")

        Profile.objects.create(
            user=user,
            role=role,
            is_verified=True,
            is_approved=False
        )

        messages.success(request, "Staff created. Awaiting admin approval.")
        return redirect('admin_dashboard')

    return render(request, 'accounts/create_staff.html')


@login_required
def approve_staff(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, "Only admin can approve staff.")
        return redirect('admin_dashboard')

    profile = Profile.objects.get(user__id=user_id)
    profile.is_approved = True
    profile.save()

    messages.success(request, "Staff approved.")
    return redirect('admin_dashboard')


# ---------------------------------------------------------
# ROLE DASHBOARDS
# ---------------------------------------------------------

@login_required
@role_required('instructor')
def instructor_dashboard(request):
    return render(request, 'staff/instructor_dashboard.html')


@login_required
@role_required('hod')
def hod_dashboard(request):
    today = timezone.now().date()
    qs = NotificationLog.objects.filter(created_at__date=today)

    summary = {
        "sent": qs.filter(status="sent").count(),
        "failed": qs.filter(status="failed").count(),
        "queued": qs.filter(status="queued").count(),
        "total": qs.count(),
    }

    return render(request, "staff/hod_dashboard.html", {"summary": summary})


# ---------------------------------------------------------
# PROFILE
# ---------------------------------------------------------

@login_required
def student_profile(request):
    return render(request, 'accounts/student_profile.html', {'student': request.user})


@login_required
def edit_profile(request):
    profile = request.user.profile
    if request.method == 'POST':
        profile.phone = request.POST.get('phone')
        profile.save()
        messages.success(request, "Profile updated.")
        return redirect('student_profile')

    return render(request, 'accounts/edit_profile.html', {'profile': profile})


# ---------------------------------------------------------
# ATTENDANCE
# ---------------------------------------------------------

@login_required
def student_view_attendance(request):
    records = Attendance.objects.filter(student=request.user).order_by('-date')

    context = {
        'attendance_records': records,
        'total_attendance': records.count(),
        'attendance_present': records.filter(status='Present').count(),
        'attendance_absent': records.filter(status='Absent').count(),
    }

    return render(request, 'accounts/student_view_attendance.html', context)


# ---------------------------------------------------------
# STUDENT MESSAGES
# ---------------------------------------------------------

@login_required
def student_messages(request):
    return render(request, 'accounts/student_messages.html')




# accounts/views.py



@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('login')

    today = timezone.now()
    last_7_days = today - timedelta(days=7)

    # ========================
    # EXECUTIVE KPIs
    # ========================
    total_users = User.objects.count()
    active_users = User.objects.filter(last_login__gte=last_7_days).count()

    total_students = Profile.objects.filter(role='student').count()
    total_instructors = Profile.objects.filter(role='instructor').count()
    total_staff = Profile.objects.filter(role='staff').count()

    total_tasks = Task.objects.count()
    completed_tasks = Task.objects.filter(status='done').count()
    pending_tasks = Task.objects.exclude(status='done').count()
    overdue_tasks = Task.objects.filter(
        due_date__lt=today,
        status__in=['todo', 'in_progress']
    ).count()

    attendance_today = Attendance.objects.filter(date=today.date()).count()

    # ========================
    # GROWTH (LAST 7 DAYS)
    # ========================
    user_growth = (
        User.objects
        .filter(date_joined__gte=last_7_days)
        .annotate(date=TruncDay('date_joined'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )

    user_labels = [str(i['date']) for i in user_growth]
    user_data = [i['count'] for i in user_growth]

    # ========================
    # TASK PERFORMANCE
    # ========================
    task_status = {
        "todo": Task.objects.filter(status='todo').count(),
        "in_progress": Task.objects.filter(status='in_progress').count(),
        "review": Task.objects.filter(status='review').count(),
        "done": completed_tasks,
    }

    # ========================
    # STAFF PERFORMANCE
    # ========================
    staff_performance = (
        Task.objects.values('assigned_to__username')
        .annotate(
            completed=Count('id', filter=Q(status='done')),
            pending=Count('id', filter=~Q(status='done')),
        )
        .order_by('-completed')[:5]
    )

    staff_labels = [i['assigned_to__username'] for i in staff_performance]
    staff_completed = [i['completed'] for i in staff_performance]

    # ========================
    # ATTENDANCE TREND
    # ========================
    attendance_trend = (
        Attendance.objects
        .filter(date__gte=last_7_days)
        .annotate(day=TruncDay('date'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    attendance_labels = [str(i['day']) for i in attendance_trend]
    attendance_data = [i['count'] for i in attendance_trend]

    # ========================
    # ALERTS SYSTEM
    # ========================
    alerts = []

    if overdue_tasks > 0:
        alerts.append(f"{overdue_tasks} overdue tasks need attention")

    if attendance_today == 0:
        alerts.append("No attendance recorded today")

    # ========================
    # RECENT ACTIVITY
    # ========================
    recent_tasks = Task.objects.order_by('-created_at')[:5]
    recent_users = User.objects.order_by('-date_joined')[:5]

    context = {
        # KPIs
        "total_users": total_users,
        "active_users": active_users,
        "total_students": total_students,
        "total_instructors": total_instructors,
        "total_staff": total_staff,

        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
        "overdue_tasks": overdue_tasks,

        "attendance_today": attendance_today,

        # Charts
        "user_labels": user_labels,
        "user_data": user_data,

        "task_status": task_status,

        "staff_labels": staff_labels,
        "staff_completed": staff_completed,

        "attendance_labels": attendance_labels,
        "attendance_data": attendance_data,

        # Alerts
        "alerts": alerts,

        # Activity
        "recent_tasks": recent_tasks,
        "recent_users": recent_users,
    }

    return render(request, "admin/dashboard.html", context)