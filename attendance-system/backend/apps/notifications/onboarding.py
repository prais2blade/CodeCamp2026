from django.conf import settings
from django.urls import reverse

from apps.settings_app.models import SystemSettings

from .services import create_notification


def send_parent_onboarding_email(parent, temporary_password, student=None, base_url=None):
    if not parent.email or not parent.receive_email:
        return None

    organization_name = get_organization_name()
    login_url = build_url("parent_template_login", base_url)
    dashboard_url = build_url("parent_template_dashboard", base_url)
    password_url = build_url("parent_template_password", base_url)
    child_line = ""

    if student:
        child_line = f"\nChild: {student.full_name} ({student.student_id})\n"

    message = (
        f"Hello {parent.full_name},\n\n"
        f"Your {organization_name} parent portal account is ready.\n"
        f"{child_line}"
        f"Login link: {login_url}\n"
        f"Dashboard link: {dashboard_url}\n"
        f"Phone number: {parent.phone_number}\n"
        f"Temporary password: {temporary_password}\n\n"
        f"You will be asked to change this password after login.\n"
        f"Password page: {password_url}\n\n"
        "If you did not expect this email, please contact the school admin."
    )

    return create_notification(
        recipient=parent.email,
        channel="email",
        subject=f"{organization_name} Parent Portal Login Details",
        message=message,
    )


def send_staff_onboarding_email(staff_user, temporary_password, base_url=None):
    if not staff_user.email:
        return None

    organization_name = get_organization_name()
    login_url = build_url("staff_login", base_url)
    dashboard_url = build_url("staff_dashboard", base_url)
    password_url = build_url("staff_change_password", base_url)

    display_name = staff_user.get_full_name() or staff_user.username
    message = (
        f"Hello {display_name},\n\n"
        f"Your {organization_name} staff portal account is ready.\n\n"
        f"Login link: {login_url}\n"
        f"Dashboard link: {dashboard_url}\n"
        f"Username: {staff_user.username}\n"
        f"Temporary password: {temporary_password}\n\n"
        f"You must change this password before using the staff dashboard.\n"
        f"Password page: {password_url}\n\n"
        "If you did not expect this email, please contact the school admin."
    )

    return create_notification(
        recipient=staff_user.email,
        channel="email",
        subject=f"{organization_name} Staff Portal Login Details",
        message=message,
    )


def send_foundation_onboarding_email(foundation, temporary_password, base_url=None):
    if not foundation.email:
        return None

    organization_name = get_organization_name()
    login_url = build_url("foundation_login", base_url)
    dashboard_url = build_url("foundation_dashboard", base_url)
    password_url = build_url("foundation_change_password", base_url)

    recipient_name = foundation.contact_person or foundation.name
    message = (
        f"Hello {recipient_name},\n\n"
        f"Your {organization_name} foundation sponsor portal account is ready.\n\n"
        f"Login link: {login_url}\n"
        f"Dashboard link: {dashboard_url}\n"
        f"Email: {foundation.email}\n"
        f"Temporary password: {temporary_password}\n\n"
        f"You must change this password before using the sponsor dashboard.\n"
        f"Password page: {password_url}\n\n"
        "This portal shows only students assigned to your foundation."
    )

    return create_notification(
        recipient=foundation.email,
        channel="email",
        subject=f"{organization_name} Foundation Portal Login Details",
        message=message,
    )


def build_url(route_name, base_url=None):
    path = reverse(route_name)
    base = (base_url or settings.PUBLIC_BASE_URL or "").rstrip("/")

    if not base:
        return path

    return f"{base}{path}"


def get_organization_name():
    settings_obj = SystemSettings.objects.first()

    if settings_obj and settings_obj.organization_name:
        return settings_obj.organization_name

    return "CodeCamp Attendance System"
