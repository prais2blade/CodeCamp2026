from django.urls import path

from .staff_views import (
    staff_announcements,
    staff_assignments,
    staff_change_password,
    staff_class_detail,
    staff_dashboard,
    staff_login,
    staff_logout,
    staff_scan_attendance,
    staff_scanner,
)


urlpatterns = [
    path(
        "login/",
        staff_login,
        name="staff_login",
    ),
    path(
        "logout/",
        staff_logout,
        name="staff_logout",
    ),
    path(
        "change-password/",
        staff_change_password,
        name="staff_change_password",
    ),
    path(
        "",
        staff_dashboard,
        name="staff_dashboard",
    ),
    path(
        "classes/<int:class_id>/",
        staff_class_detail,
        name="staff_class_detail",
    ),
    path(
        "scanner/",
        staff_scanner,
        name="staff_scanner",
    ),
    path(
        "scan/",
        staff_scan_attendance,
        name="staff_scan",
    ),
    path(
        "assignments/",
        staff_assignments,
        name="staff_assignments",
    ),
    path(
        "announcements/",
        staff_announcements,
        name="staff_announcements",
    ),
]
