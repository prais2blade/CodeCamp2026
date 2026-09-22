import csv
import secrets
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.students.models import Parent, Student, StudentParent


class Command(BaseCommand):
    help = (
        "Create Parent records and StudentParent links for existing "
        "students from a CSV export."
    )

    required_columns = {
        "student_id",
        "parent_phone",
    }

    optional_columns = {
        "parent_name",
        "parent_title",
        "parent_email",
        "parent_whatsapp",
        "relationship",
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            help=(
                "CSV file with columns: student_id, parent_phone, "
                "parent_name, parent_email, parent_whatsapp, relationship."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write changes to the database. Without this, only a dry run is performed.",
        )
        parser.add_argument(
            "--password-output",
            help=(
                "CSV path where temporary passwords for newly created "
                "parents will be written. Required with --apply."
            ),
        )
        parser.add_argument(
            "--template",
            action="store_true",
            help="Print the expected CSV header and an example row.",
        )

    def handle(self, *args, **options):
        if options["template"]:
            self.print_template()
            return

        csv_path = options.get("csv_path")
        apply_changes = options["apply"]
        password_output = options.get("password_output")

        if not csv_path:
            raise CommandError("Provide --csv or use --template.")

        if apply_changes and not password_output:
            raise CommandError(
                "--password-output is required with --apply so new parent "
                "temporary passwords are not lost."
            )

        rows = self.read_rows(csv_path)

        if apply_changes:
            results = self.apply_rows(rows)
            self.write_passwords(password_output, results)
        else:
            results = self.preview_rows(rows)

        self.print_summary(results, apply_changes)

    def print_template(self):
        self.stdout.write(
            "student_id,parent_name,parent_phone,parent_email,"
            "parent_whatsapp,relationship,parent_title"
        )
        self.stdout.write(
            "CDCP-000001,Jane Doe,08012345678,jane@example.com,"
            "08012345678,Mother,Mrs"
        )

    def read_rows(self, csv_path):
        path = Path(csv_path)

        if not path.exists():
            raise CommandError(f"CSV file not found: {path}")

        with path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)

            if reader.fieldnames is None:
                raise CommandError("CSV file is empty.")

            fieldnames = {
                field.strip()
                for field in reader.fieldnames
                if field
            }
            missing = self.required_columns - fieldnames

            if missing:
                raise CommandError(
                    "CSV is missing required column(s): "
                    + ", ".join(sorted(missing))
                )

            return [
                {
                    key: (value or "").strip()
                    for key, value in row.items()
                }
                for row in reader
            ]

    def preview_rows(self, rows):
        results = []

        for row_number, row in enumerate(rows, start=2):
            result = self.prepare_row(row_number, row)
            results.append(result)

        return results

    def apply_rows(self, rows):
        results = []

        for row_number, row in enumerate(rows, start=2):
            result = self.prepare_row(row_number, row)

            if result["status"] != "ready":
                results.append(result)
                continue

            try:
                with transaction.atomic():
                    self.create_or_update_link(result)
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)

            results.append(result)

        return results

    def prepare_row(self, row_number, row):
        student_id = row.get("student_id", "")
        parent_phone = row.get("parent_phone", "")

        result = {
            "row_number": row_number,
            "student_id": student_id,
            "parent_phone": parent_phone,
            "status": "ready",
            "message": "",
            "student": None,
            "parent_name": "",
            "parent_created": False,
            "link_created": False,
            "temporary_password": "",
            "row": row,
        }

        if not student_id:
            result["status"] = "skipped"
            result["message"] = "Missing student_id."
            return result

        try:
            student = Student.objects.get(student_id=student_id)
        except Student.DoesNotExist:
            result["status"] = "skipped"
            result["message"] = "Student not found."
            return result

        parent_name = row.get("parent_name") or student.parent_name

        if not parent_phone:
            result["status"] = "skipped"
            result["message"] = "Missing parent_phone."
            return result

        if not parent_name:
            result["status"] = "skipped"
            result["message"] = "Missing parent_name and student has no parent_name."
            return result

        result["student"] = student
        result["parent_name"] = parent_name

        return result

    def create_or_update_link(self, result):
        row = result["row"]
        student = result["student"]
        temporary_password = ""

        parent = Parent.objects.filter(
            phone_number=result["parent_phone"],
        ).first()

        if parent is None:
            temporary_password = secrets.token_urlsafe(8)
            parent = Parent(
                title=row.get("parent_title", ""),
                full_name=result["parent_name"],
                phone_number=result["parent_phone"],
                whatsapp_number=row.get("parent_whatsapp", ""),
                email=row.get("parent_email", ""),
            )
            parent.set_password(temporary_password)
            parent.save()
            result["parent_created"] = True
            result["temporary_password"] = temporary_password
        else:
            updated_fields = []

            field_updates = {
                "title": row.get("parent_title", ""),
                "full_name": result["parent_name"],
                "whatsapp_number": row.get("parent_whatsapp", ""),
                "email": row.get("parent_email", ""),
            }

            for field, value in field_updates.items():
                if value and getattr(parent, field) != value:
                    setattr(parent, field, value)
                    updated_fields.append(field)

            if updated_fields:
                parent.save(update_fields=updated_fields)

        relationship = row.get("relationship") or "Guardian"

        _, link_created = StudentParent.objects.get_or_create(
            student=student,
            parent=parent,
            defaults={
                "relationship": relationship,
            },
        )

        result["link_created"] = link_created

        if student.parent_name != parent.full_name:
            student.parent_name = parent.full_name
            student.save(update_fields=["parent_name"])

    def write_passwords(self, password_output, results):
        path = Path(password_output)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=[
                    "student_id",
                    "parent_name",
                    "parent_phone",
                    "temporary_password",
                    "parent_created",
                    "link_created",
                ],
            )
            writer.writeheader()

            for result in results:
                if not result["temporary_password"]:
                    continue

                writer.writerow(
                    {
                        "student_id": result["student_id"],
                        "parent_name": result["parent_name"],
                        "parent_phone": result["parent_phone"],
                        "temporary_password": result["temporary_password"],
                        "parent_created": result["parent_created"],
                        "link_created": result["link_created"],
                    }
                )

    def print_summary(self, results, apply_changes):
        total = len(results)
        ready = sum(result["status"] == "ready" for result in results)
        skipped = sum(result["status"] == "skipped" for result in results)
        errors = sum(result["status"] == "error" for result in results)
        parents_created = sum(result["parent_created"] for result in results)
        links_created = sum(result["link_created"] for result in results)

        mode = "APPLY" if apply_changes else "DRY RUN"

        self.stdout.write(self.style.SUCCESS(f"{mode} complete."))
        self.stdout.write(f"Rows read: {total}")
        self.stdout.write(f"Ready rows: {ready}")
        self.stdout.write(f"Skipped rows: {skipped}")
        self.stdout.write(f"Errors: {errors}")
        self.stdout.write(f"Parents created: {parents_created}")
        self.stdout.write(f"Links created: {links_created}")

        for result in results:
            if result["status"] in {"skipped", "error"}:
                self.stdout.write(
                    f"Row {result['row_number']} "
                    f"({result['student_id']}): "
                    f"{result['message']}"
                )
