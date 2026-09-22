from datetime import date, time

from django.core.management.base import BaseCommand

from teencamp.models import Batch


class Command(BaseCommand):
    help = "Create default CodeCamp batches."

    def handle(self, *args, **options):

        batches = [

            {
                "code": "P-MWF-AM",
                "name": "Morning Batch A",
                "mode": "PHYSICAL",
                "priority": 1,
                "capacity": 30,
                "class_days": "Monday, Wednesday & Friday",
                "reporting_time": time(9, 0),
            },

            {
                "code": "P-TTS-AM",
                "name": "Morning Batch B",
                "mode": "PHYSICAL",
                "priority": 2,
                "capacity": 30,
                "class_days": "Tuesday, Thursday & Saturday",
                "reporting_time": time(9, 0),
            },

            {
                "code": "P-MWF-PM",
                "name": "Afternoon Batch A",
                "mode": "PHYSICAL",
                "priority": 3,
                "capacity": 30,
                "class_days": "Monday, Wednesday & Friday",
                "reporting_time": time(13, 0),
            },

            {
                "code": "P-TTS-PM",
                "name": "Afternoon Batch B",
                "mode": "PHYSICAL",
                "priority": 4,
                "capacity": 30,
                "class_days": "Tuesday, Thursday & Saturday",
                "reporting_time": time(13, 0),
            },

            {
                "code": "V-ONLINE",
                "name": "Virtual Batch",
                "mode": "VIRTUAL",
                "priority": 100,
                "capacity": 500,
                "class_days": "Online",
                "reporting_time": time(9, 0),
            },

        ]

        year = date.today().year

        for batch in batches:

            Batch.objects.update_or_create(

                code=batch["code"],
                camp_year=year,

                defaults={

                    "name": batch["name"],
                    "mode": batch["mode"],
                    "priority": batch["priority"],
                    "capacity": batch["capacity"],
                    "class_days": batch["class_days"],
                    "reporting_time": batch["reporting_time"],
                    "start_date": date(year, 8, 3),
                    "end_date": date(year, 9, 12),
                    "accept_new_registrations": True,
                    "is_active": True,

                }
            )

            self.stdout.write(

                self.style.SUCCESS(
                    f"Created {batch['name']}"
                )

            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Batch seeding completed successfully."
            )
        )