"""
Interactive management command to import biographies from a custom Arabic CSV format.

Usage:
    python manage.py import_reciters_csv path/to/file.csv
    python manage.py import_reciters_csv path/to/file.csv --dry-run
    python manage.py import_reciters_csv path/to/file.csv --encoding utf-8
    python manage.py import_reciters_csv path/to/file.csv --skip-linking
"""

import csv
import difflib
import re
import sys
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.arabic_date_parser import parse_arabic_date
from core.csv_import import _normalize_ar, _find_location_candidates
from core.merge_utils import find_similar_to
from core.models import Attribute, Biography, Location, TeacherStudentRelationship
from core.search import normalize_arabic

# ── CSV column header keywords (normalized) ─────────────────────────────────

_COLUMN_KEYWORDS = {
    "alias":        ["شهره", "شهرة"],
    "full_name":    ["اسم الكامل", "الاسم الكامل"],
    "birth_date":   ["تاريخ الميلاد", "ميلاد"],
    "birthplace":   ["مكان الميلاد"],
    "death_date":   ["تاريخ الوفاة", "وفاة"],
    "death_place":  ["مكان الوفاة"],
    "teachers":     ["شيوخ", "شيوخه"],
    "students":     ["تلاميذ", "تلاميذه"],
    "attributes":   ["صفات", "تصنيفات"],
    "source":       ["مصدر"],
    "status":       ["حاله الترجمه", "حالة الترجمة", "معتمد"],
}

# Attribute separator characters.
_ATTR_SEPS = re.compile(r"[،,;؛/]")

# Teacher/student name separators.
_NAME_SEPS = re.compile(r"[،,;؛\n]")

# Location: "city (country)" pattern.
_LOC_RE = re.compile(r"^([^(]+)\s*\(([^)]+)\)\s*$")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _detect_columns(headers):
    """Map logical column names to CSV indices based on header text."""
    mapping = {}
    norm_headers = [_normalize_ar(h) for h in headers]
    for key, keywords in _COLUMN_KEYWORDS.items():
        for i, nh in enumerate(norm_headers):
            if any(_normalize_ar(kw) in nh for kw in keywords):
                mapping[key] = i
                break
    return mapping


def _parse_location_raw(text):
    """Return {'city_ar': ..., 'country_ar': ...} from 'city (country)' string."""
    if not text or text.strip() in ("-", "–", ""):
        return None
    text = text.strip()
    m = _LOC_RE.match(text)
    if m:
        return {"city_ar": m.group(1).strip(), "country_ar": m.group(2).strip()}
    return {"city_ar": text, "country_ar": ""}


def _split_names(text):
    """Split comma/semicolon/Arabic-comma separated name list."""
    if not text or text.strip() in ("-", "–", ""):
        return []
    parts = [p.strip() for p in _NAME_SEPS.split(text)]
    return [p for p in parts if p and p not in ("-", "–")]


def _split_attrs(text):
    """Split attribute list on common separators."""
    if not text or text.strip() in ("-", "–", ""):
        return []
    parts = [p.strip() for p in _ATTR_SEPS.split(text)]
    return [p for p in parts if p and p not in ("-", "–")]


def _prompt(question, choices, default=0):
    """
    Show a numbered menu and return the 0-based index of the chosen option.
    Pressing Enter selects `default`.
    """
    print(f"\n  {question}")
    for i, label in enumerate(choices, start=1):
        marker = " ← default" if i - 1 == default else ""
        print(f"    {i}. {label}{marker}")
    while True:
        raw = input("  Choose [1-{}]: ".format(len(choices))).strip()
        if raw == "":
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return int(raw) - 1
        print("  Invalid choice, try again.")


def _prompt_text(question, allow_empty=True):
    """Prompt for free text. Returns empty string if user presses Enter and allow_empty."""
    raw = input(f"  {question} ").strip()
    return raw


def _is_approved(status_text):
    """True if the حالة الترجمة column indicates a published/approved biography."""
    normalized = _normalize_ar(status_text or "")
    return "معتمد" in normalized or "approved" in normalized.lower()


def _date_is_ambiguous(parsed):
    """True if the parsed date needs user confirmation."""
    if parsed["calendar"] is None:
        return False  # empty — nothing to confirm
    if parsed["year"] is None:
        return True   # year could not be extracted
    if parsed["approximate"] and "وقيل" in parsed["raw"]:
        return True   # alternative year offered
    return False


