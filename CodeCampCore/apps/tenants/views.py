from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
from django.core.paginator import Paginator

from .models import Tenant, TenantDomain, TenantAPIKey
from .services import TenantQuotaService
from apps.accounts.models import Profile, Attendance
from apps.courses.models import Course
from apps.scheduling.models import Batch


def get_active_tenant_for_user(request):
    """
    Resolves the active tenant for the requesting administrator.
    Superusers can explicitly switch tenant context via ?tenant_id= or ?switch_tenant=.
    """
    if request.user.is_superuser:
        switch_slug = request.GET.get("switch_tenant") or request.GET.get("tenant_slug")
        if switch_slug:
            tenant = Tenant.objects.filter(slug=switch_slug).first()
            if tenant:
                request.session["active_tenant_id"] = tenant.id
                return tenant

        switch_id = request.GET.get("tenant_id")
        if switch_id and str(switch_id).isdigit():
            tenant = Tenant.objects.filter(id=int(switch_id)).first()
            if tenant:
                request.session["active_tenant_id"] = tenant.id
                return tenant

        session_tenant_id = request.session.get("active_tenant_id")
        if session_tenant_id:
            tenant = Tenant.objects.filter(id=session_tenant_id).first()
            if tenant:
                return tenant

    # Check middleware resolved tenant
    if getattr(request, "tenant", None):
        return request.tenant

    # Check user's profile tenant
    if hasattr(request.user, "profile") and request.user.profile.tenant:
        return request.user.profile.tenant

    # Default fallback
    return Tenant.objects.filter(is_default=True).first() or Tenant.objects.first()


