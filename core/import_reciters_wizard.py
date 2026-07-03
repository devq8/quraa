"""
Logic for the web-based biography import wizard (admin view).
Handles CSV parsing, pre-scan analysis, and the commit transaction.
"""

import csv
import difflib
import io
import re
from collections import defaultdict

from django.db import transaction

from .arabic_date_parser import parse_arabic_date
from .csv_import import _normalize_ar, _find_location_candidates
from .models import Attribute, Biography, Location, TeacherStudentRelationship
from .search import normalize_arabic

_COLUMN_KEYWORDS = {
    "alias":       ["شهره", "شهرة"],
    "full_name":   ["اسم الكامل", "الاسم الكامل"],
    "birth_date":  ["تاريخ الميلاد", "ميلاد"],
    "birthplace":  ["مكان الميلاد"],
    "death_date":  ["تاريخ الوفاة", "وفاة"],
    "death_place": ["مكان الوفاة"],
    "teachers":    ["شيوخ", "شيوخه"],
    "students":    ["تلاميذ", "تلاميذه"],
    "attributes":  ["صفات", "تصنيفات"],
    "source":      ["مصدر"],
    "status":      ["حاله الترجمه", "حالة الترجمة", "معتمد"],
}

_ATTR_SEPS = re.compile(r"[،,;؛/]")
_NAME_SEPS = re.compile(r"[،,;؛\n]")
_LOC_RE = re.compile(r"^([^(]+)\s*\(([^)]+)\)\s*$")


def _detect_columns(headers):
    mapping = {}
    norm_headers = [_normalize_ar(h) for h in headers]
    for key, keywords in _COLUMN_KEYWORDS.items():
        for i, nh in enumerate(norm_headers):
            if any(_normalize_ar(kw) in nh for kw in keywords):
                mapping[key] = i
                break
    return mapping


def _parse_loc(text):
    if not text or text.strip() in ("-", "–", ""):
        return None
    text = text.strip()
    m = _LOC_RE.match(text)
    if m:
        return {"city_ar": m.group(1).strip(), "country_ar": m.group(2).strip()}
    return {"city_ar": text, "country_ar": ""}


def _split_names(text):
    if not text or text.strip() in ("-", "–", ""):
        return []
    return [p.strip() for p in _NAME_SEPS.split(text) if p.strip() and p.strip() not in ("-", "–")]


def _split_attrs(text):
    if not text or text.strip() in ("-", "–", ""):
        return []
    return [p.strip() for p in _ATTR_SEPS.split(text) if p.strip() and p.strip() not in ("-", "–")]


def _date_is_ambiguous(parsed):
    if parsed["calendar"] is None:
        return False
    if parsed["year"] is None:
        return True
    if parsed["approximate"] and "وقيل" in parsed["raw"]:
        return True
    return False


def _fuzzy_match_attr(name, all_attrs, threshold=0.75):
    norm = _normalize_ar(name)
    best_score, best_attr = 0.0, None
    for attr in all_attrs:
        for candidate in (attr.short_name_ar, attr.long_name_ar, attr.short_name_en):
            if not candidate:
                continue
            nc = _normalize_ar(candidate)
            if nc == norm:
                return 1.0, attr
            score = difflib.SequenceMatcher(None, norm, nc).ratio()
            if score > best_score:
                best_score, best_attr = score, attr
    if best_score >= threshold:
        return best_score, best_attr
    return best_score, None


def _is_approved(status_text):
    normalized = _normalize_ar(status_text or "")
    return "معتمد" in normalized or "approved" in normalized.lower()


def scan_csv_file(file_obj):
    """Read an uploaded Django InMemoryUploadedFile, parse CSV, scan all rows."""
    text = file_obj.read()
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = text.decode("cp1256", errors="replace")
    return scan_csv_text(text)


