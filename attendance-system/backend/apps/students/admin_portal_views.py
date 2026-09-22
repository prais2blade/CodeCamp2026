from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.crypto import get_random_string
from django.views.decorators.http import require_POST

from apps.attendance.models import Attendance
from apps.notifications.onboarding import (
    send_foundation_onboarding_email,
    send_parent_onboarding_email,
    send_staff_onboarding_email,
)

from .admin_auth import admin_required, is_admin_portal_user
from .admin_portal_forms import (
    AdminLoginForm,
    FoundationCreateForm,
    FoundationEditForm,
    FoundationStudentForm,
    ParentAdminForm,
    PerformanceRecordForm,
    StaffUserCreateForm,
    StaffUserEditForm,
    StudentClassAssignmentForm,
    TeachingClassAdminForm,
    generate_foundation_temporary_password,
    generate_staff_temporary_password,
)
from .foundation_services import (
    get_foundation_student_rows,
    normalize_monitoring_days,
)
from .models import (
    Assignment,
    Foundation,
    Parent,
    PerformanceRecord,
    Student,
    StudentFoundation,
    StudentParent,
    TeachingClass,
)


def admin_login(request):
    if is_admin_portal_user(request.user):
        return redirect("school_admin:dashboard")

    form = AdminLoginForm()
    next_url = request.GET.get("next") or request.POST.get("next") or ""

    if request.method == "POST":
        form = AdminLoginForm(request.POST)

        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
            )

            if user and is_admin_portal_user(user):
                login(request, user)

                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)

                return redirect("school_admin:dashboard")

            messages.error(
                request,
                "Invalid admin login details.",
            )

    return render(
        request,
        "admin_portal/login.html",
        {
            "form": form,
            "next_url": next_url,
        },
    )


def admin_logout(request):
    logout(request)
    messages.success(
        request,
        "You have been logged out.",
    )

    return redirect("school_admin:login")


@admin_required
def admin_dashboard(request):
    User = get_user_model()
    today = timezone.localdate()

    students = Student.objects.filter(is_active=True)
    classes = TeachingClass.objects.filter(is_active=True)
    parents = Parent.objects.filter(is_active=True)
    foundations = Foundation.objects.filter(is_active=True)
    staff = User.objects.filter(role=User.TEACHER)
    present_today = Attendance.objects.filter(date=today).values(
        "student",
    ).distinct().count()

    class_rows = (
        classes.select_related("staff")
        .annotate(student_count=Count("students"))
        .order_by("name")[:8]
    )
    unassigned_students = students.filter(teaching_class__isnull=True).count()
    recent_assignments = Assignment.objects.select_related(
        "teaching_class",
        "created_by",
    )[:5]

    return render(
        request,
        "admin_portal/dashboard.html",
        {
            "summary": {
                "students": students.count(),
                "classes": classes.count(),
                "parents": parents.count(),
                "foundations": foundations.count(),
                "staff": staff.filter(is_active=True).count(),
                "present_today": present_today,
                "unassigned_students": unassigned_students,
            },
            "class_rows": class_rows,
            "recent_assignments": recent_assignments,
        },
    )


@admin_required
def admin_foundation_list(request):
    search = request.GET.get("search", "").strip()
    foundations = Foundation.objects.annotate(
        sponsored_count=Count("student_links", distinct=True),
    ).order_by("name")

    if search:
        foundations = foundations.filter(
            Q(name__icontains=search)
            | Q(contact_person__icontains=search)
            | Q(email__icontains=search)
            | Q(phone_number__icontains=search)
        )

    return render(
        request,
        "admin_portal/foundation_list.html",
        {
            "foundations": foundations,
            "search": search,
        },
    )


@admin_required
def admin_foundation_create(request):
    form = FoundationCreateForm()

    if request.method == "POST":
        form = FoundationCreateForm(request.POST)

        if form.is_valid():
            foundation = form.save()
            notification = send_foundation_onboarding_email(
                foundation=foundation,
                temporary_password=form.generated_password,
                base_url=request.build_absolute_uri("/"),
            )
            messages.success(
                request,
                f"{foundation.name} was created.",
            )
            add_onboarding_email_message(
                request=request,
                notification=notification,
                recipient_email=foundation.email,
                missing_message=(
                    "No onboarding email was sent because the foundation "
                    "account has no email address."
                ),
                sent_message=f"Login details were emailed to {foundation.email}.",
                failed_message=(
                    "The foundation account was created, but the onboarding "
                    "email could not be sent."
                ),
            )
            return render(
                request,
                "admin_portal/foundation_onboarding.html",
                {
                    "foundation": foundation,
                    "temporary_password": form.generated_password,
                    "foundation_login_url": request.build_absolute_uri(
                        reverse("foundation_login")
                    ),
                    "email_notification": notification,
                },
            )

    return render(
        request,
        "admin_portal/foundation_form.html",
        {
            "form": form,
            "title": "Create Foundation",
            "button_label": "Save Foundation",
        },
    )


