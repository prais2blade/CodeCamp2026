from django.urls import path
from . import views

app_name = "tenants"

urlpatterns = [
    path("dashboard/", views.tenant_admin_dashboard, name="dashboard"),
    
    # API Keys
    path("api-keys/", views.tenant_api_keys_view, name="api_keys"),
    path("api-keys/create/", views.tenant_api_key_create, name="api_key_create"),
    path("api-keys/<int:key_id>/revoke/", views.tenant_api_key_revoke, name="api_key_revoke"),

    # Domains
    path("domains/", views.tenant_domains_view, name="domains"),
    path("domains/add/", views.tenant_domain_add, name="domain_add"),
    path("domains/<int:domain_id>/delete/", views.tenant_domain_delete, name="domain_delete"),

    # Live Attendance
    path("attendance/", views.tenant_attendance_live, name="attendance_live"),

    # Settings & Subscription Upgrades
    path("settings/", views.tenant_settings_view, name="settings"),
    path("upgrade/", views.tenant_plan_upgrade, name="plan_upgrade"),
]
