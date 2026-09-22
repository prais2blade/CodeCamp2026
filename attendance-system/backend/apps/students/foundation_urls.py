from django.urls import path

from .foundation_views import (
    foundation_change_password,
    foundation_dashboard,
    foundation_login,
    foundation_logout,
    foundation_student_detail,
)


urlpatterns = [
    path(
        "login/",
        foundation_login,
        name="foundation_login",
    ),
    path(
        "logout/",
        foundation_logout,
        name="foundation_logout",
    ),
    path(
        "password/",
        foundation_change_password,
        name="foundation_change_password",
    ),
    path(
        "",
        foundation_dashboard,
        name="foundation_dashboard",
    ),
    path(
        "students/<int:student_id>/",
        foundation_student_detail,
        name="foundation_student_detail",
    ),
]