def _fuzzy_match_attribute(name, all_attrs, threshold=0.75):
    """Find the best-matching Attribute for `name` using normalized comparison."""
    norm = _normalize_ar(name)
    best_score, best_attr = 0.0, None
    for attr in all_attrs:
        for candidate in (attr.short_name_ar, attr.long_name_ar, attr.short_name_en):
            if not candidate:
                continue
            nc = _normalize_ar(candidate)
            if nc == norm:
                return 1.0, attr  # exact normalized match
            score = difflib.SequenceMatcher(None, norm, nc).ratio()
            if score > best_score:
                best_score, best_attr = score, attr
    if best_score >= threshold:
        return best_score, best_attr
    return best_score, None


# ── Main command ─────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Import biographies from a custom Arabic CSV format (interactive wizard)"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", help="Path to the CSV file to import")
        parser.add_argument("--dry-run", action="store_true",
                            help="Pre-scan only: report decisions needed without writing to DB")
        parser.add_argument("--encoding", default="utf-8-sig",
                            help="CSV file encoding (default: utf-8-sig)")
        parser.add_argument("--skip-linking", action="store_true",
                            help="Skip Phase 4 teacher/student linking")

    def handle(self, *args, **options):
        csv_path = options["csv_file"]
        dry_run = options["dry_run"]
        encoding = options["encoding"]
        skip_linking = options["skip_linking"]

        # ── Read CSV ──────────────────────────────────────────────────────────
        try:
            with open(csv_path, encoding=encoding, newline="") as f:
                reader = csv.reader(f)
                raw_rows = list(reader)
        except FileNotFoundError:
            raise CommandError(f"File not found: {csv_path}")
        except UnicodeDecodeError as exc:
            raise CommandError(
                f"Encoding error reading {csv_path}: {exc}\n"
                "Try --encoding utf-8 or --encoding cp1256"
            )

        if len(raw_rows) < 2:
            raise CommandError("CSV has no data rows.")

        headers = raw_rows[0]
        col = _detect_columns(headers)

        required = ["full_name", "alias"]
        missing = [k for k in required if k not in col]
        if missing:
            raise CommandError(
                f"Could not detect required columns: {missing}\n"
                f"Headers found: {headers}"
            )

        self.stdout.write(f"Detected {len(raw_rows) - 1} data rows.")
        self.stdout.write(f"Column mapping: {col}")

        # ── Phase 0: published default ────────────────────────────────────────
        if dry_run:
            published_mode = "column"
        else:
            choice = _prompt(
                "Default published status for all imported biographies?",
                [
                    "Unpublished (default — safer)",
                    "Published",
                    "Use حالة الترجمة column (معتمد → published)",
                ],
                default=0,
            )
            published_mode = {0: "unpublished", 1: "published", 2: "column"}[choice]

        # ── Phase 1: Pre-scan ─────────────────────────────────────────────────
        self.stdout.write("\n── Phase 1: Pre-scan ──────────────────────────────")
        rows = []
        ambiguous_dates = 0
        missing_country = 0
        fuzzy_attrs = 0
        no_match_attrs = 0
        all_locations = list(Location.objects.all())
        all_attrs = list(Attribute.objects.all())

        for raw in raw_rows[1:]:
            def get(key):
                idx = col.get(key)
                if idx is None or idx >= len(raw):
                    return ""
                return raw[idx].strip()

            row = {
                "alias_ar":       get("alias"),
                "full_name_ar":   get("full_name"),
                "birth_date_raw": get("birth_date"),
                "birthplace_raw": get("birthplace"),
                "death_date_raw": get("death_date"),
                "death_place_raw":get("death_place"),
                "teachers_raw":   get("teachers"),
                "students_raw":   get("students"),
                "attributes_raw": get("attributes"),
                "source_raw":     get("source"),
                "status_raw":     get("status"),
            }

            if not row["full_name_ar"]:
                continue

            # Parse dates (just scan — don't prompt yet).
            row["birth_parsed"] = parse_arabic_date(row["birth_date_raw"])
            row["death_parsed"] = parse_arabic_date(row["death_date_raw"])

            if _date_is_ambiguous(row["birth_parsed"]):
                ambiguous_dates += 1
                row["birth_needs_confirm"] = True
            else:
                row["birth_needs_confirm"] = False

            if _date_is_ambiguous(row["death_parsed"]):
                ambiguous_dates += 1
                row["death_needs_confirm"] = True
            else:
                row["death_needs_confirm"] = False

            # Parse locations.
            row["birth_loc"] = _parse_location_raw(row["birthplace_raw"])
            row["death_loc"] = _parse_location_raw(row["death_place_raw"])

            for loc_key in ("birth_loc", "death_loc"):
                loc = row[loc_key]
                if loc and not loc["country_ar"]:
                    missing_country += 1
                    row[f"{loc_key}_needs_country"] = True
                else:
                    row[f"{loc_key}_needs_country"] = False

            # Classify attributes.
            attr_names = _split_attrs(row["attributes_raw"])
            row["attr_resolved"] = []
            row["attr_missing"] = []
            for name in attr_names:
                score, match = _fuzzy_match_attribute(name, all_attrs)
                if score == 1.0:
                    row["attr_resolved"].append(match)
                elif match is not None:
                    fuzzy_attrs += 1
                    row["attr_fuzzy_pending"] = row.get("attr_fuzzy_pending", [])
                    row["attr_fuzzy_pending"].append((name, score, match))
                else:
                    no_match_attrs += 1
                    row["attr_missing"].append(name)

            rows.append(row)

        self.stdout.write(f"  {len(rows)} rows parsed")
        self.stdout.write(f"  {ambiguous_dates} date strings need confirmation")
        self.stdout.write(f"  {missing_country} locations missing country")
        self.stdout.write(f"  {fuzzy_attrs} attribute names with fuzzy match (need confirmation)")
        self.stdout.write(f"  {no_match_attrs} attribute names with no match (will create new)")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n--dry-run: no changes written. Re-run without --dry-run to import."
            ))
            return

        if not rows:
            self.stdout.write("No rows to import.")
            return

        confirm = input("\nProceed with interactive import? [y/n]: ").strip().lower()
        if confirm != "y":
            self.stdout.write("Aborted.")
            return

        # ── Phase 2: Interactive resolution ───────────────────────────────────
        self.stdout.write("\n── Phase 2: Interactive resolution ────────────────")

        # 2a. Resolve ambiguous dates and locations per row.
        for i, row in enumerate(rows, start=1):
            name = row["full_name_ar"]

            for prefix, label in [("birth", "Birth"), ("death", "Death")]:
                if not row[f"{prefix}_needs_confirm"]:
                    continue
                parsed = row[f"{prefix}_parsed"]
                raw_text = parsed["raw"]
                print(f"\n  Row {i} — {name}")
                print(f"  {label} date raw: \"{raw_text}\"")

                if parsed["year"] is None:
                    # Cannot extract year — ask for manual input.
                    print("  Cannot extract year from this text.")
                    choices = ["Enter year manually (Hijri)", "Leave date empty"]
                    choice = _prompt(f"{label} date resolution:", choices, default=1)
                    if choice == 0:
                        year_str = _prompt_text("Enter Hijri year (digits only):")
                        if year_str.isdigit():
                            parsed["year"] = int(year_str)
                            parsed["calendar"] = "hijri"
                            parsed["approximate"] = True
                        else:
                            parsed["year"] = None
                    else:
                        parsed["calendar"] = None
                else:
                    # Year extracted but text has alternatives or qualifiers.
                    alt_match = re.search(r"وقيل\s+(\d+)هـ", raw_text)
                    choices = [f"Accept as-is ({parsed['year']}هـ, approximate={parsed['approximate']})"]
                    if alt_match:
                        alt_year = int(alt_match.group(1))
                        choices.append(f"Use alternative year {alt_year}هـ (approximate)")
                    choices.append("Enter manually")
                    choices.append("Leave date empty")

                    choice = _prompt(f"{label} date resolution:", choices, default=0)
                    if choice == 0:
                        pass  # keep as-is
                    elif alt_match and choice == 1:
                        parsed["year"] = int(alt_match.group(1))
                        parsed["approximate"] = True
                    elif choice == len(choices) - 2:  # enter manually
                        year_str = _prompt_text("Enter Hijri year:")
                        if year_str.isdigit():
                            parsed["year"] = int(year_str)
                            parsed["calendar"] = "hijri"
                        approx_ans = _prompt_text("Approximate? [y/n]:").lower()
                        parsed["approximate"] = approx_ans == "y"
                    else:
                        parsed["calendar"] = None

                row[f"{prefix}_parsed"] = parsed

            # 2b. Resolve missing countries.
            for loc_key, label in [("birth_loc", "Birth place"), ("death_loc", "Death place")]:
                if not row.get(f"{loc_key}_needs_country"):
                    continue
                loc = row[loc_key]
                print(f"\n  Row {i} — {name}")
                print(f"  {label}: \"{loc['city_ar']}\"")
                print("  No country detected.")

                existing_countries = sorted({l.country_ar for l in all_locations if l.country_ar})
                country_list = existing_countries[:10] if existing_countries else []
                choices = ["Type country name (Arabic)"] + country_list + ["Leave country blank"]
                choice = _prompt("Select or type country:", choices, default=0)

                if choice == 0:
                    country = _prompt_text("Country name (Arabic):")
                    loc["country_ar"] = country
                elif choice <= len(country_list):
                    loc["country_ar"] = country_list[choice - 1]
                else:
                    loc["country_ar"] = ""

                # Also check if this is actually a region not a city.
                ambig = _prompt(
                    f'Is "{loc["city_ar"]}" a city or a country/region?',
                    ["City (with the country just entered)", "Country/region only (no specific city)"],
                    default=0,
                )
                if ambig == 1:
                    loc["country_ar"] = loc["city_ar"]
                    loc["city_ar"] = ""

                row[loc_key] = loc

        # 2c. Resolve attribute fuzzy matches (deduplicated across all rows).
        pending_attr_decisions = {}  # name → resolved Attribute or None (create)
        new_attr_cache = {}          # name → newly created Attribute

        for row in rows:
            for (name, score, match) in row.get("attr_fuzzy_pending", []):
                if name in pending_attr_decisions:
                    continue
                print(f"\n  Attribute: \"{name}\"")
                print(f"  Closest match in DB: \"{match.short_name_ar}\" — similarity {score:.0%}")
                choices = [
                    f"Accept match \"{match.short_name_ar}\"",
                    f"Create new attribute \"{name}\"",
                    "Skip this attribute",
                ]
                choice = _prompt("Choose:", choices, default=0)
                if choice == 0:
                    pending_attr_decisions[name] = match
                elif choice == 1:
                    pending_attr_decisions[name] = None  # will create below
                else:
                    pending_attr_decisions[name] = "skip"

            for name in row.get("attr_missing", []):
                if name in pending_attr_decisions or name in new_attr_cache:
                    continue
                print(f"\n  Attribute \"{name}\" — no match in DB.")
                long_name = _prompt_text(
                    f"Enter long_name_ar (or press Enter to use \"{name}\" as-is):"
                )
                pending_attr_decisions[name] = None  # create new
                new_attr_cache[name] = long_name or name

        # ── Phase 3: Commit ───────────────────────────────────────────────────
        self.stdout.write("\n── Phase 3: Commit ─────────────────────────────────")
        stats = defaultdict(int)
        bio_map = {}  # full_name_ar → Biography pk (for Phase 4)

        # Pre-create new attributes.
        for name, long_name in new_attr_cache.items():
            attr, created = Attribute.objects.get_or_create(
                short_name_ar=name,
                defaults={"long_name_ar": long_name or name},
            )
            pending_attr_decisions[name] = attr
            if created:
                stats["new_attrs"] += 1

        # Pre-create/find new attributes from fuzzy decisions (None = create).
        for name, decision in list(pending_attr_decisions.items()):
            if decision is None:
                attr, created = Attribute.objects.get_or_create(
                    short_name_ar=name,
                    defaults={"long_name_ar": name},
                )
                pending_attr_decisions[name] = attr
                if created:
                    stats["new_attrs"] += 1

        # Resolve location objects (find or create).
        loc_cache = {}  # (city_ar, country_ar) → Location

        def resolve_location(loc_spec):
            if not loc_spec:
                return None
            city = loc_spec["city_ar"] or ""
            country = loc_spec["country_ar"] or ""
            key = (city, country)
            if key in loc_cache:
                return loc_cache[key]
            candidates = _find_location_candidates(
                {"city_ar": city, "country_ar": country}, all_locations
            )
            if candidates and candidates[0][1]:  # normalized exact match
                loc = candidates[0][2]
            else:
                loc, created = Location.objects.get_or_create(
                    city_ar=city, country_ar=country
                )
                if created:
                    stats["new_locations"] += 1
                    all_locations.append(loc)
            loc_cache[key] = loc
            return loc

        accept_all_duplicates = None  # None = ask each time

        with transaction.atomic():
            for row in rows:
                name = row["full_name_ar"]
                self.stdout.write(f"  Importing: {name} ...", ending="")

                # Duplicate check.
                similar = find_similar_to(name)
                existing = None
                if similar:
                    top = similar[0]
                    top_bio_stub, match_type, _, similarity = top
                    if match_type == "cross_field" and similarity == 1.0:
                        # Exact match — update silently.
                        try:
                            existing = Biography.objects.get(pk=top_bio_stub.pk)
                        except Biography.DoesNotExist:
                            pass
                    else:
                        # Fuzzy match — ask user.
                        if accept_all_duplicates is None:
                            print()
                            print(
                                f"  Possible duplicate for \"{name}\": "
                                f"\"{top_bio_stub.full_name_ar}\" ({similarity:.0%} {match_type})"
                            )
                            choices = [
                                "Same person — update existing",
                                "Different person — create new",
                                "Accept ALL future duplicates automatically",
                                "Skip ALL future duplicates automatically",
                            ]
                            choice = _prompt("How to handle?", choices, default=1)
                            if choice == 0:
                                try:
                                    existing = Biography.objects.get(pk=top_bio_stub.pk)
                                except Biography.DoesNotExist:
                                    pass
                            elif choice == 2:
                                accept_all_duplicates = "update"
                                try:
                                    existing = Biography.objects.get(pk=top_bio_stub.pk)
                                except Biography.DoesNotExist:
                                    pass
                            elif choice == 3:
                                accept_all_duplicates = "create"
                        elif accept_all_duplicates == "update":
                            try:
                                existing = Biography.objects.get(pk=top_bio_stub.pk)
                            except Biography.DoesNotExist:
                                pass

                bio = existing or Biography()
                is_new = existing is None

                # Basic fields.
                bio.full_name_ar = name
                if row["alias_ar"]:
                    bio.alias_ar = row["alias_ar"]

                # Published status.
                if published_mode == "published":
                    bio.published = True
                elif published_mode == "unpublished":
                    if is_new:
                        bio.published = False
                else:
                    bio.published = _is_approved(row["status_raw"])

                # Source → comments_ar.
                if row["source_raw"] and row["source_raw"] not in ("-", "–"):
                    source_note = f"المصدر: {row['source_raw']}"
                    if source_note not in (bio.comments_ar or ""):
                        bio.comments_ar = (bio.comments_ar + "\n" + source_note).strip() if bio.comments_ar else source_note

                # Dates.
                for prefix in ("birth", "death"):
                    parsed = row[f"{prefix}_parsed"]
                    raw_val = parsed["raw"]

                    # Always store the raw text.
                    setattr(bio, f"{prefix}_date_raw_ar", raw_val)

                    if parsed["calendar"] is None or parsed["year"] is None:
                        continue

                    if parsed["calendar"] == "hijri":
                        cal = "hijri"
                    else:
                        cal = "greg"

                    # Only set if field is empty on existing bio.
                    year_field = f"{prefix}_{cal}_year"
                    if is_new or not getattr(bio, year_field):
                        setattr(bio, year_field, parsed["year"])
                        setattr(bio, f"{prefix}_{cal}_month", parsed["month"])
                        setattr(bio, f"{prefix}_{cal}_day", parsed["day"])
                        setattr(bio, f"{prefix}_{cal}_approximate", parsed["approximate"])

                # Locations.
                for loc_key, field_name in [("birth_loc", "birthplace"), ("death_loc", "death_location")]:
                    loc_obj = resolve_location(row[loc_key])
                    if loc_obj and (is_new or not getattr(bio, field_name + "_id")):
                        setattr(bio, field_name, loc_obj)

                bio.save()

                # Attributes (M2M).
                attrs_to_add = list(row["attr_resolved"])
                for name_key, decision in pending_attr_decisions.items():
                    if decision == "skip":
                        continue
                    if isinstance(decision, Attribute):
                        # Check if this attribute was requested for this row.
                        all_req = (
                            [n for n, _, _ in row.get("attr_fuzzy_pending", [])]
                            + row.get("attr_missing", [])
                        )
                        if name_key in all_req:
                            attrs_to_add.append(decision)
                for attr in attrs_to_add:
                    bio.attributes.add(attr)

                bio_map[bio.full_name_ar] = bio.pk

                if is_new:
                    stats["created"] += 1
                    self.stdout.write(" created")
                else:
                    stats["updated"] += 1
                    self.stdout.write(" updated")

        # ── Phase 4: Teacher/Student linking ──────────────────────────────────
        if not skip_linking:
            self.stdout.write("\n── Phase 4: Teacher/Student linking ────────────────")
            accept_all_teachers = None
            skip_all_teachers = False

            # Reload all biographies for linking (includes newly created stubs).
            for row in rows:
                if not row["full_name_ar"] or row["full_name_ar"] not in bio_map:
                    continue
                student_pk = bio_map[row["full_name_ar"]]
                try:
                    student_bio = Biography.objects.get(pk=student_pk)
                except Biography.DoesNotExist:
                    continue

                for role, role_raw, rel_field in [
                    ("teacher", "teachers_raw", None),
                    ("student", "students_raw", None),
                ]:
                    names = _split_names(row[f"{role}_raw"])
                    for person_name in names:
                        if not person_name:
                            continue

                        similar = find_similar_to(person_name)
                        matched_bio = None

                        if similar:
                            top = similar[0]
                            top_stub, match_type, _, similarity = top
                            if match_type == "cross_field" and similarity == 1.0:
                                matched_bio = Biography.objects.filter(pk=top_stub.pk).first()
                            elif not skip_all_teachers:
                                if accept_all_teachers:
                                    matched_bio = Biography.objects.filter(pk=top_stub.pk).first()
                                else:
                                    print(
                                        f"\n  {role.title()} of \"{student_bio}\": \"{person_name}\""
                                    )
                                    print(
                                        f"  Best match: \"{top_stub.full_name_ar}\" — {similarity:.0%} ({match_type})"
                                    )
                                    choices = [
                                        f"Link as {role}",
                                        "Create new stub biography and link",
                                        "Accept ALL future matches automatically",
                                        "Skip ALL future unconfirmed matches",
                                    ]
                                    choice = _prompt("Choose:", choices, default=0)
                                    if choice == 0:
                                        matched_bio = Biography.objects.filter(pk=top_stub.pk).first()
                                    elif choice == 1:
                                        matched_bio = None  # will create stub below
                                    elif choice == 2:
                                        accept_all_teachers = True
                                        matched_bio = Biography.objects.filter(pk=top_stub.pk).first()
                                    elif choice == 3:
                                        skip_all_teachers = True
                                        continue
                        else:
                            if skip_all_teachers:
                                continue

                        if matched_bio is None:
                            # Create a stub biography for this unmatched name.
                            matched_bio, created = Biography.objects.get_or_create(
                                full_name_ar=person_name,
                                defaults={"published": False},
                            )
                            if created:
                                stats["stub_bios"] += 1
                                bio_map[person_name] = matched_bio.pk

                        # Create the relationship.
                        teacher_bio = matched_bio if role == "teacher" else student_bio
                        actual_student = student_bio if role == "teacher" else matched_bio
                        if teacher_bio.pk != actual_student.pk:
                            _, created = TeacherStudentRelationship.objects.get_or_create(
                                teacher=teacher_bio,
                                student=actual_student,
                            )
                            if created:
                                stats["relationships"] += 1

        # ── Summary ───────────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS("\n── Import complete ─────────────────────────────────"))
        self.stdout.write(f"  {stats['created']} created")
        self.stdout.write(f"  {stats['updated']} updated")
        self.stdout.write(f"  {stats['new_locations']} new locations created")
        self.stdout.write(f"  {stats['new_attrs']} new attributes created")
        self.stdout.write(f"  {stats['stub_bios']} stub biographies created (teachers/students)")
        self.stdout.write(f"  {stats['relationships']} teacher/student relationships linked")
