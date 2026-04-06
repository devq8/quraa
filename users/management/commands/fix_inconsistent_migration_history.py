# One-time fix for InconsistentMigrationHistory: admin applied before users.0001_initial.
# Removes admin from django_migrations and drops django_admin_log so migrate can run in correct order.

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Fix InconsistentMigrationHistory by unapplying admin migrations and dropping django_admin_log so migrate can run (users first, then admin)."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # 1) Drop django_admin_log so admin.0001_initial can recreate it on next migrate
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='django_admin_log'"
            )
            if cursor.fetchone():
                cursor.execute("DROP TABLE django_admin_log")
                dropped = True
            else:
                dropped = False

            # 2) Remove admin from migration history so dependency order can be satisfied
            cursor.execute("DELETE FROM django_migrations WHERE app = 'admin'")
            deleted_count = cursor.rowcount

        self.stdout.write(
            self.style.SUCCESS(
                f"Unapplied admin migrations (rows deleted: {deleted_count}). "
                f"Dropped django_admin_log: {dropped}. Run: python manage.py migrate"
            )
        )
