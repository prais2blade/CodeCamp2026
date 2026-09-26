import sys
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from apps.accounts.models import Profile, SummerCertificate, Attendance
from apps.payments.models import Payment, Receipt

class Command(BaseCommand):
    help = "Checks for duplicate student accounts (by email, name, or external attendance ID) and safely merges them if requested."

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Safely merge duplicate student profiles into the primary account and remove redundant user accounts.'
        )

    def handle(self, *args, **options):
        fix_mode = options.get('fix', False)

        self.stdout.write(self.style.MIGRATE_HEADING("=== Student Duplicate Verification & Deduplication Tool ==="))

        profiles = Profile.objects.filter(role='student').select_related('user', 'course', 'batch', 'tenant')
        self.stdout.write(f"Total Student Profiles scanned: {profiles.count()}")

        # 1. Group by email (excluding generic/dummy empty)
        email_groups = defaultdict(list)
        name_groups = defaultdict(list)
        ext_id_groups = defaultdict(list)

        for p in profiles:
            u = p.user
            email_clean = (u.email or '').strip().lower()
            if email_clean and not email_clean.endswith('@student.codecamp.com.ng') and not email_clean.endswith('@summer.codecamp.org'):
                email_groups[email_clean].append(p)

            full_name = f"{u.first_name} {u.last_name}".strip().lower()
            if full_name and len(full_name) > 3:
                name_groups[full_name].append(p)

            if p.external_attendance_id:
                clean_ext = p.external_attendance_id.strip().upper()
                ext_id_groups[clean_ext].append(p)

        # Detect collisions
        duplicate_clusters = []
        seen_profile_ids = set()

        for group_dict, reason in [
            (email_groups, "Duplicate Email"),
            (name_groups, "Duplicate Full Name"),
            (ext_id_groups, "Duplicate Attendance ID")
        ]:
            for key, group in group_dict.items():
                if len(group) > 1:
                    p_ids = tuple(sorted(p.id for p in group))
                    if p_ids not in seen_profile_ids:
                        seen_profile_ids.add(p_ids)
                        duplicate_clusters.append({
                            'key': key,
                            'reason': reason,
                            'profiles': group
                        })

        if not duplicate_clusters:
            self.stdout.write(self.style.SUCCESS("[OK] No duplicate student accounts found in the database."))
            self.stdout.write(self.style.NOTICE(
                "\nNote: If you are seeing duplicate student rows in Payment Approvals (/payments/manage/) "
                "or Tuition Ledger (/payments/debtors-ledger/), this is because those tables display "
                "individual Monthly Payment Records (e.g. August 2026 vs September 2026) for each student. "
                "Filter by 'September 2026' to see each student exactly once!"
            ))
            return

        self.stdout.write(self.style.WARNING(f"\nFound {len(duplicate_clusters)} potential duplicate student cluster(s):"))
        for idx, cluster in enumerate(duplicate_clusters, 1):
            self.stdout.write(f"\nCluster #{idx}: [{cluster['reason']}] '{cluster['key']}'")
            for p in cluster['profiles']:
                payments_cnt = Payment.objects.filter(student=p.user).count()
                att_cnt = Attendance.objects.filter(student=p.user).count()
                self.stdout.write(
                    f"  - Profile ID {p.id} | User ID {p.user.id} | Username: {p.user.username} | "
                    f"Name: {p.user.get_full_name()} | Email: {p.user.email} | "
                    f"Status: {p.student_status} | Course: {p.course} | Batch: {p.batch} | "
                    f"Payments: {payments_cnt} | Attendance: {att_cnt}"
                )

        if not fix_mode:
            self.stdout.write(self.style.NOTICE(
                "\nRun with '--fix' flag (e.g., 'python manage.py check_and_deduplicate_students --fix') "
                "to automatically merge these duplicate accounts into a single primary record."
            ))
            return

        # Perform merge if --fix is set
        self.stdout.write(self.style.WARNING("\nProceeding with automated deduplication & record merging..."))
        merged_count = 0

        with transaction.atomic():
            for cluster in duplicate_clusters:
                profs = cluster['profiles']
                # Pick the primary profile: the one with payments or most recent login or earliest creation
                def profile_weight(p):
                    u = p.user
                    pay_count = Payment.objects.filter(student=u).count()
                    att_count = Attendance.objects.filter(student=u).count()
                    cert_count = SummerCertificate.objects.filter(student=u).count()
                    is_active = 1 if p.student_status == 'active' else 0
                    return (pay_count, cert_count, att_count, is_active, -p.id)

                profs_sorted = sorted(profs, key=profile_weight, reverse=True)
                primary = profs_sorted[0]
                duplicates = profs_sorted[1:]

                self.stdout.write(f"\nMerging into Primary: User #{primary.user.id} ({primary.user.username})")

                for dup in duplicates:
                    dup_user = dup.user
                    self.stdout.write(f"  -> Migrating records from User #{dup_user.id} ({dup_user.username})...")

                    # Copy any missing metadata to primary
                    if not primary.external_attendance_id and dup.external_attendance_id:
                        primary.external_attendance_id = dup.external_attendance_id
                    if not primary.phone and dup.phone:
                        primary.phone = dup.phone
                    if not primary.course and dup.course:
                        primary.course = dup.course
                    if not primary.batch and dup.batch:
                        primary.batch = dup.batch
                    primary.save()

                    # Reassign Payments
                    for p in Payment.objects.filter(student=dup_user):
                        p.student = primary.user
                        if not p.course:
                            p.course = primary.course
                        if not p.batch:
                            p.batch = primary.batch
                        p.save()

                    # Reassign Receipts
                    for r in Receipt.objects.filter(student=dup_user):
                        r.student = primary.user
                        r.save()

                    # Reassign Attendance
                    Attendance.objects.filter(student=dup_user).update(student=primary.user)

                    # Reassign Certificates
                    SummerCertificate.objects.filter(student=dup_user).update(student=primary.user)

                    # Delete duplicate profile and user
                    dup.delete()
                    dup_user.delete()
                    merged_count += 1
                    self.stdout.write(self.style.SUCCESS(f"     Successfully merged and removed duplicate #{dup_user.id}."))

        self.stdout.write(self.style.SUCCESS(f"\nDone! Successfully merged {merged_count} duplicate student account(s)."))