@admin_required
def admin_foundation_detail(request, foundation_id):
    foundation = get_object_or_404(
        Foundation,
        pk=foundation_id,
    )
    days = normalize_monitoring_days(request.GET.get("days"))
    rows = get_foundation_student_rows(
        foundation,
        days=days,
    )
    active_links = foundation.student_links.filter(is_active=True)
    performance_records = (
        PerformanceRecord.objects.filter(
            student__foundation_links__foundation=foundation,
            student__foundation_links__is_active=True,
        )
        .select_related("student")
        .distinct()[:10]
    )

    return render(
        request,
        "admin_portal/foundation_detail.html",
        {
            "foundation": foundation,
            "rows": rows,
            "days": days,
            "active_link_count": active_links.count(),
            "performance_records": performance_records,
        },
    )


@admin_required
def admin_foundation_edit(request, foundation_id):
    foundation = get_object_or_404(
        Foundation,
        pk=foundation_id,
    )
    form = FoundationEditForm(instance=foundation)

    if request.method == "POST":
        form = FoundationEditForm(
            request.POST,
            instance=foundation,
        )

        if form.is_valid():
            foundation = form.save()
            messages.success(
                request,
                f"{foundation.name} was updated.",
            )
            return redirect(
                "school_admin:foundation_detail",
                foundation_id=foundation.id,
            )

    return render(
        request,
        "admin_portal/foundation_form.html",
        {
            "form": form,
            "foundation": foundation,
            "title": "Edit Foundation",
            "button_label": "Save Changes",
        },
    )


@admin_required
def admin_foundation_delete(request, foundation_id):
    foundation = get_object_or_404(
        Foundation.objects.annotate(
            sponsored_count=Count("student_links"),
        ),
        pk=foundation_id,
    )

    if request.method == "POST":
        name = foundation.name
        foundation.delete()
        messages.success(
            request,
            f"{name} was deleted.",
        )
        return redirect("school_admin:foundation_list")

    return render(
        request,
        "admin_portal/foundation_confirm_delete.html",
        {
            "foundation": foundation,
        },
    )


@admin_required
@require_POST
def admin_foundation_reset_password(request, foundation_id):
    foundation = get_object_or_404(
        Foundation,
        pk=foundation_id,
    )
    temporary_password = generate_foundation_temporary_password()
    foundation.set_password(temporary_password)
    foundation.must_change_password = True
    foundation.save(
        update_fields=[
            "password",
            "must_change_password",
        ]
    )
    notification = send_foundation_onboarding_email(
        foundation=foundation,
        temporary_password=temporary_password,
        base_url=request.build_absolute_uri("/"),
    )
    add_onboarding_email_message(
        request=request,
        notification=notification,
        recipient_email=foundation.email,
        missing_message=(
            "No onboarding email was sent because the foundation "
            "account has no email address."
        ),
        sent_message=f"Login details were emailed to {foundation.email}.",
        failed_message=(
            "The foundation password was reset, but the onboarding "
            "email could not be sent."
        ),
    )

    return render(
        request,
        "admin_portal/foundation_onboarding.html",
        {
            "foundation": foundation,
            "temporary_password": temporary_password,
            "foundation_login_url": request.build_absolute_uri(
                reverse("foundation_login")
            ),
            "email_notification": notification,
        },
    )


@admin_required
def admin_foundation_student_add(request, foundation_id):
    foundation = get_object_or_404(
        Foundation,
        pk=foundation_id,
    )
    form = FoundationStudentForm(foundation=foundation)

    if request.method == "POST":
        form = FoundationStudentForm(
            request.POST,
            foundation=foundation,
        )

        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                form.add_error(
                    "student",
                    "This student is already assigned to this foundation.",
                )
            else:
                messages.success(
                    request,
                    "Sponsored student was added.",
                )
                return redirect(
                    "school_admin:foundation_detail",
                    foundation_id=foundation.id,
                )

    return render(
        request,
        "admin_portal/foundation_student_form.html",
        {
            "form": form,
            "foundation": foundation,
        },
    )


