from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class NotificationLog(models.Model):
    TYPE_CHOICES = [
        ('payment_reminder', 'Payment Reminder'),
        ('new_session', 'New Session Announcement'),
        ('receipt', 'Receipt'),
        ('system', 'System'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    notification_type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='other')
    subject = models.CharField(max_length=255)
    body = models.TextField(blank=True)                 # final message (text or rendered html)
    recipient = models.EmailField()                     # single recipient email
    related_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='notifications')
    related_course = models.ForeignKey('courses.Course', null=True, blank=True, on_delete=models.SET_NULL)
    related_batch = models.ForeignKey('scheduling.Batch', null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_notification_type_display()}] {self.subject} → {self.recipient}"


class NotificationAttachment(models.Model):
    log = models.ForeignKey('NotificationLog', on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='notifications/attachments/')
    filename = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename or self.file.name
