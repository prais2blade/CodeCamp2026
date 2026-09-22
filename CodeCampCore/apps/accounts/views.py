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
from apps.courses.models import Subject, Course
from apps.scheduling.models import Batch, ClassSession
from apps.payments.models import Payment, Receipt
from apps.tenants.models import Tenant
from apps.tenants.context import get_current_tenant
from apps.notifications.models import NotificationLog
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDay
from django.shortcuts import render, redirect, get_object_or_404

from apps.tasks.models import Task






# ---------------------------------------------------------
# HOME
# ---------------------------------------------------------

def home(request):
    return render(request, 'accounts/login.html')


# ---------------------------------------------------------
# REGISTER
# ---------------------------------------------------------

def register_view(request):
    selected_course_slug = request.GET.get('course', '').strip()
    courses = Course.objects.filter(is_published=True).order_by('name')

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        course_id = request.POST.get('course_id')
        delivery_mode = request.POST.get('delivery_mode', 'onsite')

        # Fallback username if missing
        if not username and email:
            username = email.split('@')[0].lower()

        # Validation
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            redirect_url = f"/account/register/?course={selected_course_slug}" if selected_course_slug else "/account/register/"
            return redirect(redirect_url)

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            redirect_url = f"/account/register/?course={selected_course_slug}" if selected_course_slug else "/account/register/"
            return redirect(redirect_url)

        if User.objects.filter(email=email).exists():
            messages.error(request, "An account with this email already exists. Please log in.")
            return redirect('login')

        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0] if name_parts else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        # Create User
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        course = Course.objects.filter(id=course_id).first() if course_id else None
        batch = None
        if course:
            batch = Batch.objects.filter(course=course, mode=delivery_mode, is_published=True).first()
            if not batch:
                batch = Batch.objects.filter(course=course, is_published=True).first()

        # 🔒 Ensure profile exists and is correct
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={
                'role': 'student',
                'phone': phone,
                'course': course,
                'batch': batch,
                'is_verified': False,
                'onboarding_stage': 'email_pending',
                'total_fee': course.fee if course else Decimal('35000.00'),
            }
        )
        if not created:
            profile.phone = phone
            profile.course = course
            profile.batch = batch
            profile.save()

        # Initialize Payment Record
        if course:
            Payment.objects.create(
                student=user,
                course=course,
                batch=batch,
                amount_due=course.fee,
                amount_paid=Decimal('0.00'),
                monthly_payment=Decimal('35000.00'),
                status='pending'
            )

        # Build verification URL and send email safely
        try:
            verification_url = request.build_absolute_uri(
                f"/account/verify/{profile.verification_token}/"
            )
            html_content = render_to_string(
                "accounts/verify_email.html",
                {
                    "user": user,
                    "verification_url": verification_url,
                    "year": timezone.now().year,
                }
            )
            text_content = strip_tags(html_content)
            msg = EmailMultiAlternatives(
                subject="Verify your CodeCamp account",
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email],
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=True)
        except Exception:
            pass

        messages.success(
            request,
            "Application created successfully! Please check your email to verify your account."
        )
        return redirect('verify_email_sent')

    return render(request, 'accounts/register.html', {
        'courses': courses,
        'selected_course_slug': selected_course_slug,
    })


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

        login_input = request.POST.get('username', '').strip()
        password = request.POST.get('password')

        # Flexible student & staff lookup: username, email, or Student ID
        matched_user = authenticate(request, username=login_input, password=password)

        if not matched_user and '@' in login_input:
            user_by_email = User.objects.filter(email__iexact=login_input).first()
            if user_by_email:
                matched_user = authenticate(request, username=user_by_email.username, password=password)

        if not matched_user:
            profile_by_id = Profile.objects.filter(external_attendance_id__iexact=login_input).select_related('user').first()
            if profile_by_id:
                matched_user = authenticate(request, username=profile_by_id.user.username, password=password)

        user = matched_user

        # ❌ Invalid login
        if not user:
            messages.error(request, "Invalid username, student ID, or password.")
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
        "is_temporary_password": user.check_password('CodeCamp@2026'),
    }

    return render(request, "accounts/student_dashboard.html", context)


