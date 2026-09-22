import json
from functools import wraps

from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login,
    logout,
    update_session_auth_hash,
)
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.attendance.models import Attendance
from apps.notifications.attendance_notifications import (
    get_parent_name,
    get_parent_whatsapp,
    notify_check_in,
    notify_check_out,
)
from apps.settings_app.models import SystemSettings

from .models import Announcement, Assignment, Student, TeachingClass
from .staff_forms import (
    StaffAnnouncementForm,
    StaffAssignmentForm,
    StaffLoginForm,
    StaffPasswordChangeForm,
    get_staff_classes,
)


def is_admin_user(user):
    return user.is_authenticated and (
        user.is_superuser
        or getattr(user, "role", "") == "ADMIN"
    )


def is_staff_portal_user(user):
    return user.is_authenticated and (
        is_admin_user(user)
        or getattr(user, "role", "") == "TEACHER"
    )


def staff_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not is_staff_portal_user(request.user):
            login_url = reverse("staff_login")
            return redirect(f"{login_url}?next={request.path}")

        url_name = getattr(request.resolver_match, "url_name", "")

        if (
            getattr(request.user, "staff_must_change_password", False)
            and url_name not in {"staff_change_password", "staff_logout"}
        ):
            return redirect("staff_change_password")

        return view_func(request, *args, **kwargs)

    return wrapped


def staff_can_access_class(user, teaching_class):
    if is_admin_user(user):
        return True

    return teaching_class.staff_id == user.id


def staff_can_access_student(user, student):
    if is_admin_user(user):
        return True

    return (
        student.teaching_class_id is not None
        and student.teaching_class.staff_id == user.id
    )


def staff_login(request):
    if is_staff_portal_user(request.user):
        return redirect("staff_dashboard")

    form = StaffLoginForm()
    next_url = request.GET.get("next") or request.POST.get("next") or ""

    if request.method == "POST":
        form = StaffLoginForm(request.POST)

        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
            )

            if user and is_staff_portal_user(user):
                login(request, user)

                if getattr(user, "staff_must_change_password", False):
                    return redirect("staff_change_password")

                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)

                return redirect("staff_dashboard")

            messages.error(
                request,
                "Invalid staff login details.",
            )

    return render(
        request,
        "staff/login.html",
        {
            "form": form,
            "next_url": next_url,
        },
    )


def staff_logout(request):
    logout(request)
    messages.success(
        request,
        "You have been logged out.",
    )

    return redirect("staff_login")


@staff_required
def staff_change_password(request):
    form = StaffPasswordChangeForm(request.user)

    if request.method == "POST":
        form = StaffPasswordChangeForm(
            request.user,
            request.POST,
        )

        if form.is_valid():
            user = form.save()
            user.staff_must_change_password = False
            user.save(
                update_fields=[
                    "staff_must_change_password",
                ]
            )
            update_session_auth_hash(request, user)
            messages.success(
                request,
                "Your password has been updated.",
            )
            return redirect("staff_dashboard")

    return render(
        request,
        "staff/change_password.html",
        {
            "form": form,
        },
    )


@staff_required
def staff_dashboard(request):
    classes = get_staff_classes(request.user).prefetch_related("students")
    today = timezone.localdate()
    class_cards = []
    total_students = 0
    present_today = 0

    for teaching_class in classes:
        students = teaching_class.students.filter(is_active=True)
        student_count = students.count()
        attendance_count = Attendance.objects.filter(
            student__in=students,
            date=today,
        ).count()

        total_students += student_count
        present_today += attendance_count
        class_cards.append(
            {
                "class": teaching_class,
                "student_count": student_count,
                "present_today": attendance_count,
                "absent_today": max(student_count - attendance_count, 0),
            }
        )

    assignments = Assignment.objects.filter(
        teaching_class__in=classes,
    ).select_related("teaching_class")[:8]
    announcements = Announcement.objects.filter(
        teaching_class__in=classes,
    ).select_related("teaching_class")[:8]

    return render(
        request,
        "staff/dashboard.html",
        {
            "class_cards": class_cards,
            "assignments": assignments,
            "announcements": announcements,
            "summary": {
                "classes": len(class_cards),
                "students": total_students,
                "present_today": present_today,
                "absent_today": max(total_students - present_today, 0),
            },
        },
    )