@admin_required
@require_POST
def admin_foundation_student_remove(request, link_id):
    link = get_object_or_404(
        StudentFoundation,
        pk=link_id,
    )
    foundation_id = link.foundation_id
    student_name = link.student.full_name
    link.delete()
    messages.success(
        request,
        f"{student_name} was removed from the foundation.",
    )

    return redirect(
        "school_admin:foundation_detail",
        foundation_id=foundation_id,
    )


@admin_required
def admin_performance_list(request):
    search = request.GET.get("search", "").strip()
    records = PerformanceRecord.objects.select_related(
        "student",
        "teaching_class",
        "uploaded_by",
    )

    if search:
        records = records.filter(
            Q(student__student_id__icontains=search)
            | Q(student__first_name__icontains=search)
            | Q(student__last_name__icontains=search)
            | Q(title__icontains=search)
            | Q(subject__icontains=search)
            | Q(term__icontains=search)
        )

    return render(
        request,
        "admin_portal/performance_list.html",
        {
            "records": records,
            "search": search,
        },
    )


@admin_required
def admin_performance_create(request):
    student_id = request.GET.get("student")
    initial_student = None

    if student_id:
        initial_student = Student.objects.filter(pk=student_id).first()

    form = PerformanceRecordForm(initial_student=initial_student)

    if request.method == "POST":
        form = PerformanceRecordForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            record = form.save(commit=False)
            record.uploaded_by = request.user
            record.save()
            messages.success(
                request,
                "Performance record was uploaded.",
            )
            return redirect("school_admin:performance_list")

    return render(
        request,
        "admin_portal/performance_form.html",
        {
            "form": form,
            "title": "Upload Performance",
            "button_label": "Save Performance",
        },
    )


@admin_required
def admin_performance_edit(request, record_id):
    record = get_object_or_404(
        PerformanceRecord,
        pk=record_id,
    )
    form = PerformanceRecordForm(instance=record)

    if request.method == "POST":
        form = PerformanceRecordForm(
            request.POST,
            request.FILES,
            instance=record,
        )

        if form.is_valid():
            record = form.save(commit=False)
            record.uploaded_by = request.user
            record.save()
            messages.success(
                request,
                "Performance record was updated.",
            )
            return redirect("school_admin:performance_list")

    return render(
        request,
        "admin_portal/performance_form.html",
        {
            "form": form,
            "record": record,
            "title": "Edit Performance",
            "button_label": "Save Changes",
        },
    )


@admin_required
def admin_performance_delete(request, record_id):
    record = get_object_or_404(
        PerformanceRecord.objects.select_related("student"),
        pk=record_id,
    )

    if request.method == "POST":
        record.delete()
        messages.success(
            request,
            "Performance record was deleted.",
        )
        return redirect("school_admin:performance_list")

    return render(
        request,
        "admin_portal/performance_confirm_delete.html",
        {
            "record": record,
        },
    )


@admin_required
def admin_parent_list(request):
    search = request.GET.get("search", "").strip()
    parents = Parent.objects.annotate(
        child_count=Count("students", distinct=True),
    ).order_by("full_name")

    if search:
        parents = parents.filter(
            Q(full_name__icontains=search)
            | Q(phone_number__icontains=search)
            | Q(whatsapp_number__icontains=search)
            | Q(email__icontains=search)
            | Q(students__student__student_id__icontains=search)
            | Q(students__student__first_name__icontains=search)
            | Q(students__student__last_name__icontains=search)
        ).distinct()

    return render(
        request,
        "admin_portal/parent_list.html",
        {
            "parents": parents,
            "search": search,
        },
    )


@admin_required
def admin_parent_detail(request, parent_id):
    parent = get_object_or_404(
        Parent.objects.prefetch_related(
            "students__student__teaching_class",
        ),
        pk=parent_id,
    )

    return render(
        request,
        "admin_portal/parent_detail.html",
        {
            "parent": parent,
            "student_links": parent.students.all(),
        },
    )


@admin_required
def admin_parent_edit(request, parent_id):
    parent = get_object_or_404(
        Parent,
        pk=parent_id,
    )
    form = ParentAdminForm(instance=parent)

    if request.method == "POST":
        form = ParentAdminForm(
            request.POST,
            instance=parent,
        )

        if form.is_valid():
            parent = form.save()
            messages.success(
                request,
                f"{parent.full_name} was updated.",
            )
            return redirect(
                "school_admin:parent_detail",
                parent_id=parent.id,
            )

    return render(
        request,
        "admin_portal/parent_form.html",
        {
            "form": form,
            "parent": parent,
        },
    )


