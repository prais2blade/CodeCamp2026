from django.utils.deprecation import MiddlewareMixin
from .context import set_current_tenant, clear_current_tenant
from .models import Tenant, TenantDomain


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware that identifies the active tenant for each request and
    injects it into `request.tenant` as well as the thread-local context.
    """

    def process_request(self, request):
        tenant = self._resolve_tenant(request)
        request.tenant = tenant
        set_current_tenant(tenant)

    def process_response(self, request, response):
        clear_current_tenant()
        if hasattr(request, "tenant") and request.tenant:
            response["X-Tenant-Slug"] = request.tenant.slug
        return response

    def process_exception(self, request, exception):
        clear_current_tenant()

    def _resolve_tenant(self, request):
        # 1. Header Resolution (API requests, Kiosks, admissions sync)
        header_tenant_slug = (
            request.headers.get("X-Tenant-Slug")
            or request.headers.get("X-Tenant-ID")
            or request.META.get("HTTP_X_TENANT_SLUG")
            or request.META.get("HTTP_X_TENANT_ID")
        )
        if header_tenant_slug:
            slug = str(header_tenant_slug).strip().lower()
            tenant = Tenant.objects.filter(slug__iexact=slug, is_active=True).first()
            if not tenant and slug.isdigit():
                tenant = Tenant.objects.filter(id=int(slug), is_active=True).first()
            if tenant:
                return tenant

        # 2. Hostname & Subdomain Resolution
        host = request.get_host().split(":")[0].lower()
        if host:
            domain_obj = TenantDomain.objects.select_related("tenant").filter(
                domain__iexact=host,
                tenant__is_active=True
            ).first()
            if domain_obj:
                return domain_obj.tenant

            # Subdomain check (e.g. lagos.localhost or lagos.codecamp.org)
            parts = host.split(".")
            if len(parts) >= 2:
                subdomain = parts[0]
                if subdomain not in ("www", "api", "app", "localhost", "127"):
                    tenant = Tenant.objects.filter(
                        slug__iexact=subdomain,
                        is_active=True
                    ).first()
                    if tenant:
                        return tenant

        # 3. Authenticated User Profile Tenant
        if getattr(request, "user", None) and request.user.is_authenticated:
            profile = getattr(request.user, "profile", None)
            if profile and getattr(profile, "tenant", None):
                return profile.tenant

        # 4. Fallback Default Tenant (Ensures existing endpoints work transparently)
        default_tenant = Tenant.objects.filter(is_default=True, is_active=True).first()
        if not default_tenant:
            default_tenant = Tenant.objects.filter(is_active=True).first()

        return default_tenant
