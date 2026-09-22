from django.contrib import admin
from .models import NotificationLog, NotificationAttachment


class NotificationAttachmentInline(admin.TabularInline):
    model = NotificationAttachment
    extra = 1


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    inlines = [NotificationAttachmentInline]

    list_display = (
        'notification_type',
        'subject',
        'recipient',
        'status',
        'created_at',
        'sent_at',
    )

    list_filter = ('notification_type', 'status', 'created_at')

    search_fields = ('subject', 'recipient', 'body', 'error_message')

    readonly_fields = ('created_at', 'sent_at')

    ordering = ('-created_at',)
