from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Staff Profile",
            {
                "fields": (
                    "role",
                    "phone_number",
                    "staff_must_change_password",
                ),
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Staff Profile",
            {
                "fields": (
                    "role",
                    "phone_number",
                    "staff_must_change_password",
                ),
            },
        ),
    )
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "staff_must_change_password",
        "is_staff",
        "is_active",
    )
    list_filter = (
        "role",
        "staff_must_change_password",
        "is_staff",
        "is_superuser",
        "is_active",
    )
