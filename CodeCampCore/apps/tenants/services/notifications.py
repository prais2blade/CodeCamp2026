import json
import hmac
import hashlib
import urllib.request
import urllib.error
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


class TenantNotificationService:
    @classmethod
    def send_attendance_alert(cls, attendance):
        """
        Sends branded parent/student attendance notification and triggers outbound webhooks.
        """
        student = attendance.student
        tenant = attendance.tenant
        status = (attendance.status or 'Present').upper()
        date_str = attendance.date.strftime("%B %d, %Y") if attendance.date else str(timezone.localdate())
        time_str = attendance.check_in_time.strftime("%I:%M %p") if attendance.check_in_time else "Registered Time"

        tenant_name = tenant.name if tenant else "CodeCamp Academy"

        # Determine subject & message body
        if status == "PRESENT":
            subject = f"Safe Arrival Alert: {student.get_full_name() or student.username} is at {tenant_name}"
            body = (
                f"Dear Parent/Guardian,\n\n"
                f"This is to notify you that {student.get_full_name() or student.username} has checked in safely at {tenant_name} "
                f"today ({date_str}) at {time_str}.\n\n"
                f"Batch/Class: {attendance.batch.name if attendance.batch else 'General Cohort'}\n\n"
                f"Best regards,\n{tenant_name} Admissions & Safety Team"
            )
            event_type = "attendance.checkin"
        elif status == "ABSENT":
            subject = f"Attendance Notice: {student.get_full_name() or student.username} marked Absent ({date_str})"
            body = (
                f"Dear Parent/Guardian,\n\n"
                f"Our records indicate that {student.get_full_name() or student.username} was marked absent for scheduled classes today ({date_str}) at {tenant_name}.\n\n"
                f"If this absence was unexpected, please contact the academy coordinator immediately.\n\n"
                f"Best regards,\n{tenant_name} Admissions Team"
            )
            event_type = "attendance.absent"
        elif status == "LATE":
            subject = f"Tardiness Notice: {student.get_full_name() or student.username} checked in late ({date_str})"
            body = (
                f"Dear Parent/Guardian,\n\n"
                f"{student.get_full_name() or student.username} was checked in late at {tenant_name} today ({date_str}) at {time_str}.\n\n"
                f"Best regards,\n{tenant_name}"
            )
            event_type = "attendance.late"
        else:
            subject = f"Attendance Update: {student.get_full_name() or student.username} ({date_str})"
            body = f"Attendance status updated to {status} for {student.get_full_name() or student.username} at {tenant_name}."
            event_type = "attendance.updated"

        # 1. Send Email to Student & Parent
        recipient_emails = []
        if student.email:
            recipient_emails.append(student.email)

        # Check guardian email from profile
        profile = getattr(student, 'profile', None)
        if profile and profile.phone:
            # We can log SMS/WhatsApp dispatch payload
            pass

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'notifications@codecamp.org')
        if recipient_emails:
            try:
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=from_email,
                    recipient_list=recipient_emails,
                    fail_silently=True,
                )
            except Exception:
                pass

        # 2. Dispatch Outbound Tenant Webhooks
        payload = {
            "event": event_type,
            "timestamp": timezone.now().isoformat(),
            "tenant": {
                "id": tenant.id if tenant else None,
                "slug": tenant.slug if tenant else None,
                "name": tenant_name,
            },
            "student": {
                "id": student.id,
                "username": student.username,
                "full_name": student.get_full_name(),
                "external_id": profile.external_attendance_id if profile else None,
            },
            "attendance": {
                "id": attendance.id,
                "date": str(attendance.date),
                "status": attendance.status,
                "check_in_time": str(attendance.check_in_time) if attendance.check_in_time else None,
                "check_out_time": str(attendance.check_out_time) if attendance.check_out_time else None,
            }
        }

        if tenant:
            cls.dispatch_webhook(tenant, event_type, payload)

        return {
            "subject": subject,
            "recipients": recipient_emails,
            "event_type": event_type,
        }

    @classmethod
    def dispatch_webhook(cls, tenant, event_type, payload_dict):
        """
        Dispatches signed JSON webhook payload to all active registered endpoints for this tenant.
        """
        endpoints = tenant.webhooks.filter(is_active=True)
        if not endpoints.exists():
            return 0

        payload_bytes = json.dumps(payload_dict, default=str).encode('utf-8')
        dispatched_count = 0

        for ep in endpoints:
            # Check topic subscription
            allowed_topics = [t.strip() for t in ep.events.split(',') if t.strip()]
            is_subscribed = (
                "attendance.all" in allowed_topics
                or "all" in allowed_topics
                or event_type in allowed_topics
                or event_type.split('.')[0] + ".*" in allowed_topics
            )

            if not is_subscribed:
                continue

            # Compute HMAC SHA256 Signature
            signature = hmac.new(
                ep.secret.encode('utf-8'),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()

            req = urllib.request.Request(
                ep.target_url,
                data=payload_bytes,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'CodeCampCore-Webhook-Dispatcher/2.0',
                    'X-CodeCamp-Signature': signature,
                    'X-CodeCamp-Event': event_type,
                }
            )

            try:
                # Dispatch with a 2-second timeout so it never hangs web requests
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    if 200 <= resp.status < 300:
                        ep.last_dispatched_at = timezone.now()
                        ep.save(update_fields=['last_dispatched_at'])
                        dispatched_count += 1
            except Exception:
                # Logged or silenced for resilient async handling
                pass

        return dispatched_count
