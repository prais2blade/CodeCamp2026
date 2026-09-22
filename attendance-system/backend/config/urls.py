
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # HTML pages
    path("school-admin/", include("apps.students.admin_portal_urls")),
    path("students/", include("apps.students.urls")),
    path("parent/", include("apps.students.parent_template_urls")),
    path("staff/", include("apps.students.staff_urls")),
    path("foundation/", include("apps.students.foundation_urls")),

    # Attendance APIs
    path("api/attendance/", include("apps.attendance.urls")),

    # Student + Parent APIs
    path("api/", include("apps.students.api_urls")),

    # Reports
    path("api/reports/", include("apps.reports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
