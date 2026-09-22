# competition/management/commands/new_edition.py
from django.core.management.base import BaseCommand
from apps.competition.models import CompetitionEdition


class Command(BaseCommand):
    help = "Create a new competition edition, optionally cloning settings from the latest one."

    def add_arguments(self, parser):
        parser.add_argument('year', type=int, help='New edition year (e.g. 2026)')

    def handle(self, *args, **options):
        year = options['year']
        if CompetitionEdition.objects.filter(year=year).exists():
            self.stdout.write(self.style.ERROR(f"Edition {year} already exists."))
            return

        latest = CompetitionEdition.objects.order_by('-year').first()
        if latest:
            new_edition = CompetitionEdition.objects.create(
                year=year,
                name=f"CRACKdaCODE {year}",
                is_active=False,
                start_date=None,
                end_date=None,
                min_team_size=latest.min_team_size,
                max_team_size=latest.max_team_size,
                schedule_markdown=latest.schedule_markdown,
                rules_markdown=latest.rules_markdown,
                prizes_markdown=latest.prizes_markdown,
                reminder_subject=latest.reminder_subject,
                reminder_body=latest.reminder_body,
            )
        else:
            new_edition = CompetitionEdition.objects.create(
                year=year,
                name=f"CRACKdaCODE {year}",
                is_active=False,
            )

        self.stdout.write(self.style.SUCCESS(f"Created edition: {new_edition}"))
