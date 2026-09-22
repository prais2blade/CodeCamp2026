from django.core.management.base import BaseCommand

from apps.students.models import Student
from apps.students.qr_utils import (
    ensure_student_qr_code,
    regenerate_student_qr_code,
)


class Command(BaseCommand):
    help = "Regenerate student QR code images."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Regenerate QR codes for all students, not only missing files.",
        )
        parser.add_argument(
            "--student-id",
            help="Regenerate the QR code for one student ID.",
        )

    def handle(self, *args, **options):
        queryset = Student.objects.all().order_by("id")

        if options["student_id"]:
            queryset = queryset.filter(
                student_id=options["student_id"],
            )

        checked_count = 0
        regenerated_count = 0

        for student in queryset:
            checked_count += 1

            if options["all"]:
                regenerate_student_qr_code(student)
                regenerated_count += 1
            elif ensure_student_qr_code(student):
                regenerated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Checked {checked_count} student(s). "
                    f"Regenerated {regenerated_count} QR code(s)."
                )
            )
        )
