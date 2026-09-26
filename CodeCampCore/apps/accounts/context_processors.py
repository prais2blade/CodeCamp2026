from django.conf import settings


def system_urls(request):
    """Provides unified system URLs for cross-platform navigation."""
    return {
        'attendance_system_url': getattr(
            settings, 'ATTENDANCE_SYSTEM_URL', 'https://attendance.codecamp.com.ng'
        ),
        'core_portal_url': getattr(
            settings, 'CORE_PORTAL_URL', 'https://www.codecamp.com.ng'
        ),
    }
