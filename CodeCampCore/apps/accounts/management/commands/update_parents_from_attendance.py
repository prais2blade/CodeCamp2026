import os
import sqlite3
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import Profile, Parent
from apps.accounts.services.attendance_sync_service import AttendanceSyncService


class Command(BaseCommand):
    help = "Imports and updates parents/guardians from the Attendance System into CodeCampCore."

    def add_arguments(self, parser):
        parser.add_argument(
            "--attendance-db",
            type=str,
            default=None,
            help="Path to attendance system SQLite database (auto-detected if omitted)",
        )
        parser.add_argument(
            "--pg-dbname",
            type=str,
            default="attendance_db",
            help="PostgreSQL database name for attendance system (default: attendance_db)",
        )
        parser.add_argument(
            "--pg-user",
            type=str,
            default="attendance_user",
            help="PostgreSQL user for attendance system (default: attendance_user)",
        )
        parser.add_argument(
            "--pg-password",
            type=str,
            default="JetZ@t_2026",
            help="PostgreSQL password for attendance system",
        )
        parser.add_argument(
            "--pg-host",
            type=str,
            default="localhost",
            help="PostgreSQL host for attendance system (default: localhost)",
        )
        parser.add_argument(
            "--pg-port",
            type=int,
            default=5432,
            help="PostgreSQL port for attendance system (default: 5432)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the parent update without saving changes",
        )

    def _try_sqlite(self, path):
        if not path or not os.path.exists(path):
            return None, 0
        try:
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM students_student")
            count = cur.fetchone()[0]
            if count > 0:
                return conn, count
            conn.close()
        except Exception:
            pass
        return None, 0

    def _try_postgres(self, dbname, user, password, host, port):
        # Try psycopg (v3)
        try:
            import psycopg
            from psycopg.rows import dict_row
            conn = psycopg.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port,
                row_factory=dict_row
            )
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM students_student")
            row = cur.fetchone()
            count = list(row.values())[0] if isinstance(row, dict) else row[0]
            if count > 0:
                return conn, "psycopg", count
            conn.close()
        except Exception:
            pass

        # Try psycopg2 (v2)
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            conn = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port,
                cursor_factory=RealDictCursor
            )
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM students_student")
            row = cur.fetchone()
            count = list(row.values())[0] if isinstance(row, dict) else row[0]
            if count > 0:
                return conn, "psycopg2", count
            conn.close()
        except Exception:
            pass

        return None, None, 0

    def handle(self, *args, **options):
        custom_db_path = options.get("attendance_db")
        dry_run = options.get("dry_run", False)
        pg_dbname = options.get("pg_dbname", "attendance_db")
        pg_user = options.get("pg_user", "attendance_user")
        pg_password = options.get("pg_password", "JetZ@t_2026")
        pg_host = options.get("pg_host", "localhost")
        pg_port = options.get("pg_port", 5432)

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== Attendance System Parent Synchronization ({'DRY RUN' if dry_run else 'LIVE TRANSACTION'}) ==="
        ))

        db_conn = None
        db_description = None

        # 1. Custom path
        if custom_db_path:
            c, count = self._try_sqlite(custom_db_path)
            if c:
                db_conn = c
                db_description = f"Custom SQLite ({custom_db_path}) with {count} students"

        # 2. Candidate paths
        if not db_conn:
            candidates = [
                "/var/www/codecamp2026/attendance-system/backend/db.sqlite3",
                "/var/www/attendance-system/backend/db.sqlite3",
                "/var/www/attendance/backend/db.sqlite3",
                "/var/www/attendance-system/db.sqlite3",
                "/var/www/codecamp/attendance-system/backend/db.sqlite3",
                r"c:\Projects\attendance-system\backend\db.sqlite3",
                r"c:\Projects\codecamp2026\attendance-system\backend\db.sqlite3",
                "attendance-system/backend/db.sqlite3",
                "../attendance-system/backend/db.sqlite3",
            ]
            for path in candidates:
                c, count = self._try_sqlite(path)
                if c:
                    db_conn = c
                    db_description = f"SQLite ({os.path.abspath(path)}) with {count} students"
                    break

        # 3. PostgreSQL
        if not db_conn:
            pg_conn, pg_driver, count = self._try_postgres(pg_dbname, pg_user, pg_password, pg_host, pg_port)
            if pg_conn:
                db_conn = pg_conn
                db_description = f"PostgreSQL {pg_dbname} on {pg_host}:{pg_port} ({pg_driver}) with {count} students"

        # 4. PostgreSQL peer socket
        if not db_conn:
            pg_conn, pg_driver, count = self._try_postgres(pg_dbname, "postgres", "", "localhost", pg_port)
            if pg_conn:
                db_conn = pg_conn
                db_description = f"PostgreSQL {pg_dbname} as postgres user with {count} students"

        if not db_conn:
            self.stderr.write(self.style.ERROR(
                "[ERROR] Could not connect to Attendance database!\n"
                "Checked local/VPS SQLite candidate paths and PostgreSQL attendance_db.\n"
                "Use --attendance-db <path> or --pg-host / --pg-dbname to specify connection."
            ))
            return

        self.stdout.write(self.style.SUCCESS(f"[OK] Connected to Attendance Source: {db_description}"))

        if dry_run:
            with transaction.atomic():
                res = AttendanceSyncService.sync_parents(connection=db_conn)
                transaction.set_rollback(True)
        else:
            res = AttendanceSyncService.sync_parents(connection=db_conn)

        if not res.get("success"):
            self.stderr.write(self.style.ERROR(f"[ERROR] Parent sync failed: {res.get('error')}"))
            return

        roster = res.get("updated_roster", [])
        self.stdout.write(f"\n{'Student ID':<15} | {'Student Name':<25} | {'Parent / Sponsor':<25} | {'Relationship':<12} | {'Phone':<15}")
        self.stdout.write("-" * 95)
        for item in roster:
            self.stdout.write(
                f"{item['student_id']:<15} | {item['student_name']:<25} | {item['parent_name']:<25} | {item['relationship']:<12} | {item['parent_phone']:<15}"
            )

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS(
            f"[OK] PARENT SYNC COMPLETED SUCCESSFULLY:\n"
            f" - Attendance Students Scanned: {res.get('attendance_students_count', 0)}\n"
            f" - Matched CodeCampCore Profiles: {res.get('students_matched', 0)}\n"
            f" - New Parents Created:          {res.get('parents_created', 0)}\n"
            f" - Student Profiles Linked:       {res.get('parents_linked', 0)}"
        ))
        self.stdout.write("=" * 50 + "\n")