def scan_csv_text(text):
    """
    Parse CSV text, scan all rows. Returns (rows, stats, csv_text).

    rows: list of JSON-serializable dicts, one per biography.
    stats: summary counts dict.
    csv_text: the original text (stored in session for re-parse if needed).
    """
    raw_rows = list(csv.reader(io.StringIO(text)))
    if len(raw_rows) < 2:
        return [], {"total": 0}, text

    headers = raw_rows[0]
    col = _detect_columns(headers)
    all_attrs = list(Attribute.objects.all())

    rows = []
    stats = defaultdict(int)

    for raw in raw_rows[1:]:
        def get(key, _raw=raw):
            idx = col.get(key)
            if idx is None or idx >= len(_raw):
                return ""
            return _raw[idx].strip()

        full_name = get("full_name")
        if not full_name:
            continue

        row = {
            "alias_ar":       get("alias"),
            "full_name_ar":   full_name,
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

        row["birth_parsed"] = parse_arabic_date(row["birth_date_raw"])
        row["death_parsed"] = parse_arabic_date(row["death_date_raw"])
        row["birth_needs_confirm"] = _date_is_ambiguous(row["birth_parsed"])
        row["death_needs_confirm"] = _date_is_ambiguous(row["death_parsed"])

        if row["birth_needs_confirm"]:
            stats["ambiguous_dates"] += 1
        if row["death_needs_confirm"]:
            stats["ambiguous_dates"] += 1

        birth_loc = _parse_loc(row["birthplace_raw"])
        death_loc = _parse_loc(row["death_place_raw"])
        row["birth_loc"] = birth_loc
        row["death_loc"] = death_loc
        row["birth_loc_needs_country"] = bool(birth_loc and not birth_loc["country_ar"])
        row["death_loc_needs_country"] = bool(death_loc and not death_loc["country_ar"])

        if row["birth_loc_needs_country"]:
            stats["missing_countries"] += 1
        if row["death_loc_needs_country"]:
            stats["missing_countries"] += 1

        attr_names = _split_attrs(row["attributes_raw"])
        row["attr_exact_pks"] = []
        row["attr_fuzzy"] = []
        row["attr_missing"] = []
        seen_names = set()
        for name in attr_names:
            if name in seen_names:
                continue
            seen_names.add(name)
            score, match = _fuzzy_match_attr(name, all_attrs)
            if score == 1.0:
                row["attr_exact_pks"].append(match.pk)
            elif match is not None:
                row["attr_fuzzy"].append({
                    "name": name,
                    "score": round(score, 3),
                    "match_pk": match.pk,
                    "match_name": match.short_name_ar or "",
                })
                stats["fuzzy_attrs"] += 1
            else:
                row["attr_missing"].append(name)
                stats["missing_attrs"] += 1

        rows.append(row)
        stats["total"] += 1

    return rows, dict(stats), text


def get_unique_missing_cities(rows):
    """Return unique city_ar values that need a country, preserving first-seen order."""
    seen = {}
    for row in rows:
        for loc_key in ("birth_loc", "death_loc"):
            if row.get(f"{loc_key}_needs_country") and row.get(loc_key):
                city = row[loc_key]["city_ar"]
                if city and city not in seen:
                    seen[city] = True
    return list(seen.keys())


def get_unique_fuzzy_attrs(rows):
    """Return unique fuzzy-match attribute items across all rows."""
    seen = {}
    for row in rows:
        for item in row.get("attr_fuzzy", []):
            if item["name"] not in seen:
                seen[item["name"]] = item
    return list(seen.values())


def get_unique_missing_attrs(rows):
    """Return unique no-match attribute names across all rows."""
    seen = {}
    for row in rows:
        for name in row.get("attr_missing", []):
            if name not in seen:
                seen[name] = True
    return list(seen.keys())


def commit_import(rows, published_mode, date_decisions, location_decisions, attr_decisions, teacher_fuzzy_mode="auto"):
    """
    Commit all rows to the database.

    date_decisions    : {"0_birth": parsed_dict, "1_death": parsed_dict, ...}
    location_decisions: {"city_ar": {"city_ar": str, "country_ar": str}}
    attr_decisions    : {"attr_name": {"action": "accept"|"create"|"skip",
                                       "match_pk": int|None, "long_name": str}}
    teacher_fuzzy_mode: "auto"  → link fuzzy matches (≥0.85) automatically
                        "stub"  → create a stub bio for fuzzy matches
                        "skip"  → skip unmatched names entirely

    Returns a stats dict.
    """
    stats = defaultdict(int)
    bio_map = {}  # full_name_ar → pk (used in Phase 4)

    # ── Pre-create / resolve attributes ──────────────────────────────────────
    pending_attr_pks = {}  # attr_name → int pk, or "skip"
    for attr_name, decision in attr_decisions.items():
        action = decision.get("action", "skip")
        if action == "accept":
            match_pk = decision.get("match_pk")
            if match_pk:
                pending_attr_pks[attr_name] = int(match_pk)
        elif action == "create":
            long_name = decision.get("long_name") or attr_name
            attr, created = Attribute.objects.get_or_create(
                short_name_ar=attr_name,
                defaults={"long_name_ar": long_name},
            )
            pending_attr_pks[attr_name] = attr.pk
            if created:
                stats["new_attrs"] += 1
        # "skip" → omit from pending_attr_pks

    # ── Location resolver ─────────────────────────────────────────────────────
    all_locations = list(Location.objects.all())
    loc_cache = {}  # (city_ar, country_ar) → Location

    def resolve_location(city_ar, country_ar):
        key = (city_ar or "", country_ar or "")
        if key in loc_cache:
            return loc_cache[key]
        spec = {"city_ar": key[0], "country_ar": key[1]}
        candidates = _find_location_candidates(spec, all_locations)
        if candidates and candidates[0][1]:  # exact normalized match
            loc = candidates[0][2]
        else:
            loc, created = Location.objects.get_or_create(
                city_ar=key[0], country_ar=key[1]
            )
            if created:
                stats["new_locations"] += 1
                all_locations.append(loc)
        loc_cache[key] = loc
        return loc

    # ── Phase 3: Commit biographies ───────────────────────────────────────────
    from .merge_utils import find_similar_to

    with transaction.atomic():
        for idx, row in enumerate(rows):
            name = row["full_name_ar"]

            # Apply user date decisions (override auto-parsed values)
            birth_parsed = date_decisions.get(f"{idx}_birth", row["birth_parsed"])
            death_parsed = date_decisions.get(f"{idx}_death", row["death_parsed"])

            # Exact duplicate check only (fuzzy duplicates auto-create a new bio)
            existing = None
            similar = find_similar_to(name)
            if similar:
                top_stub, match_type, _, similarity = similar[0]
                if match_type == "cross_field" and similarity == 1.0:
                    try:
                        existing = Biography.objects.get(pk=top_stub.pk)
                    except Biography.DoesNotExist:
                        pass

            bio = existing or Biography()
            is_new = existing is None

            bio.full_name_ar = name
            if row["alias_ar"]:
                bio.alias_ar = row["alias_ar"]

            # Published status
            if published_mode == "published":
                bio.published = True
            elif published_mode == "unpublished":
                if is_new:
                    bio.published = False
            else:
                bio.published = _is_approved(row["status_raw"])

            # Source note → append to comments_ar
            if row["source_raw"] and row["source_raw"] not in ("-", "–"):
                note = f"المصدر: {row['source_raw']}"
                if note not in (bio.comments_ar or ""):
                    bio.comments_ar = (
                        (bio.comments_ar + "\n" + note) if bio.comments_ar else note
                    ).strip()

            # Dates
            for prefix, parsed in [("birth", birth_parsed), ("death", death_parsed)]:
                setattr(bio, f"{prefix}_date_raw_ar", parsed["raw"])
                if parsed["calendar"] is None or parsed["year"] is None:
                    continue
                cal = "hijri" if parsed["calendar"] == "hijri" else "greg"
                year_field = f"{prefix}_{cal}_year"
                if is_new or not getattr(bio, year_field):
                    setattr(bio, year_field, parsed["year"])
                    setattr(bio, f"{prefix}_{cal}_month", parsed["month"])
                    setattr(bio, f"{prefix}_{cal}_day", parsed["day"])
                    setattr(bio, f"{prefix}_{cal}_approximate", parsed["approximate"])

            # Locations
            for loc_key, field_name in [("birth_loc", "birthplace"), ("death_loc", "death_location")]:
                raw_loc = row.get(loc_key)
                if not raw_loc:
                    continue
                city_ar = raw_loc["city_ar"]
                country_ar = raw_loc["country_ar"]
                # Apply user location decision
                if row.get(f"{loc_key}_needs_country") and city_ar in location_decisions:
                    decided = location_decisions[city_ar]
                    city_ar = decided.get("city_ar", city_ar)
                    country_ar = decided.get("country_ar", "")
                if city_ar or country_ar:
                    loc_obj = resolve_location(city_ar, country_ar)
                    if loc_obj and (is_new or not getattr(bio, field_name + "_id")):
                        setattr(bio, field_name, loc_obj)

            bio.save()

            # Attributes (M2M)
            attrs_to_add = list(row.get("attr_exact_pks", []))
            all_req_names = (
                [item["name"] for item in row.get("attr_fuzzy", [])]
                + row.get("attr_missing", [])
            )
            for attr_name in all_req_names:
                pk = pending_attr_pks.get(attr_name)
                if pk:
                    attrs_to_add.append(pk)
            if attrs_to_add:
                bio.attributes.add(*attrs_to_add)

            bio_map[bio.full_name_ar] = bio.pk
            stats["created" if is_new else "updated"] += 1

    # ── Phase 4: Teacher / Student linking ────────────────────────────────────
    # Load all bios into memory for fast in-memory matching (avoids N+1 queries).
    all_bios = list(Biography.objects.values_list("id", "full_name_ar", "alias_ar"))
    name_to_pk = {}
    norm_to_pk = {}
    norm_list = []  # [(normalized_name, pk)] for fuzzy iteration
    for pk, full_name, alias in all_bios:
        if full_name:
            name_to_pk[full_name] = pk
            n = normalize_arabic(full_name)
            norm_to_pk[n] = pk
            norm_list.append((n, pk))
        if alias:
            na = normalize_arabic(alias)
            if na not in norm_to_pk:
                norm_to_pk[na] = pk
                norm_list.append((na, pk))

    def find_bio_pk(person_name):
        if person_name in name_to_pk:
            return name_to_pk[person_name]
        norm = normalize_arabic(person_name)
        if norm in norm_to_pk:
            return norm_to_pk[norm]
        if teacher_fuzzy_mode == "auto":
            best_score, best_pk = 0.0, None
            for bio_norm, bio_pk in norm_list:
                if not bio_norm:
                    continue
                score = difflib.SequenceMatcher(None, norm, bio_norm).ratio()
                if score > best_score:
                    best_score, best_pk = score, bio_pk
            if best_score >= 0.85:
                return best_pk
        return None

    for idx, row in enumerate(rows):
        if row["full_name_ar"] not in bio_map:
            continue
        student_pk = bio_map[row["full_name_ar"]]

        for role, raw_key in [("teacher", "teachers_raw"), ("student", "students_raw")]:
            for person_name in _split_names(row.get(raw_key, "")):
                if not person_name:
                    continue

                matched_pk = find_bio_pk(person_name)

                if matched_pk is None:
                    if teacher_fuzzy_mode == "skip":
                        continue
                    stub, created = Biography.objects.get_or_create(
                        full_name_ar=person_name,
                        defaults={"published": False},
                    )
                    if created:
                        stats["stub_bios"] += 1
                        name_to_pk[person_name] = stub.pk
                        n = normalize_arabic(person_name)
                        norm_to_pk[n] = stub.pk
                        norm_list.append((n, stub.pk))
                    matched_pk = stub.pk

                teacher_pk = matched_pk if role == "teacher" else student_pk
                actual_student_pk = student_pk if role == "teacher" else matched_pk
                if teacher_pk != actual_student_pk:
                    _, created = TeacherStudentRelationship.objects.get_or_create(
                        teacher_id=teacher_pk,
                        student_id=actual_student_pk,
                    )
                    if created:
                        stats["relationships"] += 1

    return dict(stats)
