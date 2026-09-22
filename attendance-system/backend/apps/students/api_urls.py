from django.urls import path

from apps.students.integration_views import RegisterStudentAPIView
from .api.parent_auth import (
    ParentLoginAPIView,
)

from .api.parent_profile import (
    ParentProfileAPIView,
)

from .api.parent_dashboard import (
    ParentDashboardAPIView,
)

from .api.parent_history import (
    ParentStudentHistoryAPIView,
)

from .api.student_api import (
    student_list_api,
    student_detail_api,
)

urlpatterns = [
    # Student APIs
    path("students/", student_list_api, name="student_list_api"),
    path("students/<str:student_id>/", student_detail_api, name="student_detail_api"),

    # Parent APIs
    path("parent/login/", ParentLoginAPIView.as_view(), name="parent_login"),
    path("parent/dashboard/", ParentDashboardAPIView.as_view(), name="parent_dashboard"),
    path(
        "parent/student/<int:student_id>/history/",
        ParentStudentHistoryAPIView.as_view(),
        name="parent_student_history",
    ),
    path(
    "parent/profile/",
    ParentProfileAPIView.as_view(),
    name="parent_profile",
),
    
    path(
        "integration/register-student/",
        RegisterStudentAPIView.as_view(),
        name="integration_register_student",
    ),
]