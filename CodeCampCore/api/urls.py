from django.urls import path, include

from api.accounts.enrollment_api import StudentEnrollmentSyncAPIView
from api.accounts.views import (
    RegisterAPI,
    LoginAPI,
    StudentDashboardAPI,
    TeacherDashboardAPI,
)
from api.courses.catalog_api import CourseCatalogAPIView, BatchCatalogAPIView
from apps.accounts.attendance_api import sync_attendance

from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny


@api_view(["GET"])
@permission_classes([AllowAny])
def ping_view(request):
    tenant_slug = request.tenant.slug if getattr(request, "tenant", None) else None
    return Response({"status": "ok", "tenant": tenant_slug})


app_name = "api_v1"

urlpatterns = [
    path("ping/", ping_view, name="api_ping"),
    # M2M Ingestion & Sync
    path("enrollment/sync/", StudentEnrollmentSyncAPIView.as_view(), name="enrollment_sync"),
    path("attendance/sync/", sync_attendance, name="attendance_sync"),

    # Catalogs
    path("catalog/courses/", CourseCatalogAPIView.as_view(), name="catalog_courses"),
    path("catalog/batches/", BatchCatalogAPIView.as_view(), name="catalog_batches"),

    # Auth & Dashboards
    path("accounts/register/", RegisterAPI.as_view(), name="account_register"),
    path("accounts/login/", LoginAPI.as_view(), name="account_login"),
    path("accounts/dashboard/student/", StudentDashboardAPI.as_view(), name="dashboard_student"),
    path("accounts/dashboard/teacher/", TeacherDashboardAPI.as_view(), name="dashboard_teacher"),
]
