from functools import wraps

from django.contrib import messages
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from apps.attendance.models import Attendance

from .models import Assignment, Announcement, Parent, StudentParent
from .parent_forms import ParentLoginForm, ParentPasswordChangeForm


PARENT_SESSION_KEY = "parent_portal_parent_id"


def get_session_parent(request):
    parent_id = request.session.get(PARENT_SESSION_KEY)

    if not parent_id:
        return None

    return Parent.objects.filter(
        id=parent_id,
        is_active=True,
    ).first()


def parent_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        parent = get_session_parent(request)

        if parent is None:
            login_url = reverse("parent_template_login")
            return redirect(f"{login_url}?next={request.path}")

        request.parent = parent

        return view_func(request, *args, **kwargs)

    return wrapped


def parent_login(request):
    parent = get_session_parent(request)

    if parent is not None:
        return redirect("parent_template_dashboard")

    form = ParentLoginForm()
    next_url = request.GET.get("next") or request.POST.get("next") or ""

    if request.method == "POST":
        form = ParentLoginForm(request.POST)

        if form.is_valid():
            phone_number = form.cleaned_data["phone_number"].strip()
            password = form.cleaned_data["password"]

            parent = Parent.objects.filter(
                phone_number=phone_number,
                is_active=True,
            ).first()

            if parent and parent.check_password(password):
                request.session[PARENT_SESSION_KEY] = parent.id
                request.session.cycle_key()
                parent.update_last_login()

                if parent.must_change_password:
                    return redirect("parent_template_password")

                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)

                return redirect("parent_template_dashboard")

            messages.error(
                request,
                "Invalid phone number or password.",
            )

    return render(
        request,
        "parents/login.html",
        {
            "form": form,
            "next_url": next_url,
        },
    )


def parent_logout(request):
    request.session.pop(PARENT_SESSION_KEY, None)
    messages.success(
        request,
        "You have been logged out.",
    )

    return redirect("parent_template_login")


@parent_required
def parent_dashboard(request):
    parent = request.parent

    if parent.must_change_password:
        return redirect("parent_template_password")

    today = timezone.localdate()
    relationships = (
        StudentParent.objects.select_related("student")
        .filter(parent=parent)
        .order_by("student__first_name", "student__last_name")
    )

    children = []
    child_classes = []
    child_class_names = []
    present_today = 0
    checked_out_today = 0

    for relation in relationships:
        student = relation.student
        attendance = Attendance.objects.filter(
            student=student,
            date=today,
        ).first()
        latest_attendance = (
            Attendance.objects.filter(student=student)
            .order_by("-date", "-check_in")
            .first()
        )

        if attendance:
            present_today += 1

            if attendance.check_out:
                checked_out_today += 1

        if student.teaching_class:
            child_classes.append(student.teaching_class)

        if student.class_name:
            child_class_names.append(student.class_name)

        children.append(
            {
                "student": student,
                "relationship": relation.relationship,
                "attendance": attendance,
                "latest_attendance": latest_attendance,
                "status": attendance.status if attendance else "ABSENT",
            }
        )

    total_children = len(children)
    absent_today = total_children - present_today
    assignments = Assignment.objects.none()
    announcements = Announcement.objects.none()

    if child_classes:
        assignments = (
            Assignment.objects.filter(
                teaching_class__in=child_classes,
                is_active=True,
            )
            .select_related("teaching_class")
            .order_by("-created_at")[:10]
        )

    announcements = (
        Announcement.objects.filter(
            is_active=True,
        )
        .filter(
            models.Q(expires_at__isnull=True)
            | models.Q(expires_at__gte=timezone.now())
        )
        .filter(
            models.Q(target=Announcement.TARGET_ALL)
            | models.Q(teaching_class__in=child_classes)
            | models.Q(class_name__in=child_class_names)
        )
        .select_related("teaching_class")
        .order_by("-publish_at")[:10]
    )

    return render(
        request,
        "parents/dashboard.html",
        {
            "parent": parent,
            "children": children,
            "assignments": assignments,
            "announcements": announcements,
            "today": today,
            "summary": {
                "total_children": total_children,
                "present_today": present_today,
                "checked_out_today": checked_out_today,
                "absent_today": absent_today,
            },
        },
    )


@parent_required
def parent_child_history(request, student_id):
    parent = request.parent

    if parent.must_change_password:
        return redirect("parent_template_password")

    relation = get_object_or_404(
        StudentParent.objects.select_related("student"),
        parent=parent,
        student_id=student_id,
    )
    student = relation.student
    history = (
        Attendance.objects.filter(student=student)
        .order_by("-date", "-check_in")[:90]
    )

    return render(
        request,
        "parents/child_history.html",
        {
            "parent": parent,
            "student": student,
            "relationship": relation.relationship,
            "history": history,
        },
    )


@parent_required
def parent_change_password(request):
    parent = request.parent
    form = ParentPasswordChangeForm()

    if request.method == "POST":
        form = ParentPasswordChangeForm(request.POST)

        if form.is_valid():
            current_password = form.cleaned_data["current_password"]
            new_password = form.cleaned_data["new_password"]

            if not parent.check_password(current_password):
                form.add_error(
                    "current_password",
                    "Current password is incorrect.",
                )
            else:
                parent.set_password(new_password)
                parent.must_change_password = False
                parent.last_password_change = timezone.now()
                parent.save(
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

                return redirect("parent_template_dashboard")

    return render(
        request,
        "parents/change_password.html",
        {
            "parent": parent,
            "form": form,
        },
    )
