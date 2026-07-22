"""Migrate the denormalized ``Location`` text columns into the normalized
``Country`` / ``City`` tables and link each ``Location`` to them.

This is a deliberate, on-demand step: the schema migration only creates the
empty ``Country`` / ``City`` tables and the nullable ``Location.city`` /
``Location.country`` columns, leaving all existing data untouched. Run this
command once you are satisfied with the new structure to populate it.

Safety:
    * The ``city_ar`` / ``city_en`` / ``country_ar`` / ``country_en`` columns are
      **never modified** — they remain the source of truth until you explicitly
      decide to drop them in a later, separate migration.
    * Idempotent: re-running only creates what is missing and links what is not
      yet linked. Already-correct rows are left alone.
    * ``--dry-run`` reports exactly what would change without writing anything.

Usage:
    python manage.py migrate_location_data --dry-run
    python manage.py migrate_location_data
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import City, Country, Location


def _clean(value):
    return (value or "").strip()


class Command(BaseCommand):
    help = (
        "Backfill Country/City from Location text columns and link the FKs. "
        "Idempotent; never modifies the text columns. Use --dry-run to preview."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without writing anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        stats = {
            "countries_created": 0,
            "cities_created": 0,
            "locations_linked": 0,
            "locations_already_linked": 0,
            "locations_empty": 0,
        }
        # Rows with a city but no country — informational; linked with a null
        # country (a city whose country is unknown).
        cities_without_country = []

        country_cache = {}   # name_ar -> Country
        city_cache = {}      # (country_id, name_ar) -> City

        with transaction.atomic():
            for loc in Location.objects.all().iterator():
                country_ar = _clean(loc.country_ar)
                city_ar = _clean(loc.city_ar)

                if not country_ar and not city_ar:
                    stats["locations_empty"] += 1
                    continue

                country = None
                if country_ar:
                    country = country_cache.get(country_ar)
                    if country is None:
                        country, created = Country.objects.get_or_create(
                            name_ar=country_ar,
                            defaults={"name_en": _clean(loc.country_en)},
                        )
                        country_cache[country_ar] = country
                        if created:
                            stats["countries_created"] += 1

                city = None
                if city_ar:
                    if country is None:
                        cities_without_country.append(city_ar)
                    key = (country.id if country else None, city_ar)
                    city = city_cache.get(key)
                    if city is None:
                        city, created = City.objects.get_or_create(
                            country=country, name_ar=city_ar,
                            defaults={"name_en": _clean(loc.city_en)},
                        )
                        city_cache[key] = city
                        if created:
                            stats["cities_created"] += 1

                new_country_id = country.id if country else None
                new_city_id = city.id if city else None
                if loc.country_id == new_country_id and loc.city_id == new_city_id:
                    stats["locations_already_linked"] += 1
                else:
                    # .update() bypasses Location.save() so the text columns are
                    # left exactly as they are — only the FKs are written.
                    Location.objects.filter(pk=loc.pk).update(
                        city=city, country=country
                    )
                    stats["locations_linked"] += 1

            if dry_run:
                transaction.set_rollback(True)

        self._report(stats, cities_without_country, dry_run)

    def _report(self, stats, cities_without_country, dry_run):
        title = "DRY RUN — no changes written" if dry_run else "Migration complete"
        self.stdout.write(self.style.MIGRATE_HEADING(title))
        self.stdout.write(f"  Countries created:          {stats['countries_created']}")
        self.stdout.write(f"  Cities created:             {stats['cities_created']}")
        self.stdout.write(f"  Locations linked:           {stats['locations_linked']}")
        self.stdout.write(f"  Locations already linked:   {stats['locations_already_linked']}")
        self.stdout.write(f"  Locations empty (skipped):  {stats['locations_empty']}")

        if cities_without_country:
            unique = sorted(set(cities_without_country))
            self.stdout.write(self.style.WARNING(
                f"  {len(unique)} city name(s) had no country and were linked "
                f"with a null country: {', '.join(unique)}"
            ))

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                "Text columns were left untouched — nothing was destroyed."
            ))
