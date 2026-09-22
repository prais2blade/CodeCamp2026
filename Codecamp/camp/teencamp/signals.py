# camp/signals.py
from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import CodingCampRegistration


@receiver(post_save, sender=CodingCampRegistration)
def notify_on_verification(sender, instance, created, **kwargs):
    if created or not instance.payment_verified:
        # Only care when it flips from False ➜ True
        return
    subject = "Your CodeCamp seat is confirmed!"
    body = (
        f"Hi {instance.full_name},\n\n"
        "We've verified your payment receipt. "
        "Your seat for CodeCamp Teens is now confirmed. "
        "See you on Monday 3 August!\n\n"
        "CodeCamp Team"
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [instance.parent_email], fail_silently=True)

@receiver(post_save, sender=CodingCampRegistration)
def broadcast_dashboard_update(sender, instance, created, **kw):
    if not created and not kw.get("update_dashboard", True):
        return
    regs = CodingCampRegistration.objects
    payload = {
        "total": regs.count(),
        "verified": regs.filter(payment_verified=True).count(),
    }
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "dashboard",
        {"type": "dashboard.update", "data": payload}
    )