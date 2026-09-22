from django.contrib import admin
from .models import Tenant, TenantDomain, TenantAPIKey


class TenantDomainInline(admin.TabularInline):
    model = TenantDomain
    extra = 1


class TenantAPIKeyInline(admin.TabularInline):
    model = TenantAPIKey
    extra = 1
    readonly_fields = ('created_at', 'last_used_at')


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'subscription_tier', 'is_active', 'is_default', 'created_at')
    list_filter = ('is_active', 'is_default', 'subscription_tier')
    search_fields = ('name', 'slug', 'contact_email', 'contact_name')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [TenantDomainInline, TenantAPIKeyInline]


@admin.register(TenantDomain)
class TenantDomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'tenant', 'is_primary', 'created_at')
    list_filter = ('is_primary',)
    search_fields = ('domain', 'tenant__name')


@admin.register(TenantAPIKey)
class TenantAPIKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'key', 'is_active', 'last_used_at', 'created_at')
    list_filter = ('is_active', 'tenant')
    search_fields = ('name', 'key', 'tenant__name')
