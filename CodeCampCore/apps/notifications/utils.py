from django.utils import timezone
from django.core.mail import EmailMessage
from .models import NotificationLog

def log_notification(notification_type, subject, body, recipient, related_user=None, related_course=None, related_batch=None):
    """Create a log entry (queued)."""
    return NotificationLog.objects.create(
        notification_type=notification_type,
        subject=subject[:255],
        body=body,
        recipient=recipient,
        related_user=related_user,
        related_course=related_course,
        related_batch=related_batch,
        status='queued'
    )


def send_and_log(notification_log: NotificationLog, html=False, from_email=None):
    try:
        msg = EmailMessage(
            notification_log.subject,
            notification_log.body,
            from_email or "noreply@codecampcore.com",
            [notification_log.recipient],
        )

        if html:
            msg.content_subtype = "html"

        # Attach any related files
        for attachment in notification_log.attachments.all():
            msg.attach_file(attachment.file.path)

        msg.send(fail_silently=False)
        notification_log.status = 'sent'
        notification_log.sent_at = timezone.now()
        notification_log.error_message = ''
        notification_log.save(update_fields=['status', 'sent_at', 'error_message'])
        return True

    except Exception as exc:
        notification_log.status = 'failed'
        notification_log.error_message = str(exc)
        notification_log.save(update_fields=['status', 'error_message'])
        return False
