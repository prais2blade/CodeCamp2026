from django.core.management.base import BaseCommand
from django.db.models import Q
from apps.accounts.models import Profile, SummerCertificate
from apps.courses.models import Course
from apps.scheduling.models import Batch


class Command(BaseCommand):
    help = "Transition summer camp students to 'summer_alumni' (inactive) until they re-register and pay for the main term."

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch',
            type=str,
            help='Specific batch/cohort name or ID to target (e.g. "Summer")'
        )
        parser.add_argument(
            '--course',
            type=str,
            help='Specific course name or ID to target'
        )
        parser.add_argument(
            '--all-summer',
            action='store_true',
            help='Target all students in batches/courses with "Summer" or "Bootcamp" in their title'
        )
        parser.add_argument(
            '--auto-certificates',
            action='store_true',
            help='Automatically initialize a Summer Certificate record for each transitioned student'
        )

    def handle(self, *args, **options):
        profiles = Profile.objects.filter(role='student')

        batch_arg = options.get('batch')
        course_arg = options.get('course')
        all_summer = options.get('all_summer')
        auto_certificates = options.get('auto_certificates')

        if batch_arg:
            profiles = profiles.filter(Q(batch__name__icontains=batch_arg) | Q(batch__id__iexact=batch_arg))
        elif course_arg:
            profiles = profiles.filter(Q(course__name__icontains=course_arg) | Q(course__id__iexact=course_arg))
        elif all_summer:
            profiles = profiles.filter(
                Q(batch__name__icontains='Summer') |
                Q(course__name__icontains='Summer') |
                Q(batch__name__icontains='Bootcamp') |
                Q(course__name__icontains='Bootcamp')
            )
        else:
            # Default to all students if no specific filter
            self.stdout.write(self.style.WARNING("No specific filter passed. Targetting students who have not yet transitioned..."))
            profiles = profiles.filter(student_status='active')

        count = 0
        cert_count = 0
        for profile in profiles:
            profile.student_status = 'summer_alumni'
            profile.has_paid = False
            profile.save(update_fields=['student_status', 'has_paid'])
            count += 1

            if auto_certificates:
                cert, created = SummerCertificate.objects.get_or_create(
                    student=profile.user,
                    defaults={
                        'course': profile.course,
                        'title': f"Certificate of Completion - {profile.course.name if profile.course else 'Summer CodeCamp'}",
                        'remarks': 'Successfully completed the intensive 2026 Summer Coding & Technology Camp.'
                    }
                )
                if created:
                    cert_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully transitioned {count} student(s) to 'summer_alumni' status!"
        ))
        if auto_certificates:
            self.stdout.write(self.style.SUCCESS(
                f"Generated {cert_count} initial Summer Certificate records."
            ))