@admin_required
def admin_parent_delete(request, parent_id):
    parent = get_object_or_404(
        Parent.objects.prefetch_related(
            "students__student",
        ),
        pk=parent_id,
    )

    if request.method == "POST":
        parent_name = parent.full_name
        parent.delete()
        messages.success(
            request,
            f"{parent_name} was deleted.",
        )
        return redirect("school_admin:parent_list")

    return render(
        request,
        "admin_portal/parent_confirm_delete.html",
        {
            "parent": parent,
            "student_links": parent.students.all(),
        },
    )


@admin_required
@require_POST
def admin_parent_reset_password(request, parent_id):
    parent = get_object_or_404(
        Parent,
        pk=parent_id,
    )
    temporary_password = generate_parent_temporary_password()
    parent.set_password(temporary_password)
    parent.must_change_password = True
    parent.save(
        update_fields=[
            "password",
            "must_change_password",
        ]
    )
    notification = send_parent_onboarding_email(
        parent=parent,
        temporary_password=temporary_password,
        base_url=request.build_absolute_uri("/"),
    )

    if notification is None:
        messages.warning(
            request,
            (
                "Parent password was reset, but no email was sent "
                "because no active email is available."
            ),
        )
    elif notification.status == "sent":
        messages.success(
            request,
            f"Login details were emailed to {parent.email}.",
        )
    else:
        messages.warning(
            request,
            "Parent password was reset, but the email could not be sent.",
        )

    return render(
        request,
        "admin_portal/parent_onboarding.html",
        {
            "parent": parent,
            "temporary_password": temporary_password,
            "parent_login_url": request.build_absolute_uri(
                reverse("parent_template_login")
            ),
            "email_notification": notification,
        },
    )


@admin_required
def admin_staff_list(request):
    User = get_user_model()
    staff = User.objects.filter(role=User.TEACHER).order_by(
        "first_name",
        "last_name",
        "username",
    )

    return render(
        request,
        "admin_portal/staff_list.html",
        {
            "staff": staff,
        },
    )


@admin_required
def admin_staff_create(request):
    form = StaffUserCreateForm()

    if request.method == "POST":
        form = StaffUserCreateForm(request.POST)

        if form.is_valid():
            user = form.save()
            notification = send_staff_onboarding_email(
                staff_user=user,
                temporary_password=form.generated_password,
                base_url=request.build_absolute_uri("/"),
            )
            messages.success(
                request,
                f"Staff account {user.username} was created.",
            )
            add_onboarding_email_message(
                request=request,
                notification=notification,
                recipient_email=user.email,
                missing_message=(
                    "No onboarding email was sent because the staff "
                    "account has no email address."
                ),
                sent_message=f"Login details were emailed to {user.email}.",
                failed_message=(
                    "The staff account was created, but the onboarding "
                    "email could not be sent."
                ),
            )
            return render(
                request,
                "admin_portal/staff_onboarding.html",
                {
                    "staff_user": user,
                    "temporary_password": form.generated_password,
                    "staff_login_url": request.build_absolute_uri(
                        reverse("staff_login")
                    ),
                    "email_notification": notification,
                },
            )

    return render(
        request,
        "admin_portal/staff_create.html",
        {
            "form": form,
        },
    )


@admin_required
def admin_staff_edit(request, staff_id):
    User = get_user_model()
    staff_user = get_object_or_404(
        User,
        pk=staff_id,
        role=User.TEACHER,
    )
    form = StaffUserEditForm(instance=staff_user)

    if request.method == "POST":
        form = StaffUserEditForm(
            request.POST,
            instance=staff_user,
        )

        if form.is_valid():
            staff_user = form.save()
            messages.success(
                request,
                f"{staff_user.username} was updated.",
            )
            return redirect("school_admin:staff_list")

    return render(
        request,
        "admin_portal/staff_edit.html",
        {
            "form": form,
            "staff_user": staff_user,
        },
    )


@admin_required
def admin_staff_delete(request, staff_id):
    User = get_user_model()
    staff_user = get_object_or_404(
        User.objects.annotate(
            class_count=Count("teaching_classes"),
        ),
        pk=staff_id,
        role=User.TEACHER,
    )

    if request.method == "POST":
        username = staff_user.username
        staff_user.delete()
        messages.success(
            request,
            f"{username} was deleted.",
        )
        return redirect("school_admin:staff_list")

    return render(
        request,
        "admin_portal/staff_confirm_delete.html",
        {
            "staff_user": staff_user,
        },
    )


