"""Management command: merge two Biography records.

Usage:
    python manage.py merge_biographies <primary_id> <duplicate_id>
    python manage.py merge_biographies <primary_id> <duplicate_id> --dry-run
"""

from django.core.management.base import BaseCommand, CommandError

from core.merge_utils import compute_field_resolutions, merge_biographies


class Command(BaseCommand):
    help = "Merge a duplicate Biography into a primary Biography."

    def add_arguments(self, parser):
        parser.add_argument("primary_id", type=int, help="ID of the biography to keep.")
        parser.add_argument("duplicate_id", type=int, help="ID of the biography to merge away.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would happen without writing anything.",
        )

    def handle(self, *args, **options):
        from core.models import Biography

        try:
            primary = Biography.objects.get(pk=options["primary_id"])
        except Biography.DoesNotExist:
            raise CommandError(f"Biography #{options['primary_id']} not found.")

        try:
            duplicate = Biography.objects.get(pk=options["duplicate_id"])
        except Biography.DoesNotExist:
            raise CommandError(f"Biography #{options['duplicate_id']} not found.")

        if primary.pk == duplicate.pk:
            raise CommandError("Primary and duplicate are the same biography.")

        dry_run = options["dry_run"]

        self.stdout.write(f"Primary:   #{primary.pk}  {primary.full_name_ar}")
        self.stdout.write(f"Duplicate: #{duplicate.pk}  {duplicate.full_name_ar}")
        self.stdout.write("")

        resolutions = compute_field_resolutions(primary, duplicate)
        conflict_fields = [r for r in resolutions if r.status == "conflict"]

        field_choices = {}

        if conflict_fields:
            self.stdout.write(self.style.WARNING(f"{len(conflict_fields)} conflict(s) to resolve:\n"))
            for res in conflict_fields:
                self.stdout.write(f"  Field: {res.label} ({res.field_name})")
                self.stdout.write(f"    A (primary #{primary.pk}):   {res.display_a}")
                self.stdout.write(f"    B (duplicate #{duplicate.pk}): {res.display_b}")

                if dry_run:
                    field_choices[res.field_name] = "a"
                    self.stdout.write("    → [DRY RUN] defaulting to A")
                else:
                    while True:
                        choice = input("    Keep [A] or [B]? ").strip().lower()
                        if choice in ("a", "b"):
                            field_choices[res.field_name] = choice
                            break
                        self.stdout.write("    Please enter A or B.")
                self.stdout.write("")
        else:
            self.stdout.write("No field conflicts — merge will auto-fill missing fields.\n")

        if dry_run:
            self.stdout.write(self.style.WARNING("--- DRY RUN --- (no changes will be written)\n"))

        log = merge_biographies(primary, duplicate, field_choices, dry_run=dry_run)

        for level, msg in log:
            if level == "error":
                self.stderr.write(self.style.ERROR(f"  ERROR: {msg}"))
            elif level == "warning":
                self.stdout.write(self.style.WARNING(f"  WARN:  {msg}"))
            else:
                self.stdout.write(f"  {msg}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\nDry run complete — no changes written."))
        elif not log.has_errors():
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nMerged Biography #{duplicate.pk} into #{primary.pk} successfully."
                )
            )
        else:
            self.stderr.write(self.style.ERROR("\nMerge completed with errors — review output above."))
