# apps/settings_app/admin.py

from django.contrib import admin

from .models import SystemSettings


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):

    def has_add_permission(
        self,
        request
    ):
        return not SystemSettings.objects.exists()