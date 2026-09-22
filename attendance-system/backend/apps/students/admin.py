from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Announcement,
    Assignment,
    Foundation,
    Parent,
    PerformanceRecord,
    Student,
    StudentFoundation,
    StudentParent,
    TeachingClass,
)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    def qr_preview(self, obj):

        if obj.qr_code:

            return format_html(
                '<img src="{}" width="100" />',
                obj.qr_code.url
            )

        return "-"

    qr_preview.short_description = "QR Code"
    
    readonly_fields = (
        "qr_preview",
    )

    list_display = (
        "student_id",
        "first_name",
        "last_name",
        "teaching_class",
        "is_active",
    )
    list_filter = (
        "teaching_class",
        "is_active",
    )
    search_fields = (
        "student_id",
        "first_name",
        "last_name",
        "parent_name",
    )


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "target",
        "teaching_class",
        "class_name",
        "publish_at",
        "expires_at",
        "is_active",
    )

    list_filter = (
        "target",
        "teaching_class",
        "is_active",
        "publish_at",
    )

    search_fields = (
        "title",
        "message",
        "class_name",
    )

    ordering = (
        "-publish_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (

        (
            "Announcement",
            {
                "fields": (
                    "title",
                    "message",
                ),
            },
        ),

        (
            "Audience",
            {
                "fields": (
                    "target",
                    "teaching_class",
                    "class_name",
                ),
            },
        ),

        (
            "Attachment",
            {
                "fields": (
                    "attachment",
                ),
            },
        ),

        (
            "Publication",
            {
                "fields": (
                    "is_active",
                    "publish_at",
                    "expires_at",
                ),
            },
        ),

        (
            "Audit",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                ),
            },
        ),

    )

    actions = (
        "activate_announcements",
        "deactivate_announcements",
    )

    @admin.action(
        description="Activate selected announcements"
    )
    def activate_announcements(
        self,
        request,
        queryset,
    ):
        queryset.update(
            is_active=True,
        )

    @admin.action(
        description="Deactivate selected announcements"
    )
    def deactivate_announcements(
        self,
        request,
        queryset,
    ):
        queryset.update(
            is_active=False,
        )

@admin.register(TeachingClass)
class TeachingClassAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "staff",
        "is_active",
    )
    list_filter = (
        "staff",
        "is_active",
    )
    search_fields = (
        "name",
        "staff__username",
        "staff__first_name",
        "staff__last_name",
    )


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "teaching_class",
        "due_date",
        "created_by",
        "is_active",
        "created_at",
    )
    list_filter = (
        "teaching_class",
        "is_active",
        "created_at",
    )
    search_fields = (
        "title",
        "description",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(Foundation)
class FoundationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "contact_person",
        "email",
        "is_active",
    )
    list_filter = (
        "is_active",
        "must_change_password",
    )
    search_fields = (
        "name",
        "contact_person",
        "email",
        "phone_number",
    )
    readonly_fields = (
        "last_login_at",
        "last_password_change",
        "created_at",
        "updated_at",
    )


@admin.register(StudentFoundation)
class StudentFoundationAdmin(admin.ModelAdmin):
    list_display = (
        "foundation",
        "student",
        "is_active",
        "start_date",
        "end_date",
    )
    list_filter = (
        "foundation",
        "is_active",
    )
    search_fields = (
        "foundation__name",
        "student__student_id",
        "student__first_name",
        "student__last_name",
    )


@admin.register(PerformanceRecord)
class PerformanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "title",
        "subject",
        "score",
        "max_score",
        "grade",
        "visible_to_foundations",
        "recorded_at",
    )
    list_filter = (
        "visible_to_foundations",
        "teaching_class",
        "recorded_at",
    )
    search_fields = (
        "student__student_id",
        "student__first_name",
        "student__last_name",
        "title",
        "subject",
        "term",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "phone_number",
        "email",
        "is_active",
    )
    search_fields = (
        "full_name",
        "phone_number",
        "email",
    )


@admin.register(StudentParent)
class StudentParentAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "parent",
        "relationship",
        "teaching_class",
    )
    list_filter = (
        "relationship",
        "teaching_class",
    )
    search_fields = (
        "student__student_id",
        "student__first_name",
        "student__last_name",
        "parent__full_name",
        "parent__phone_number",
    )
