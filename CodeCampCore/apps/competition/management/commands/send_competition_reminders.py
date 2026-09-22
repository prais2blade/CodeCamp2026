# competition/management/commands/send_competition_reminders.py
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings

from apps.competition.models import CompetitionEdition, CompetitionParticipant


class Command(BaseCommand):
    help = "Send reminder emails to all participants of a specific edition (or active edition)."

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, help='Edition year (e.g. 2025)')

    def handle(self, *args, **options):
        year = options.get('year')
        if year:
            edition = CompetitionEdition.objects.filter(year=year).first()
        else:
            edition = CompetitionEdition.objects.filter(is_active=True).order_by('-year').first()

        if not edition:
            self.stdout.write(self.style.ERROR("No matching edition found."))
            return

        subject = edition.reminder_subject or f"Reminder: {edition.name}"
        body_template = edition.reminder_body or (
            "Hi {full_name},\n\n"
            "This is a reminder about the upcoming CRACKdaCODE competition."
        )

        participants = CompetitionParticipant.objects.filter(edition=edition)
        count = 0
        for p in participants:
            if p.email:
                body = body_template.format(full_name=p.full_name)
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=settings.EMAIL_HOST_USER or "no-reply@example.com",
                    recipient_list=[p.email],
                    fail_silently=True,
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f"Reminders sent: {count} (edition {edition.year})"))
