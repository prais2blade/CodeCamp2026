import secrets
from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication


class APIClientUser:
    """Represents an authenticated machine-to-machine service client."""

    is_authenticated = True
    is_active = True
    is_staff = False
    is_superuser = False

    def __init__(self, client_name="service_client"):
        self.username = client_name
        self.client_name = client_name

    def __str__(self):
        return f"APIClient({self.client_name})"


from django.utils import timezone
from apps.tenants.context import set_current_tenant


class CoreAPIKeyAuthentication(BaseAuthentication):
    """
    Authentication for trusted server-to-server requests
    coming from Codecamp (admissions) or attendance-system.
    Supports both tenant-specific API keys and master configured keys.
    """

    def authenticate(self, request):
        provided_key = self.get_api_key(request)

        if not provided_key:
            return None

        # 1. Check Tenant-specific API Keys
        try:
            from apps.tenants.models import TenantAPIKey
            tenant_key = TenantAPIKey.objects.select_related("tenant").filter(
                key=provided_key,
                is_active=True,
                tenant__is_active=True,
            ).first()

            if tenant_key:
                tenant_key.last_used_at = timezone.now()
                tenant_key.save(update_fields=["last_used_at"])
                request.tenant = tenant_key.tenant
                set_current_tenant(tenant_key.tenant)
                client_name = f"tenant_{tenant_key.tenant.slug}_{tenant_key.name}"
                return (APIClientUser(client_name=client_name), None)
        except Exception:
            pass

        # 2. Check Master Configured Keys
        configured_keys = self.get_configured_keys()
        if not configured_keys:
            raise exceptions.AuthenticationFailed("API key authentication is not configured on the server.")

        matched = any(
            secrets.compare_digest(provided_key, key)
            for key in configured_keys
        )

        if not matched:
            raise exceptions.AuthenticationFailed("Invalid API Key.")

        client_name = request.headers.get("X-Client-Name", "trusted_subsystem")
        return (APIClientUser(client_name=client_name), None)

    def get_api_key(self, request):
        header_key = request.headers.get("X-API-KEY") or request.META.get("HTTP_X_API_KEY", "")
        if header_key:
            return header_key.strip()

        auth_header = (request.headers.get("Authorization", "") or request.META.get("HTTP_AUTHORIZATION", "")).strip()
        if auth_header.lower().startswith("bearer "):
            return auth_header.split(" ", 1)[1].strip()

        return None

    def get_configured_keys(self):
        candidate_keys = [
            getattr(settings, "CORE_API_KEY", ""),
            getattr(settings, "ATTENDANCE_API_KEY", ""),
            getattr(settings, "REGISTRATION_API_KEY", ""),
        ]
        return [k for k in candidate_keys if k and len(k) >= 8]
