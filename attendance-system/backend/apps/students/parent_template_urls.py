from django.urls import path

from .parent_views import (
    parent_change_password,
    parent_child_history,
    parent_dashboard,
    parent_login,
    parent_logout,
)


urlpatterns = [
    path(
        "login/",
        parent_login,
        name="parent_template_login",
    ),
    path(
        "dashboard/",
        parent_dashboard,
        name="parent_template_dashboard",
    ),
    path(
        "logout/",
        parent_logout,
        name="parent_template_logout",
    ),
    path(
        "password/",
        parent_change_password,
        name="parent_template_password",
    ),
    path(
        "children/<int:student_id>/",
        parent_child_history,
        name="parent_template_child_history",
    ),
]