@login_required
def change_password_view(request):
    from django.contrib.auth import update_session_auth_hash
    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if not new_password or len(new_password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
            return redirect(request.META.get('HTTP_REFERER', 'student_dashboard'))

        if new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
            return redirect(request.META.get('HTTP_REFERER', 'student_dashboard'))

        request.user.set_password(new_password)
        request.user.save()
        update_session_auth_hash(request, request.user)
        messages.success(request, "🎉 Your password has been successfully updated! You can now log in with your new password.")

        if hasattr(request.user, 'profile') and request.user.profile.role == 'student':
            return redirect('student_dashboard')
        return redirect('admin_dashboard')

    is_temp = request.user.check_password('CodeCamp@2026')
    return render(request, 'accounts/change_password.html', {
        'is_temp_password': is_temp,
    })

# ---------------------------------------------------------
# ---------------------------------------------------------
# STAFF & TEACHER ONBOARDING AND MANAGEMENT
# ---------------------------------------------------------

@login_required
def create_staff(request):
    """Onboards a teacher, instructor, or staff member directly from the dashboard."""
    if not (request.user.is_superuser or request.user.profile.role == 'hod'):
        messages.error(request, "Access denied. Administrator privileges required.")
        return redirect('admin_dashboard')

    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        role = request.POST.get('role', 'instructor').strip()
        course_id = request.POST.get('course_id')
        password = request.POST.get('password', '').strip() or "CodeCamp2026!"
        auto_approve = request.POST.get('is_approved') == 'on' or request.user.is_superuser

        if not email:
            messages.error(request, "Email address is required.")
            return redirect('/account/admin/dashboard/#staff')

        if not username:
            username = email.split('@')[0].lower()

        if User.objects.filter(username=username).exists():
            messages.error(request, f"User with username '{username}' already exists.")
            return redirect('/account/admin/dashboard/#staff')

        if User.objects.filter(email=email).exists():
            messages.error(request, f"User with email '{email}' already exists.")
            return redirect('/account/admin/dashboard/#staff')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        course = Course.objects.filter(id=course_id).first() if course_id else None

        Profile.objects.create(
            user=user,
            role=role,
            phone=phone,
            course=course,
            is_verified=True,
            is_approved=auto_approve,
            onboarding_stage='finished',
        )

        role_display = "Teacher / Instructor" if role == 'instructor' else role.upper()
        name_display = user.get_full_name() or user.username
        messages.success(request, f"🎉 {role_display} '{name_display}' onboarded successfully and active in the system!")
        return redirect('/account/admin/dashboard/#staff')

    return render(request, 'accounts/create_staff.html')


@login_required
def approve_staff(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, "Only admin can approve staff.")
        return redirect('/account/admin/dashboard/#staff')

    profile = get_object_or_404(Profile, user__id=user_id)
    profile.is_approved = True
    profile.save(update_fields=['is_approved'])

    messages.success(request, f"Staff member '{profile.user.get_full_name() or profile.user.username}' has been approved.")
    return redirect('/account/admin/dashboard/#staff')


@login_required
def admin_staff_toggle_status(request, user_id):
    """Activates or deactivates an instructor/staff account."""
    if not request.user.is_superuser:
        messages.error(request, "Access restricted to administrators.")
        return redirect('/account/admin/dashboard/#staff')

    if request.method == "POST":
        user = get_object_or_404(User, id=user_id)
        if user == request.user:
            messages.error(request, "You cannot deactivate your own account.")
            return redirect('/account/admin/dashboard/#staff')

        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])

        state = "activated" if user.is_active else "deactivated"
        messages.success(request, f"Teacher/Staff account '{user.get_full_name() or user.username}' has been {state}.")
        return redirect('/account/admin/dashboard/#staff')

    return redirect('/account/admin/dashboard/#staff')