@admin_required
@require_POST
def admin_staff_reset_password(request, staff_id):
    User = get_user_model()
    staff_user = get_object_or_404(
        User,
        pk=staff_id,
        role=User.TEACHER,
    )
    temporary_password = generate_staff_temporary_password()
    staff_user.set_password(temporary_password)
    staff_user.staff_must_change_password = True
    staff_user.save(
        update_fields=[
            "password",
            "staff_must_change_password",
        ]
    )

    messages.success(
        request,
        f"Temporary password reset for {staff_user.username}.",
    )
    notification = send_staff_onboarding_email(
        staff_user=staff_user,
        temporary_password=temporary_password,
        base_url=request.build_absolute_uri("/"),
    )
    add_onboarding_email_message(
        request=request,
        notification=notification,
        recipient_email=staff_user.email,
        missing_message=(
            "No onboarding email was sent because the staff account "
            "has no email address."
        ),
        sent_message=f"Login details were emailed to {staff_user.email}.",
        failed_message=(
            "The password was reset, but the onboarding email could "
            "not be sent."
        ),
    )

    return render(
        request,
        "admin_portal/staff_onboarding.html",
        {
            "staff_user": staff_user,
            "temporary_password": temporary_password,
            "staff_login_url": request.build_absolute_uri(
                reverse("staff_login")
            ),
            "email_notification": notification,
        },
    )


def generate_parent_temporary_password():
    return f"Parent-{get_random_string(8)}-9"


def add_onboarding_email_message(
    request,
    notification,
    recipient_email,
    missing_message,
    sent_message,
    failed_message,
):
    if notification is None or not recipient_email:
        messages.warning(
            request,
            missing_message,
        )
    elif notification.status == "sent":
        messages.success(
            request,
            sent_message,
        )
    else:
        messages.warning(
            request,
            failed_message,
        )


@admin_required
def admin_class_list(request):
    classes = (
        TeachingClass.objects.select_related("staff")
        .annotate(student_count=Count("students"))
        .order_by("name")
    )

    return render(
        request,
        "admin_portal/class_list.html",
        {
            "classes": classes,
        },
    )


@admin_required
def admin_class_create(request):
    form = TeachingClassAdminForm()

    if request.method == "POST":
        form = TeachingClassAdminForm(request.POST)

        if form.is_valid():
            teaching_class = form.save()
            messages.success(
                request,
                f"{teaching_class.name} was created.",
            )
            return redirect("school_admin:class_list")

    return render(
        request,
        "admin_portal/class_form.html",
        {
            "form": form,
            "title": "Create Class",
            "button_label": "Save Class",
        },
    )


@admin_required
def admin_class_edit(request, class_id):
    teaching_class = get_object_or_404(
        TeachingClass,
        pk=class_id,
    )
    form = TeachingClassAdminForm(instance=teaching_class)

    if request.method == "POST":
        form = TeachingClassAdminForm(
            request.POST,
            instance=teaching_class,
        )

        if form.is_valid():
            teaching_class = form.save()
            messages.success(
                request,
                f"{teaching_class.name} was updated.",
            )
            return redirect("school_admin:class_list")

    return render(
        request,
        "admin_portal/class_form.html",
        {
            "form": form,
            "title": "Edit Class",
            "button_label": "Update Class",
        },
    )


@admin_required
def admin_student_list(request):
    search = request.GET.get("search", "").strip()
    class_id = request.GET.get("class", "").strip()
    students = Student.objects.select_related("teaching_class").order_by(
        "first_name",
        "last_name",
    )

    if search:
        students = students.filter(
            Q(student_id__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(parent_name__icontains=search)
        )

    if class_id:
        students = students.filter(teaching_class_id=class_id)

    classes = TeachingClass.objects.filter(is_active=True).order_by("name")

    return render(
        request,
        "admin_portal/student_list.html",
        {
            "students": students,
            "classes": classes,
            "search": search,
            "class_id": class_id,
        },
    )


@admin_required
def admin_student_assign_class(request, student_id):
    student = get_object_or_404(
        Student.objects.select_related("teaching_class"),
        pk=student_id,
    )
    form = StudentClassAssignmentForm(instance=student)

    if request.method == "POST":
        form = StudentClassAssignmentForm(
            request.POST,
            instance=student,
        )

        if form.is_valid():
            student = form.save()
            StudentParent.objects.filter(student=student).update(
                teaching_class=student.teaching_class,
            )
            messages.success(
                request,
                f"{student.full_name} was assigned successfully.",
            )
            return redirect("school_admin:student_list")

    return render(
        request,
        "admin_portal/student_assign_class.html",
        {
            "form": form,
            "student": student,
        },
    )
