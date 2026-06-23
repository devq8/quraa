"""Management command: find duplicate biographies.

Usage:
    python manage.py find_duplicate_biographies
    python manage.py find_duplicate_biographies --fuzzy
    python manage.py find_duplicate_biographies --fuzzy --threshold 0.80
"""

from django.core.management.base import BaseCommand

from core.merge_utils import build_duplicate_candidates


class Command(BaseCommand):
    help = "Find potential duplicate Biography records by name similarity."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fuzzy",
            action="store_true",
            help="Also include fuzzy (SequenceMatcher) near-matches.",
        )
        parser.add_argument(
            "--threshold",
            type=float,
            default=0.85,
            help="Minimum similarity ratio for fuzzy matches (default: 0.85).",
        )

    def handle(self, *args, **options):
        fuzzy = options["fuzzy"]
        threshold = options["threshold"]

        self.stdout.write("Scanning for duplicate biographies…")
        candidates = build_duplicate_candidates(fuzzy=fuzzy, threshold=threshold)

        if not candidates:
            self.stdout.write(self.style.SUCCESS("No duplicate biographies found."))
            return

        by_type = {"exact": [], "cross_field": [], "partial": [], "fuzzy": []}
        for c in candidates:
            by_type[c.match_type].append(c)

        type_labels = {
            "exact":       "Exact normalized match",
            "cross_field": "Cross-field exact match",
            "partial":     "Partial / substring match",
            "fuzzy":       f"Fuzzy near-match (threshold {threshold})",
        }

        total = len(candidates)
        self.stdout.write(f"\nFound {total} potential duplicate pair(s):\n")

        for match_type, label in type_labels.items():
            group = by_type[match_type]
            if not group:
                continue
            self.stdout.write(self.style.WARNING(f"=== {label} ({len(group)}) ==="))
            for c in group:
                sim_pct = int(c.similarity * 100)
                fa, fb = c.match_fields
                self.stdout.write(
                    f"  #{c.bio_a.pk:>6}  {c.bio_a.full_name_ar}"
                    + (f"  [{c.bio_a.alias_ar}]" if c.bio_a.alias_ar else "")
                )
                self.stdout.write(
                    f"  #{c.bio_b.pk:>6}  {c.bio_b.full_name_ar}"
                    + (f"  [{c.bio_b.alias_ar}]" if c.bio_b.alias_ar else "")
                )
                self.stdout.write(
                    f"          match: {fa} ↔ {fb}  ({sim_pct}%)"
                )
                self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                f"To merge a pair: python manage.py merge_biographies <primary_id> <duplicate_id>"
            )
        )