@login_required
def admin_staff_delete(request, user_id):
    """Removes an instructor/staff account."""
    if not request.user.is_superuser:
        messages.error(request, "Access restricted to administrators.")
        return redirect('/account/admin/dashboard/#staff')

    if request.method == "POST":
        user = get_object_or_404(User, id=user_id)
        if user == request.user:
            messages.error(request, "You cannot delete your own account.")
            return redirect('/account/admin/dashboard/#staff')

        name = user.get_full_name() or user.username
        user.delete()
        messages.success(request, f"Teacher/Staff record for '{name}' was removed.")
        return redirect('/account/admin/dashboard/#staff')

    return redirect('/account/admin/dashboard/#staff')


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
        messages.error(request, "Access restricted to administrators.")
        return redirect('login')

    today = timezone.now()
    today_date = today.date()
    last_7_days = today - timedelta(days=7)

    # ========================
    # 1. EXECUTIVE KPIs
    # ========================
    total_users = User.objects.count()
    active_users = User.objects.filter(last_login__gte=last_7_days).count()
    total_students = Profile.objects.filter(role='student').count()
    total_instructors = Profile.objects.filter(role__in=['instructor', 'hod']).count()
    total_staff = Profile.objects.filter(role__in=['staff', 'support']).count()
    total_courses = Course.objects.count()
    total_batches = Batch.objects.count()

    # Financials
    fin_agg = Payment.objects.aggregate(
        invoiced=Sum('amount_due'),
        collected=Sum('amount_paid')
    )
    total_invoiced = fin_agg['invoiced'] or Decimal('0.00')
    total_collected = fin_agg['collected'] or Decimal('0.00')
    pending_revenue = max(Decimal('0.00'), total_invoiced - total_collected)
    collection_rate = round((float(total_collected) / float(total_invoiced) * 100), 1) if total_invoiced > 0 else 0

    # Tasks & Attendance
    total_tasks = Task.objects.count()
    completed_tasks = Task.objects.filter(status='done').count()
    pending_tasks = Task.objects.exclude(status='done').count()
    overdue_tasks = Task.objects.filter(
        due_date__lt=today,
        status__in=['todo', 'in_progress']
    ).count()
    attendance_today = Attendance.objects.filter(date=today_date).count()

    # ========================
    # 2. DATASETS FOR DIRECT MANAGEMENT
    # ========================
    # Students
    students = (
        Profile.objects.filter(role='student')
        .select_related('user', 'course', 'batch', 'tenant')
        .order_by('-user__date_joined')
    )
    student_user_ids = [s.user_id for s in students]
    payments_map = {
        p.student_id: p
        for p in Payment.objects.filter(student_id__in=student_user_ids).select_related('course', 'batch')
    }
    for s in students:
        s.payment_record = payments_map.get(s.user_id)
        if s.payment_record and s.payment_record.amount_due > 0:
            s.payment_pct = min(100, round((float(s.payment_record.amount_paid) / float(s.payment_record.amount_due)) * 100, 1))
        else:
            s.payment_pct = 0

    # Courses
    courses = Course.objects.all().prefetch_related('subjects', 'batches').order_by('name')
    course_students_counts = {
        item['course_id']: item['count']
        for item in Profile.objects.filter(role='student', course__isnull=False).values('course_id').annotate(count=Count('id'))
    }
    course_cohort_counts = {
        item['course_id']: item['count']
        for item in Batch.objects.values('course_id').annotate(count=Count('id'))
    }
    for c in courses:
        c.student_count = course_students_counts.get(c.id, 0)
        c.cohort_count = course_cohort_counts.get(c.id, 0)

    # Batches / Cohorts
    batches = Batch.objects.all().select_related('course').order_by('course__name', 'mode', 'session_period')
    batch_enrollment_counts = {
        item['batch_id']: item['count']
        for item in Profile.objects.filter(batch__isnull=False).values('batch_id').annotate(count=Count('id'))
    }
    for b in batches:
        b.enrolled_count = batch_enrollment_counts.get(b.id, 0)
        b.occupancy_pct = min(100, round((b.enrolled_count / b.max_students) * 100, 1)) if b.max_students > 0 else 0

    # Payments & Receipts
    payments = Payment.objects.all().select_related('student', 'course', 'batch').order_by('-payment_date')[:100]
    recent_receipts = Receipt.objects.all().select_related('payment__student', 'payment__course').order_by('-issued_date')[:25]

    # Live Attendance Log
    attendance_records = Attendance.objects.all().select_related('student', 'subject', 'batch').order_by('-date', '-check_in_time')[:60]

    # Staff / Instructors
    staff_members = Profile.objects.filter(role__in=['instructor', 'hod', 'staff', 'support']).select_related('user', 'course').order_by('-user__date_joined')

    # Dropdown lookups for modals
    all_courses = Course.objects.all().order_by('name')
    all_batches = Batch.objects.all().select_related('course').order_by('course__name', 'name')
    all_subjects = Subject.objects.all().select_related('course').order_by('course__name', 'name')

    # ========================
    # 3. CHARTS DATA
    # ========================
    user_growth = (
        User.objects.filter(date_joined__gte=last_7_days)
        .annotate(date=TruncDay('date_joined'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    user_labels = [str(i['date']) for i in user_growth]
    user_data = [i['count'] for i in user_growth]

    attendance_trend = (
        Attendance.objects.filter(date__gte=last_7_days.date())
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    attendance_labels = [str(i['date']) for i in attendance_trend]
    attendance_data = [i['count'] for i in attendance_trend]

    task_status = {
        "todo": Task.objects.filter(status='todo').count(),
        "in_progress": Task.objects.filter(status='in_progress').count(),
        "review": Task.objects.filter(status='review').count(),
        "done": completed_tasks,
    }

    # ========================
    # 4. ALERTS
    # ========================
    alerts = []
    if overdue_tasks > 0:
        alerts.append(f"{overdue_tasks} overdue tasks need attention")
    if pending_revenue > 0:
        alerts.append(f"₦{pending_revenue:,.2f} in pending tuition balances across cohorts")
    if attendance_today == 0:
        alerts.append("No student attendance logged yet today")

    context = {
        # KPIs
        "total_users": total_users,
        "active_users": active_users,
        "total_students": total_students,
        "total_instructors": total_instructors,
        "total_staff": total_staff,
        "total_courses": total_courses,
        "total_batches": total_batches,
        "total_invoiced": total_invoiced,
        "total_collected": total_collected,
        "pending_revenue": pending_revenue,
        "collection_rate": collection_rate,
        "attendance_today": attendance_today,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
        "overdue_tasks": overdue_tasks,

        # Datasets
        "students": students,
        "courses": courses,
        "batches": batches,
        "payments": payments,
        "recent_receipts": recent_receipts,
        "attendance_records": attendance_records,
        "staff_members": staff_members,

        # Modals Lookups
        "all_courses": all_courses,
        "all_batches": all_batches,
        "all_subjects": all_subjects,

        # Charts
        "user_labels": user_labels,
        "user_data": user_data,
        "attendance_labels": attendance_labels,
        "attendance_data": attendance_data,
        "task_status": task_status,
        "alerts": alerts,
    }

    return render(request, "admin/dashboard.html", context)


# ---------------------------------------------------------
# ADMIN IN-DASHBOARD MANAGEMENT ACTIONS
# ---------------------------------------------------------

@login_required
def admin_student_create(request):
    """Enrolls a student directly from the modern Admin Dashboard."""
    if not request.user.is_superuser:
        messages.error(request, "Access restricted to administrators.")
        return redirect('admin_dashboard')

    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        course_id = request.POST.get('course_id')
        batch_id = request.POST.get('batch_id')
        password = request.POST.get('password', '').strip() or "CodeCamp2026!"

        if not username or not email:
            messages.error(request, "Username and Email are required.")
            return redirect('/account/admin/dashboard/#students')

        if User.objects.filter(username=username).exists():
            messages.error(request, f"User '{username}' already exists.")
            return redirect('/account/admin/dashboard/#students')

        if User.objects.filter(email=email).exists():
            messages.error(request, f"User with email '{email}' already exists.")
            return redirect('/account/admin/dashboard/#students')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        course = Course.objects.filter(id=course_id).first() if course_id else None
        batch = Batch.objects.filter(id=batch_id).first() if batch_id else None

        profile, _ = Profile.objects.get_or_create(
            user=user,
            defaults={
                'role': 'student',
                'phone': phone,
                'course': course,
                'batch': batch,
                'is_verified': True,
                'is_approved': True,
                'onboarding_stage': 'finished',
            }
        )
        if not _:
            profile.phone = phone
            profile.course = course
            profile.batch = batch
            profile.is_verified = True
            profile.is_approved = True
            profile.onboarding_stage = 'finished'
            profile.save()

        # Initialize Payment Record
        if course:
            payment = Payment.objects.create(
                student=user,
                course=course,
                batch=batch,
                amount_due=course.fee,
                amount_paid=Decimal('0.00'),
                monthly_payment=Decimal('35000.00') if course.fee >= 35000 else course.fee,
                status='pending'
            )
            profile.total_fee = course.fee
            profile.save(update_fields=['total_fee'])

        if batch:
            batch.check_capacity()

        messages.success(request, f"Student '{user.get_full_name() or user.username}' successfully enrolled!")
        return redirect('/account/admin/dashboard/#students')

    return redirect('admin_dashboard')


@login_required
def admin_student_update_batch(request, profile_id):
    """Assigns or updates student's cohort/batch directly."""
    if not request.user.is_superuser:
        messages.error(request, "Access restricted to administrators.")
        return redirect('admin_dashboard')

    if request.method == "POST":
        profile = get_object_or_404(Profile, id=profile_id)
        batch_id = request.POST.get('batch_id')
        old_batch = profile.batch

        new_batch = Batch.objects.filter(id=batch_id).first() if batch_id else None
        profile.batch = new_batch
        profile.save(update_fields=['batch'])

        # Keep payment record in sync
        Payment.objects.filter(student=profile.user).update(batch=new_batch)

        if old_batch:
            old_batch.check_capacity()
        if new_batch:
            new_batch.check_capacity()

        messages.success(request, f"Cohort updated for {profile.user.username}: {new_batch.name if new_batch else 'None'}.")
        return redirect('/account/admin/dashboard/#students')

    return redirect('admin_dashboard')


@login_required
def admin_student_toggle_status(request, profile_id):
    """Toggles active/inactive status for a student account."""
    if not request.user.is_superuser:
        messages.error(request, "Access restricted to administrators.")
        return redirect('admin_dashboard')

    if request.method == "POST":
        profile = get_object_or_404(Profile, id=profile_id)
        profile.user.is_active = not profile.user.is_active
        profile.user.save(update_fields=['is_active'])

        status_label = "activated" if profile.user.is_active else "deactivated"
        messages.success(request, f"Student {profile.user.username} account has been {status_label}.")
        return redirect('/account/admin/dashboard/#students')

    return redirect('admin_dashboard')


@login_required
def admin_course_create(request):
    """Creates a new Innovation Hub course directly from the dashboard."""
    if not request.user.is_superuser:
        messages.error(request, "Access restricted to administrators.")
        return redirect('admin_dashboard')

    if request.method == "POST":
        name = request.POST.get('name', '').strip()
        short_desc = request.POST.get('short_description', '').strip()
        description = request.POST.get('description', '').strip()
        duration_weeks = int(request.POST.get('duration_weeks') or 12)
        fee = Decimal(request.POST.get('fee') or '35000.00')
        is_published = request.POST.get('is_published') == 'on'

        if not name:
            messages.error(request, "Course name is required.")
            return redirect('/account/admin/dashboard/#courses')

        Course.objects.create(
            name=name,
            short_description=short_desc,
            description=description,
            duration_weeks=duration_weeks,
            fee=fee,
            is_published=is_published,
        )
        messages.success(request, f"Programme '{name}' created successfully!")
        return redirect('/account/admin/dashboard/#courses')

    return redirect('admin_dashboard')


@login_required
def admin_course_toggle_publish(request, course_id):
    """Toggles course published status on web admissions."""
    if not request.user.is_superuser:
        messages.error(request, "Access restricted to administrators.")
        return redirect('admin_dashboard')

    if request.method == "POST":
        course = get_object_or_404(Course, id=course_id)
        course.is_published = not course.is_published
        course.save(update_fields=['is_published'])

        status_text = "published and open for admissions" if course.is_published else "hidden from public admissions"
        messages.success(request, f"Course '{course.name}' is now {status_text}.")
        return redirect('/account/admin/dashboard/#courses')

    return redirect('admin_dashboard')


@login_required
def admin_batch_create(request):
    """Creates a new cohort/batch directly from the dashboard."""
    if not request.user.is_superuser:
        messages.error(request, "Access restricted to administrators.")
        return redirect('admin_dashboard')

    if request.method == "POST":
        name = request.POST.get('name', '').strip()
        course_id = request.POST.get('course_id')
        mode = request.POST.get('mode', 'onsite')
        batch_type = request.POST.get('batch_type', 'weekdays')
        session_period = request.POST.get('session_period', 'morning')
        days_pattern = request.POST.get('days_pattern', 'mon_wed_fri')
        start_date = request.POST.get('start_date') or timezone.now().date()
        end_date = request.POST.get('end_date') or (timezone.now() + timedelta(days=90)).date()
        max_students = int(request.POST.get('max_students') or 20)
        is_published = request.POST.get('is_published') == 'on'

        course = get_object_or_404(Course, id=course_id)

        Batch.objects.create(
            name=name or f"{course.name} - {mode.title()} {batch_type.title()}",
            course=course,
            mode=mode,
            batch_type=batch_type,
            session_period=session_period,
            days_pattern=days_pattern,
            start_date=start_date,
            end_date=end_date,
            max_students=max_students,
            is_published=is_published,
            created_by=request.user,
        )
        messages.success(request, f"Cohort created successfully for {course.name}!")
        return redirect('/account/admin/dashboard/#cohorts')

    return redirect('admin_dashboard')


@login_required
def admin_batch_toggle_publish(request, batch_id):
    """Toggles batch publishing/intake status."""
    if not request.user.is_superuser:
        messages.error(request, "Access restricted to administrators.")
        return redirect('admin_dashboard')

    if request.method == "POST":
        batch = get_object_or_404(Batch, id=batch_id)
        batch.is_published = not batch.is_published
        batch.save(update_fields=['is_published'])

        status_text = "opened for student intake" if batch.is_published else "closed/hidden"
        messages.success(request, f"Batch '{batch.name}' is now {status_text}.")
        return redirect('/account/admin/dashboard/#cohorts')

    return redirect('admin_dashboard')


@login_required
def admin_payment_record(request):
    """Records tuition payment installments and issues an automated receipt."""
    if not request.user.is_superuser:
        messages.error(request, "Access restricted to administrators.")
        return redirect('admin_dashboard')

    if request.method == "POST":
        student_id = request.POST.get('student_id')
        amount_raw = request.POST.get('amount', '0').strip()

        try:
            amount = Decimal(amount_raw)
            if amount <= 0:
                raise ValueError("Amount must be greater than zero.")
        except Exception:
            messages.error(request, "Invalid payment amount provided.")
            return redirect('/account/admin/dashboard/#billing')

        user = get_object_or_404(User, id=student_id)
        payment = Payment.objects.filter(student=user).first()

        if not payment:
            # Create payment record on the fly if missing
            course = getattr(user.profile, 'course', None) or Course.objects.first()
            payment = Payment.objects.create(
                student=user,
                course=course,
                batch=getattr(user.profile, 'batch', None),
                amount_due=getattr(course, 'fee', Decimal('35000.00')),
                amount_paid=Decimal('0.00'),
                monthly_payment=Decimal('35000.00'),
            )

        payment.amount_paid += amount
        payment.verified_by = request.user
        payment.update_status()

        # Generate official digital receipt
        receipt = Receipt.objects.create(
            payment=payment,
            amount=amount
        )

        # Update profile financial progression
        profile = user.profile
        profile.paid_amount = payment.amount_paid
        profile.tuition_paid = payment.status == 'paid'
        profile.has_paid = True
        profile.save(update_fields=['paid_amount', 'tuition_paid', 'has_paid'])

        messages.success(
            request,
            f"Payment of ₦{amount:,.2f} recorded for {user.get_full_name() or user.username}! Receipt #{str(receipt.reference)[:8].upper()} issued."
        )
        return redirect('/account/admin/dashboard/#billing')

    return redirect('admin_dashboard')


@login_required
def admin_attendance_mark(request):
    """Manually records or modifies student attendance from the command center."""
    if not request.user.is_superuser:
        messages.error(request, "Access restricted to administrators.")
        return redirect('admin_dashboard')

    if request.method == "POST":
        student_id = request.POST.get('student_id')
        subject_id = request.POST.get('subject_id')
        date_str = request.POST.get('date') or timezone.localdate().isoformat()
        status = request.POST.get('status', 'Present')
        remarks = request.POST.get('remarks', '').strip()

        student = get_object_or_404(User, id=student_id)
        subject = get_object_or_404(Subject, id=subject_id)
        batch = getattr(student.profile, 'batch', None)

        record, created = Attendance.objects.update_or_create(
            student=student,
            subject=subject,
            date=date_str,
            defaults={
                'batch': batch,
                'status': status,
                'marked_by': request.user,
                'remarks': remarks,
                'source': 'Admin Command Center',
                'check_in_time': timezone.localtime().time() if status == 'Present' else None
            }
        )

        action_word = "logged" if created else "updated"
        messages.success(request, f"Attendance {action_word}: {student.username} marked '{status}' for {subject.name}.")
        return redirect('/account/admin/dashboard/#attendance')

    return redirect('admin_dashboard')