def tenant_admin_required(view_func):
    """
    Ensures the user is authenticated and authorized to manage the tenant console.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        profile = getattr(request.user, "profile", None)
        is_staff_or_admin = (
            request.user.is_superuser
            or request.user.is_staff
            or (profile and profile.role in ["admin", "hod", "staff", "instructor"])
        )
        if not is_staff_or_admin:
            messages.error(request, "You do not have administrative access to the Tenant Console.")
            return redirect("login")

        tenant = get_active_tenant_for_user(request)
        if not tenant:
            messages.warning(request, "No active Academy Tenant found. Please create or configure a tenant.")
            return redirect("admin_dashboard")

        request.active_tenant = tenant
        return view_func(request, *args, **kwargs)

    return _wrapped_view


# ---------------------------------------------------------
# 1. TENANT DASHBOARD
# ---------------------------------------------------------

@tenant_admin_required
def tenant_admin_dashboard(request):
    tenant = request.active_tenant
    today = timezone.localdate()

    # Core Metrics
    total_students = Profile.objects.filter(
        Q(tenant=tenant) | (Q(tenant__isnull=True) if tenant.is_default else Q(pk__in=[])),
        role="student",
    ).count()

    total_courses = Course.objects.filter(
        Q(tenant=tenant) | (Q(tenant__isnull=True) if tenant.is_default else Q(pk__in=[])),
        is_published=True,
    ).count()

    total_batches = Batch.objects.filter(
        Q(tenant=tenant) | (Q(tenant__isnull=True) if tenant.is_default else Q(pk__in=[])),
        is_published=True,
    ).count()

    # Attendance Metrics
    today_attendance_qs = Attendance.objects.filter(
        Q(tenant=tenant) | (Q(tenant__isnull=True) if tenant.is_default else Q(pk__in=[])),
        date=today,
    )
    today_scans = today_attendance_qs.count()
    present_today = today_attendance_qs.filter(status__iexact="Present").count()
    absent_today = today_attendance_qs.filter(status__iexact="Absent").count()
    late_today = today_attendance_qs.filter(status__iexact="Late").count()

    attendance_rate = 0
    if total_students > 0 and today_scans > 0:
        attendance_rate = round((present_today / total_students) * 100, 1)

    # Quota Usage from Quota Service
    quota_metrics = TenantQuotaService.get_usage_metrics(tenant)
    quota_limit = quota_metrics['students']['limit']
    quota_percentage = quota_metrics['students']['percentage']

    # Recent Activity Feed
    recent_attendance = (
        Attendance.objects.select_related("student", "subject", "batch")
        .filter(
            Q(tenant=tenant) | (Q(tenant__isnull=True) if tenant.is_default else Q(pk__in=[]))
        )
        .order_by("-date", "-id")[:8]
    )

    # All tenants for superusers switcher
    all_tenants = Tenant.objects.filter(is_active=True).order_by("name") if request.user.is_superuser else None

    # Active API Keys count & Domains count
    active_keys_count = TenantAPIKey.objects.filter(tenant=tenant, is_active=True).count()
    domains_count = TenantDomain.objects.filter(tenant=tenant).count()

    context = {
        "tenant": tenant,
        "all_tenants": all_tenants,
        "total_students": total_students,
        "total_courses": total_courses,
        "total_batches": total_batches,
        "today_scans": today_scans,
        "present_today": present_today,
        "absent_today": absent_today,
        "late_today": late_today,
        "attendance_rate": attendance_rate,
        "quota_limit": quota_limit,
        "quota_percentage": quota_percentage,
        "quota_metrics": quota_metrics,
        "recent_attendance": recent_attendance,
        "active_keys_count": active_keys_count,
        "domains_count": domains_count,
    }
    return render(request, "tenants/dashboard.html", context)


# ---------------------------------------------------------
# 2. API KEYS MANAGEMENT
# ---------------------------------------------------------

@tenant_admin_required
def tenant_api_keys_view(request):
    tenant = request.active_tenant
    keys = TenantAPIKey.objects.filter(tenant=tenant).order_by("-created_at")
    quota_metrics = TenantQuotaService.get_usage_metrics(tenant)

    all_tenants = Tenant.objects.filter(is_active=True).order_by("name") if request.user.is_superuser else None

    newly_created_key = request.session.pop("newly_created_key", None)
    newly_created_name = request.session.pop("newly_created_name", None)

    context = {
        "tenant": tenant,
        "all_tenants": all_tenants,
        "keys": keys,
        "quota_metrics": quota_metrics,
        "newly_created_key": newly_created_key,
        "newly_created_name": newly_created_name,
    }
    return render(request, "tenants/api_keys.html", context)


@tenant_admin_required
def tenant_api_key_create(request):
    tenant = request.active_tenant
    if request.method == "POST":
        can_create, reason = TenantQuotaService.can_create_api_key(tenant)
        if not can_create:
            messages.error(request, reason)
            return redirect("tenants:api_keys")

        name = request.POST.get("name", "").strip() or "Integration Gateway Key"
        key_obj = TenantAPIKey.objects.create(
            tenant=tenant,
            name=name,
            is_active=True,
        )
        request.session["newly_created_key"] = key_obj.key
        request.session["newly_created_name"] = key_obj.name
        messages.success(request, f"New API key '{name}' generated successfully! Please copy it now.")
    return redirect("tenants:api_keys")


@tenant_admin_required
def tenant_api_key_revoke(request, key_id):
    tenant = request.active_tenant
    if request.method == "POST":
        key_obj = get_object_or_404(TenantAPIKey, id=key_id, tenant=tenant)
        key_obj.is_active = False
        key_obj.save(update_fields=["is_active"])
        messages.warning(request, f"API key '{key_obj.name}' has been revoked.")
    return redirect("tenants:api_keys")


# ---------------------------------------------------------
# 3. DOMAINS MANAGEMENT
# ---------------------------------------------------------

@tenant_admin_required
def tenant_domains_view(request):
    tenant = request.active_tenant
    domains = TenantDomain.objects.filter(tenant=tenant).order_by("-is_primary", "domain")
    quota_metrics = TenantQuotaService.get_usage_metrics(tenant)
    all_tenants = Tenant.objects.filter(is_active=True).order_by("name") if request.user.is_superuser else None

    context = {
        "tenant": tenant,
        "all_tenants": all_tenants,
        "domains": domains,
        "quota_metrics": quota_metrics,
    }
    return render(request, "tenants/domains.html", context)


@tenant_admin_required
def tenant_domain_add(request):
    tenant = request.active_tenant
    if request.method == "POST":
        can_create, reason = TenantQuotaService.can_create_domain(tenant)
        if not can_create:
            messages.error(request, reason)
            return redirect("tenants:domains")

        domain = request.POST.get("domain", "").strip().lower()
        is_primary = request.POST.get("is_primary") == "on"

        if not domain:
            messages.error(request, "Please enter a valid domain name.")
            return redirect("tenants:domains")

        # Clean host (strip http:// or https://)
        domain = domain.replace("http://", "").replace("https://", "").split("/")[0]

        if TenantDomain.objects.filter(domain=domain).exists():
            messages.error(request, f"Domain '{domain}' is already assigned to an organization.")
            return redirect("tenants:domains")

        if is_primary:
            TenantDomain.objects.filter(tenant=tenant).update(is_primary=False)

        TenantDomain.objects.create(
            tenant=tenant,
            domain=domain,
            is_primary=is_primary,
            is_verified=True,
        )
        messages.success(request, f"Domain '{domain}' successfully added to {tenant.name}.")
    return redirect("tenants:domains")


@tenant_admin_required
def tenant_plan_upgrade(request):
    tenant = request.active_tenant
    if request.method == "POST":
        target_tier = request.POST.get("target_tier", "").lower().strip()
        tier_capacity_map = {
            "starter": 50,
            "pro": 500,
            "enterprise": 5000,
        }
        if target_tier not in tier_capacity_map:
            messages.error(request, "Invalid subscription plan selected.")
            return redirect("tenants:settings")

        tenant.subscription_tier = target_tier
        tenant.max_students = tier_capacity_map[target_tier]
        tenant.save()
        messages.success(request, f"Successfully upgraded {tenant.name} to the {target_tier.capitalize()} Plan ({tier_capacity_map[target_tier]} Student Quota)!")
    return redirect("tenants:settings")


@tenant_admin_required
def tenant_domain_delete(request, domain_id):
    tenant = request.active_tenant
    if request.method == "POST":
        domain_obj = get_object_or_404(TenantDomain, id=domain_id, tenant=tenant)
        domain_name = domain_obj.domain
        domain_obj.delete()
        messages.info(request, f"Domain '{domain_name}' removed.")
    return redirect("tenants:domains")


# ---------------------------------------------------------
# 4. LIVE ATTENDANCE STREAM
# ---------------------------------------------------------

@tenant_admin_required
def tenant_attendance_live(request):
    tenant = request.active_tenant
    all_tenants = Tenant.objects.filter(is_active=True).order_by("name") if request.user.is_superuser else None

    queryset = (
        Attendance.objects.select_related("student", "subject", "batch")
        .filter(
            Q(tenant=tenant) | (Q(tenant__isnull=True) if tenant.is_default else Q(pk__in=[]))
        )
        .order_by("-date", "-id")
    )

    # Filter by Date
    date_filter = request.GET.get("date")
    if date_filter:
        queryset = queryset.filter(date=date_filter)

    # Filter by Status
    status_filter = request.GET.get("status")
    if status_filter:
        queryset = queryset.filter(status__iexact=status_filter)

    # Search by Student Name or External ID
    search_query = request.GET.get("q", "").strip()
    if search_query:
        queryset = queryset.filter(
            Q(student__username__icontains=search_query)
            | Q(student__first_name__icontains=search_query)
            | Q(student__last_name__icontains=search_query)
            | Q(student__email__icontains=search_query)
            | Q(student__profile__external_attendance_id__icontains=search_query)
        )

    paginator = Paginator(queryset, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "tenant": tenant,
        "all_tenants": all_tenants,
        "page_obj": page_obj,
        "date_filter": date_filter or "",
        "status_filter": status_filter or "",
        "search_query": search_query,
        "total_records": queryset.count(),
    }
    return render(request, "tenants/attendance_live.html", context)


# ---------------------------------------------------------
# 5. TENANT PROFILE & SETTINGS
# ---------------------------------------------------------

@tenant_admin_required
def tenant_settings_view(request):
    tenant = request.active_tenant
    all_tenants = Tenant.objects.filter(is_active=True).order_by("name") if request.user.is_superuser else None

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        contact_email = request.POST.get("contact_email", "").strip()
        contact_phone = request.POST.get("contact_phone", "").strip()
        address = request.POST.get("address", "").strip()
        timezone_str = request.POST.get("timezone", "UTC").strip()

        if name:
            tenant.name = name
        tenant.contact_email = contact_email
        tenant.contact_phone = contact_phone
        tenant.address = address
        tenant.timezone = timezone_str
        tenant.save()

        messages.success(request, "Academy settings saved successfully.")
        return redirect("tenants:settings")

    context = {
        "tenant": tenant,
        "all_tenants": all_tenants,
    }
    return render(request, "tenants/settings.html", context)
