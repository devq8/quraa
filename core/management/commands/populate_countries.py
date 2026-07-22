"""Create a ``Country`` row for every distinct country found in the ``Location``
table's ``country_ar`` column.

This only touches the ``Country`` table — it does not link Locations or create
cities (use ``migrate_location_data`` for the full backfill). Country names are
trimmed and de-duplicated, so values differing only by surrounding whitespace
collapse into a single ``Country``.

Idempotent (existing countries are left alone) and safe to re-run. ``--dry-run``
reports what would be created without writing anything.

Usage:
    python manage.py populate_countries --dry-run
    python manage.py populate_countries
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Country, Location


class Command(BaseCommand):
    help = (
        "Create a Country row for every distinct country in the Location table. "
        "Idempotent; use --dry-run to preview."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would be created without writing anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Map each trimmed Arabic country name to a representative English name
        # (the first non-empty one seen).
        names = {}
        for country_ar, country_en in Location.objects.values_list("country_ar", "country_en"):
            name_ar = (country_ar or "").strip()
            if not name_ar:
                continue
            name_en = (country_en or "").strip()
            if name_ar not in names or (not names[name_ar] and name_en):
                names[name_ar] = name_en

        created, existing = 0, 0
        created_names = []
        with transaction.atomic():
            for name_ar, name_en in sorted(names.items()):
                country, was_created = Country.objects.get_or_create(
                    name_ar=name_ar, defaults={"name_en": name_en},
                )
                if was_created:
                    created += 1
                    created_names.append(name_ar)
                else:
                    existing += 1
            if dry_run:
                transaction.set_rollback(True)

        title = "DRY RUN — no changes written" if dry_run else "Done"
        self.stdout.write(self.style.MIGRATE_HEADING(title))
        self.stdout.write(f"  Distinct countries in Location: {len(names)}")
        self.stdout.write(f"  Countries created:              {created}")
        self.stdout.write(f"  Already existed:                {existing}")
        if created_names:
            self.stdout.write("  Created: " + "، ".join(created_names))