@staff_required
def staff_class_detail(request, class_id):
    teaching_class = get_object_or_404(TeachingClass, id=class_id)

    if not staff_can_access_class(request.user, teaching_class):
        messages.error(
            request,
            "You do not have access to that class.",
        )
        return redirect("staff_dashboard")

    today = timezone.localdate()
    students = (
        teaching_class.students.filter(is_active=True)
        .order_by("first_name", "last_name")
    )
    rows = []

    for student in students:
        attendance = Attendance.objects.filter(
            student=student,
            date=today,
        ).first()
        rows.append(
            {
                "student": student,
                "attendance": attendance,
                "status": attendance.status if attendance else "ABSENT",
            }
        )

    return render(
        request,
        "staff/class_detail.html",
        {
            "teaching_class": teaching_class,
            "rows": rows,
            "today": today,
        },
    )


@staff_required
def staff_scanner(request):
    return render(
        request,
        "staff/scanner.html",
        {
            "classes": get_staff_classes(request.user),
        },
    )


@staff_required
@require_POST
def staff_scan_attendance(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "error": "Invalid request body.",
            },
            status=400,
        )

    student_id = body.get("student_id")

    if not student_id:
        return JsonResponse(
            {
                "error": "Student ID is required.",
            },
            status=400,
        )

    student = Student.objects.filter(
        student_id=student_id,
        is_active=True,
    ).select_related("teaching_class").first()

    if student is None:
        return JsonResponse(
            {
                "error": "Student not found.",
            },
            status=404,
        )

    if not staff_can_access_student(request.user, student):
        return JsonResponse(
            {
                "error": "This student is not assigned to your class.",
            },
            status=403,
        )

    today = timezone.localdate()
    attendance, _ = Attendance.objects.get_or_create(
        student=student,
        date=today,
    )
    now = timezone.now()
    settings_obj = SystemSettings.objects.first()
    auto_whatsapp_popup = (
        settings_obj.auto_whatsapp_popup
        if settings_obj
        else False
    )

    if attendance.check_in is None:
        attendance.check_in = now
        attendance.save(update_fields=["check_in"])
        notify_check_in(student, now)
        status = "CHECK_IN"
    elif attendance.check_out is None:
        attendance.check_out = now
        attendance.save(update_fields=["check_out"])
        notify_check_out(student, now)
        status = "CHECK_OUT"
    else:
        status = "ALREADY_COMPLETED"

    return JsonResponse(
        {
            "status": status,
            "student_name": student.full_name,
            "student_id": student.student_id,
            "class_name": (
                student.teaching_class.name
                if student.teaching_class
                else student.class_name
            ),
            "parent": (
                get_parent_name(student)
                if student.parents.exists()
                else "N/A"
            ),
            "time": now.strftime("%H:%M:%S"),
            "whatsapp_url": get_parent_whatsapp(student),
            "auto_whatsapp_popup": auto_whatsapp_popup,
        }
    )


@staff_required
def staff_assignments(request):
    classes = get_staff_classes(request.user)
    form = StaffAssignmentForm(user=request.user)

    if request.method == "POST":
        form = StaffAssignmentForm(
            request.POST,
            request.FILES,
            user=request.user,
        )

        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.created_by = request.user

            if not staff_can_access_class(request.user, assignment.teaching_class):
                messages.error(
                    request,
                    "You cannot create assignments for that class.",
                )
            else:
                assignment.save()
                messages.success(
                    request,
                    "Assignment uploaded successfully.",
                )
                return redirect("staff_assignments")

    assignments = (
        Assignment.objects.filter(teaching_class__in=classes)
        .select_related("teaching_class", "created_by")
        .order_by("-created_at")
    )

    return render(
        request,
        "staff/assignments.html",
        {
            "form": form,
            "assignments": assignments,
        },
    )


@staff_required
def staff_announcements(request):
    classes = get_staff_classes(request.user)
    form = StaffAnnouncementForm(user=request.user)

    if request.method == "POST":
        form = StaffAnnouncementForm(
            request.POST,
            request.FILES,
            user=request.user,
        )

        if form.is_valid():
            announcement = form.save(commit=False)

            if not staff_can_access_class(request.user, announcement.teaching_class):
                messages.error(
                    request,
                    "You cannot create announcements for that class.",
                )
            else:
                announcement.target = Announcement.TARGET_CLASS
                announcement.class_name = announcement.teaching_class.name
                announcement.created_by = request.user.get_username()
                announcement.save()
                messages.success(
                    request,
                    "Announcement published successfully.",
                )
                return redirect("staff_announcements")

    announcements = (
        Announcement.objects.filter(teaching_class__in=classes)
        .select_related("teaching_class")
        .order_by("-publish_at")
    )

    return render(
        request,
        "staff/announcements.html",
        {
            "form": form,
            "announcements": announcements,
        },
    )
