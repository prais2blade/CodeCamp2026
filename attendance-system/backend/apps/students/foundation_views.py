from functools import wraps

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from apps.attendance.models import Attendance

from .foundation_forms import (
    FoundationLoginForm,
    FoundationPasswordChangeForm,
)
from .foundation_services import (
    get_foundation_student_rows,
    get_student_attendance_summary,
    normalize_monitoring_days,
)
from .models import Foundation, PerformanceRecord, StudentFoundation


FOUNDATION_SESSION_KEY = "foundation_portal_foundation_id"


def get_session_foundation(request):
    foundation_id = request.session.get(FOUNDATION_SESSION_KEY)

    if not foundation_id:
        return None

    return Foundation.objects.filter(
        id=foundation_id,
        is_active=True,
    ).first()


def foundation_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        foundation = get_session_foundation(request)

        if foundation is None:
            login_url = reverse("foundation_login")
            return redirect(f"{login_url}?next={request.path}")

        request.foundation = foundation

        if (
            foundation.must_change_password
            and getattr(request.resolver_match, "url_name", "")
            not in {"foundation_change_password", "foundation_logout"}
        ):
            return redirect("foundation_change_password")

        return view_func(request, *args, **kwargs)

    return wrapped


def foundation_login(request):
    foundation = get_session_foundation(request)

    if foundation is not None:
        return redirect("foundation_dashboard")

    form = FoundationLoginForm()
    next_url = request.GET.get("next") or request.POST.get("next") or ""

    if request.method == "POST":
        form = FoundationLoginForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            password = form.cleaned_data["password"]
            foundation = Foundation.objects.filter(
                email__iexact=email,
                is_active=True,
            ).first()

            if foundation and foundation.check_password(password):
                request.session[FOUNDATION_SESSION_KEY] = foundation.id
                request.session.cycle_key()
                foundation.update_last_login()

                if foundation.must_change_password:
                    return redirect("foundation_change_password")

                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)

                return redirect("foundation_dashboard")

            messages.error(
                request,
                "Invalid email or password.",
            )

    return render(
        request,
        "foundation/login.html",
        {
            "form": form,
            "next_url": next_url,
        },
    )


def foundation_logout(request):
    request.session.pop(FOUNDATION_SESSION_KEY, None)
    messages.success(
        request,
        "You have been logged out.",
    )

    return redirect("foundation_login")


@foundation_required
def foundation_change_password(request):
    foundation = request.foundation
    form = FoundationPasswordChangeForm()

    if request.method == "POST":
        form = FoundationPasswordChangeForm(request.POST)

        if form.is_valid():
            current_password = form.cleaned_data["current_password"]
            new_password = form.cleaned_data["new_password"]

            if not foundation.check_password(current_password):
                form.add_error(
                    "current_password",
                    "Current password is incorrect.",
                )
            else:
                foundation.set_password(new_password)
                foundation.must_change_password = False
                foundation.last_password_change = timezone.now()
                foundation.save(
                    update_fields=[
                        "password",
                        "must_change_password",
                        "last_password_change",
                    ]
                )
                messages.success(
                    request,
                    "Password changed successfully.",
                )
                return redirect("foundation_dashboard")

    return render(
        request,
        "foundation/change_password.html",
        {
            "foundation": foundation,
            "form": form,
        },
    )


@foundation_required
def foundation_dashboard(request):
    foundation = request.foundation
    days = normalize_monitoring_days(request.GET.get("days"))
    rows = get_foundation_student_rows(
        foundation,
        days=days,
    )
    sponsored_students = len(rows)
    total_present_days = sum(
        row["attendance"]["present_days"]
        for row in rows
    )
    average_attendance = 0

    if sponsored_students and days:
        average_attendance = round(
            total_present_days / (sponsored_students * days) * 100,
            1,
        )

    performance_records = (
        PerformanceRecord.objects.filter(
            student__foundation_links__foundation=foundation,
            student__foundation_links__is_active=True,
            visible_to_foundations=True,
        )
        .select_related("student")
        .distinct()[:8]
    )

    return render(
        request,
        "foundation/dashboard.html",
        {
            "foundation": foundation,
            "rows": rows,
            "days": days,
            "performance_records": performance_records,
            "summary": {
                "sponsored_students": sponsored_students,
                "average_attendance": average_attendance,
                "performance_records": performance_records.count(),
            },
        },
    )


@foundation_required
def foundation_student_detail(request, student_id):
    foundation = request.foundation
    link = get_object_or_404(
        StudentFoundation.objects.select_related(
            "student",
            "student__teaching_class",
        ),
        foundation=foundation,
        student_id=student_id,
        is_active=True,
    )
    student = link.student
    days = normalize_monitoring_days(request.GET.get("days"), default=90)
    attendance_summary = get_student_attendance_summary(
        student,
        days=days,
    )
    attendance_history = Attendance.objects.filter(
        student=student,
    ).order_by(
        "-date",
        "-check_in",
    )[:90]
    performance_records = PerformanceRecord.objects.filter(
        student=student,
        visible_to_foundations=True,
    )

    return render(
        request,
        "foundation/student_detail.html",
        {
            "foundation": foundation,
            "link": link,
            "student": student,
            "days": days,
            "attendance_summary": attendance_summary,
            "attendance_history": attendance_history,
            "performance_records": performance_records,
        },
    )
