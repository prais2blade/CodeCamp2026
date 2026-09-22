from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Payment

def send_payment_reminders():
    today = timezone.now().date()
    reminders_sent = 0
    for p in Payment.objects.filter(status__in=['pending', 'partial']).select_related('student', 'course'):
        # Rough 30-day window check (monthly reminder)
        last_payment = p.payment_date.date()
        days_since = (today - last_payment).days
        if days_since >= 25 and p.student.email and p.course:  # Send 5 days before next cycle
            send_mail(
                subject="Payment Reminder – CodeCamp Core",
                message=f"Hi {p.student.username}, your next payment of ₦{p.monthly_payment} "
                        f"is due soon for {p.course.name}. Please pay by the end of the week.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[p.student.email],
                fail_silently=True,
            )
            reminders_sent += 1

    return reminders_sent
