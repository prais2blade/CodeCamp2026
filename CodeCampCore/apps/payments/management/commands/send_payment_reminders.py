from django.core.management.base import BaseCommand

from apps.payments.tasks import send_payment_reminders


class Command(BaseCommand):
    help = "Send reminder emails for pending or partially paid student payments."

    def handle(self, *args, **options):
        reminders_sent = send_payment_reminders()
        self.stdout.write(
            self.style.SUCCESS(f"Payment reminders sent: {reminders_sent}")
        )
