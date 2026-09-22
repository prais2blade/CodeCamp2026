from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.accounts.attendance_api import sync_attendance
from .views import health_check

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health_check'),
    path('api/v1/', include('api.urls')),
    path('integrations/attendance/', sync_attendance, name='attendance_sync'),
    path('account/', include('apps.accounts.urls')),
    path('courses/', include('apps.courses.urls')),
    path('scheduling/', include('apps.scheduling.urls')),
    path('payments/', include('apps.payments.urls')),
    path('mailing/', include('apps.mailing.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('', include('apps.website.urls')),
    path('blog/', include('apps.blog.urls')),
    path('competition/', include('apps.competition.urls', namespace='competition')),
    path('tasks/', include('apps.tasks.urls')),
    path('tenants/', include('apps.tenants.urls', namespace='tenants')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
