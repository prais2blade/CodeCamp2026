from django.contrib import admin

from .models import Attendance, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'role',
        'course',
        'batch',
        'external_attendance_id',
        'is_verified',
        'is_approved',
        'has_paid',
    )
    list_filter = ('role', 'is_verified', 'is_approved', 'has_paid', 'course', 'batch')
    search_fields = (
        'user__username',
        'user__email',
        'phone',
        'external_attendance_id',
    )


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'subject',
        'batch',
        'date',
        'status',
        'source',
        'external_reference',
        'marked_by',
    )
    list_filter = ('status', 'source', 'date', 'subject', 'batch')
    search_fields = (
        'student__username',
        'student__email',
        'subject__name',
        'batch__name',
        'external_reference',
    )
    date_hierarchy = 'date'
