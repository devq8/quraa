"""Duplicate detection and merge logic for Biography records.

Detection passes (ordered by confidence):
  1. exact         — normalize_arabic(full_name_ar) matches exactly
  2. cross_field   — any normalized name field of A equals any of B
  3. partial       — one normalized name is a substring of another (≥5 chars)
  4. fuzzy         — SequenceMatcher ratio ≥ threshold (opt-in)

Merge:
  - scalar fields: copy from duplicate to primary only when primary is empty,
    except conflict fields where the user explicitly picks which value to keep.
  - M2M (attributes, hometown): always union — no data is ever lost.
  - TeacherStudentRelationship: re-point both sides to primary, merging notes.
  - Source / Esnad / EsnadLink / EsnadTemplateLink: re-point FK to primary.
"""

import difflib
from dataclasses import dataclass, field
from typing import Any

from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _

from .search import normalize_arabic


NAME_FIELDS = ["full_name_ar", "alias_ar", "full_name_en", "alias_en"]

SCALAR_CONFLICT_FIELDS = [
    ("full_name_ar",        _("Full Name (Arabic)")),
    ("full_name_en",        _("Full Name (English)")),
    ("alias_ar",            _("Alias (Arabic)")),
    ("alias_en",            _("Alias (English)")),
    ("comments_ar",         _("Comments (Arabic)")),
    ("comments_en",         _("Comments (English)")),
    ("birthplace_id",       _("Birthplace")),
    ("death_location_id",   _("Death Location")),
    ("birth_hijri_year",    _("Birth Year (Hijri)")),
    ("birth_hijri_month",   _("Birth Month (Hijri)")),
    ("birth_hijri_day",     _("Birth Day (Hijri)")),
    ("birth_greg_year",     _("Birth Year (Gregorian)")),
    ("birth_greg_month",    _("Birth Month (Gregorian)")),
    ("birth_greg_day",      _("Birth Day (Gregorian)")),
    ("death_hijri_year",    _("Death Year (Hijri)")),
    ("death_hijri_month",   _("Death Month (Hijri)")),
    ("death_hijri_day",     _("Death Day (Hijri)")),
    ("death_greg_year",     _("Death Year (Gregorian)")),
    ("death_greg_month",    _("Death Month (Gregorian)")),
    ("death_greg_day",      _("Death Day (Gregorian)")),
]


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

@dataclass
class DuplicateCandidate:
    bio_a: Any
    bio_b: Any
    match_type: str   # "exact" | "cross_field" | "partial" | "fuzzy"
    match_fields: tuple
    similarity: float


def build_duplicate_candidates(fuzzy=False, threshold=0.85):
    """Return a list of DuplicateCandidate pairs (each pair appears once).

    Sorted highest-confidence first: exact → cross_field → partial → fuzzy.
    """
    from .models import Biography

    rows = list(
        Biography.objects.values_list("id", "full_name_ar", "full_name_en", "alias_ar", "alias_en")
    )
    bio_map = {row[0]: row for row in rows}

    class _BioStub:
        __slots__ = ("pk", "full_name_ar", "full_name_en", "alias_ar", "alias_en")
        def __init__(self, row):
            self.pk, self.full_name_ar, self.full_name_en, self.alias_ar, self.alias_en = row

    stubs = [_BioStub(row) for row in rows]

    seen_pairs = set()
    candidates = []

    def _add(bio_a, bio_b, match_type, match_fields, similarity):
        key = (min(bio_a.pk, bio_b.pk), max(bio_a.pk, bio_b.pk))
        if key in seen_pairs:
            return
        seen_pairs.add(key)
        candidates.append(DuplicateCandidate(bio_a, bio_b, match_type, match_fields, similarity))

    def _norm_fields(bio):
        return {f: normalize_arabic(getattr(bio, f) or "") for f in NAME_FIELDS}

    norm_map = {bio.pk: _norm_fields(bio) for bio in stubs}
    bios = stubs

    # Pass 1 — exact normalized full_name_ar match
    from collections import defaultdict
    by_norm_name = defaultdict(list)
    for bio in bios:
        key = norm_map[bio.pk]["full_name_ar"]
        if key:
            by_norm_name[key].append(bio)

    for group in by_norm_name.values():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                _add(group[i], group[j], "exact", ("full_name_ar", "full_name_ar"), 1.0)

    # Pass 2 — cross-field exact match (any field of A == any field of B)
    for i, bio_a in enumerate(bios):
        for j in range(i + 1, len(bios)):
            bio_b = bios[j]
            pair_key = (min(bio_a.pk, bio_b.pk), max(bio_a.pk, bio_b.pk))
            if pair_key in seen_pairs:
                continue
            norms_a = norm_map[bio_a.pk]
            norms_b = norm_map[bio_b.pk]
            for fa in NAME_FIELDS:
                val_a = norms_a[fa]
                if not val_a:
                    continue
                for fb in NAME_FIELDS:
                    val_b = norms_b[fb]
                    if not val_b:
                        continue
                    if val_a == val_b:
                        _add(bio_a, bio_b, "cross_field", (fa, fb), 1.0)
                        break
                if pair_key in seen_pairs:
                    break

    # Pass 3 — partial/substring match (shorter is substring of longer, ≥5 chars)
    for i, bio_a in enumerate(bios):
        for j in range(i + 1, len(bios)):
            bio_b = bios[j]
            pair_key = (min(bio_a.pk, bio_b.pk), max(bio_a.pk, bio_b.pk))
            if pair_key in seen_pairs:
                continue
            norms_a = norm_map[bio_a.pk]
            norms_b = norm_map[bio_b.pk]
            for fa in NAME_FIELDS:
                val_a = norms_a[fa]
                if len(val_a) < 5:
                    continue
                for fb in NAME_FIELDS:
                    val_b = norms_b[fb]
                    if len(val_b) < 5:
                        continue
                    if val_a == val_b:
                        continue
                    shorter, longer = (val_a, val_b) if len(val_a) <= len(val_b) else (val_b, val_a)
                    if shorter in longer:
                        sim = len(shorter) / len(longer)
                        _add(bio_a, bio_b, "partial", (fa, fb), sim)
                        break
                if pair_key in seen_pairs:
                    break

    # Pass 4 — fuzzy (opt-in)
    if fuzzy:
        for i, bio_a in enumerate(bios):
            for j in range(i + 1, len(bios)):
                bio_b = bios[j]
                pair_key = (min(bio_a.pk, bio_b.pk), max(bio_a.pk, bio_b.pk))
                if pair_key in seen_pairs:
                    continue
                norms_a = norm_map[bio_a.pk]
                norms_b = norm_map[bio_b.pk]
                best_ratio = 0.0
                best_fields = (NAME_FIELDS[0], NAME_FIELDS[0])
                for fa in NAME_FIELDS:
                    val_a = norms_a[fa]
                    if not val_a:
                        continue
                    for fb in NAME_FIELDS:
                        val_b = norms_b[fb]
                        if not val_b:
                            continue
                        ratio = difflib.SequenceMatcher(None, val_a, val_b).ratio()
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_fields = (fa, fb)
                if best_ratio >= threshold:
                    _add(bio_a, bio_b, "fuzzy", best_fields, best_ratio)

    order = {"exact": 0, "cross_field": 1, "partial": 2, "fuzzy": 3}
    candidates.sort(key=lambda c: (order[c.match_type], -c.similarity))
    return candidates


def find_similar_to(name, exclude_pk=None, threshold=0.85):
    """Return biographies similar to `name` (used during CSV import).

    Checks exact normalized match, cross-field match, and partial match.
    Returns list of (Biography, match_type, match_fields, similarity).
    """
    from .models import Biography

    norm = normalize_arabic(name)
    if not norm:
        return []

    qs = Biography.objects.values_list("id", "full_name_ar", "full_name_en", "alias_ar", "alias_en")
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    class _BioStub:
        __slots__ = ("pk", "full_name_ar", "full_name_en", "alias_ar", "alias_en")
        def __init__(self, row):
            self.pk, self.full_name_ar, self.full_name_en, self.alias_ar, self.alias_en = row

    results = []
    seen = set()

    for row in qs:
        bio = _BioStub(row)
        norms = {f: normalize_arabic(getattr(bio, f) or "") for f in NAME_FIELDS}

        # exact
        for fb in NAME_FIELDS:
            if norms[fb] and norms[fb] == norm:
                results.append((bio, "cross_field", ("full_name_ar", fb), 1.0))
                seen.add(bio.pk)
                break

        if bio.pk in seen:
            continue

        # partial
        for fb in NAME_FIELDS:
            val_b = norms[fb]
            if len(val_b) < 5 or len(norm) < 5:
                continue
            shorter, longer = (norm, val_b) if len(norm) <= len(val_b) else (val_b, norm)
            if shorter in longer:
                sim = len(shorter) / len(longer)
                results.append((bio, "partial", ("full_name_ar", fb), sim))
                seen.add(bio.pk)
                break

        if bio.pk in seen:
            continue

        # fuzzy
        for fb in NAME_FIELDS:
            val_b = norms[fb]
            if not val_b:
                continue
            ratio = difflib.SequenceMatcher(None, norm, val_b).ratio()
            if ratio >= threshold:
                results.append((bio, "fuzzy", ("full_name_ar", fb), ratio))
                seen.add(bio.pk)
                break

    results.sort(key=lambda r: -r[3])
    return results


# ---------------------------------------------------------------------------
# Field conflict analysis
# ---------------------------------------------------------------------------

@dataclass
class FieldResolution:
    field_name: str
    label: str
    value_a: Any
    value_b: Any
    display_a: str
    display_b: str
    status: str  # "same" | "only_a" | "only_b" | "conflict"


def compute_field_resolutions(bio_a, bio_b):
    """Compare bio_a and bio_b field by field.

    Returns a list of FieldResolution objects. The caller uses these to
    build the merge confirmation form and to apply user choices.
    """
    from .models import Location

    resolutions = []

    for field_name, label in SCALAR_CONFLICT_FIELDS:
        val_a = getattr(bio_a, field_name)
        val_b = getattr(bio_b, field_name)

        # For FK _id fields, also provide a readable display value
        if field_name.endswith("_id"):
            display_a = _location_display(val_a)
            display_b = _location_display(val_b)
        else:
            display_a = str(val_a) if val_a else ""
            display_b = str(val_b) if val_b else ""

        has_a = bool(val_a)
        has_b = bool(val_b)

        if not has_a and not has_b:
            continue  # both empty — nothing to show

        if has_a and has_b:
            if val_a == val_b:
                status = "same"
            else:
                status = "conflict"
        elif has_a:
            status = "only_a"
        else:
            status = "only_b"

        resolutions.append(FieldResolution(
            field_name=field_name,
            label=str(label),
            value_a=val_a,
            value_b=val_b,
            display_a=display_a,
            display_b=display_b,
            status=status,
        ))

    return resolutions


def _location_display(pk):
    if not pk:
        return ""
    from .models import Location
    try:
        loc = Location.objects.get(pk=pk)
        return str(loc)
    except Location.DoesNotExist:
        return str(pk)


# ---------------------------------------------------------------------------
# Merge log
# ---------------------------------------------------------------------------

class MergeLog:
    def __init__(self):
        self._entries = []

    def info(self, msg):
        self._entries.append(("info", msg))

    def warning(self, msg):
        self._entries.append(("warning", msg))

    def error(self, msg):
        self._entries.append(("error", msg))

    def has_errors(self):
        return any(level == "error" for level, _ in self._entries)

    def __iter__(self):
        return iter(self._entries)


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def merge_biographies(primary, duplicate, field_choices, *, dry_run=False):
    """Merge duplicate into primary.

    field_choices: dict mapping field_name → "a" or "b" for conflict fields.
    Returns a MergeLog. Raises ValueError for pre-flight errors.
    """
    log = MergeLog()

    if primary.pk == duplicate.pk:
        raise ValueError("Cannot merge a biography with itself.")

    resolutions = compute_field_resolutions(primary, duplicate)

    with transaction.atomic():
        if dry_run:
            transaction.set_rollback(True)

        _apply_field_choices(primary, duplicate, resolutions, field_choices, log, dry_run)
        _merge_m2m(primary, duplicate, log, dry_run)
        _transfer_tsr(primary, duplicate, log, dry_run)
        _transfer_simple_fk(primary, duplicate, log, dry_run)

        if not dry_run:
            dup_pk = duplicate.pk
            duplicate.delete()
            log.info(f"Deleted duplicate Biography #{dup_pk}.")
        else:
            log.info(f"[DRY RUN] Would delete Biography #{duplicate.pk}.")

    return log


def _apply_field_choices(primary, duplicate, resolutions, field_choices, log, dry_run):
    changed = False

    for res in resolutions:
        if res.status == "same":
            continue

        if res.status == "only_a":
            # primary already has the value (bio_a is primary if they were
            # passed in the natural order — but primary may be either bio).
            # We use getattr on primary/duplicate directly.
            if not getattr(primary, res.field_name) and getattr(duplicate, res.field_name):
                val = getattr(duplicate, res.field_name)
                if not dry_run:
                    setattr(primary, res.field_name, val)
                log.info(f"Auto-filled {res.field_name} from duplicate: {res.display_b or val}")
                changed = True
            elif getattr(primary, res.field_name):
                log.info(f"Kept existing {res.field_name} on primary: {res.display_a}")

        elif res.status == "only_b":
            if not getattr(primary, res.field_name) and getattr(duplicate, res.field_name):
                val = getattr(duplicate, res.field_name)
                if not dry_run:
                    setattr(primary, res.field_name, val)
                log.info(f"Auto-filled {res.field_name} from duplicate: {res.display_b or val}")
                changed = True
            elif getattr(primary, res.field_name):
                log.info(f"Kept existing {res.field_name} on primary: {res.display_a}")

        elif res.status == "conflict":
            choice = field_choices.get(res.field_name)
            if choice == "b":
                val = getattr(duplicate, res.field_name)
                if not dry_run:
                    setattr(primary, res.field_name, val)
                log.info(f"Field {res.field_name}: used duplicate value ({res.display_b or val})")
                changed = True
            else:
                log.info(f"Field {res.field_name}: kept primary value ({res.display_a})")

    if changed and not dry_run:
        primary.save()


def _merge_m2m(primary, duplicate, log, dry_run):
    attr_ids = list(duplicate.attributes.values_list("pk", flat=True))
    if attr_ids:
        if not dry_run:
            primary.attributes.add(*attr_ids)
        log.info(f"Merged {len(attr_ids)} attribute(s) from duplicate.")

    hometown_ids = list(duplicate.hometown.values_list("pk", flat=True))
    if hometown_ids:
        if not dry_run:
            primary.hometown.add(*hometown_ids)
        log.info(f"Merged {len(hometown_ids)} hometown location(s) from duplicate.")


def _transfer_tsr(primary, duplicate, log, dry_run):
    from .models import TeacherStudentRelationship as TSR

    teacher_side = list(
        duplicate.student_relationships.prefetch_related("notes").all()
    )
    student_side = list(
        duplicate.teacher_relationships.prefetch_related("notes").all()
    )

    for old_tsr in teacher_side:
        if old_tsr.student_id == primary.pk:
            log.warning(
                f"Skipping TSR #{old_tsr.pk}: would make primary a teacher of themselves."
            )
            if not dry_run:
                old_tsr.delete()
            continue
        note_ids = list(old_tsr.notes.values_list("pk", flat=True))
        if not dry_run:
            new_tsr, created = TSR.objects.get_or_create(
                teacher=primary, student_id=old_tsr.student_id
            )
            if note_ids:
                new_tsr.notes.add(*note_ids)
            old_tsr.delete()
        action = "Would transfer" if dry_run else "Transferred"
        log.info(
            f"{action} teacher relationship: primary → student #{old_tsr.student_id}"
            f" (notes: {note_ids})"
        )

    for old_tsr in student_side:
        if old_tsr.teacher_id == primary.pk:
            log.warning(
                f"Skipping TSR #{old_tsr.pk}: would make primary a student of themselves."
            )
            if not dry_run:
                old_tsr.delete()
            continue
        note_ids = list(old_tsr.notes.values_list("pk", flat=True))
        if not dry_run:
            new_tsr, created = TSR.objects.get_or_create(
                teacher_id=old_tsr.teacher_id, student=primary
            )
            if note_ids:
                new_tsr.notes.add(*note_ids)
            old_tsr.delete()
        action = "Would transfer" if dry_run else "Transferred"
        log.info(
            f"{action} student relationship: teacher #{old_tsr.teacher_id} → primary"
            f" (notes: {note_ids})"
        )


def _transfer_simple_fk(primary, duplicate, log, dry_run):
    if not dry_run:
        count = duplicate.sources.count()
        duplicate.sources.update(biography=primary)
        log.info(f"Transferred {count} source(s).")

        count = duplicate.esnads.count()
        duplicate.esnads.update(biography=primary)
        log.info(f"Transferred {count} esnad(s).")

        for link in list(duplicate.esnad_appearances.all()):
            try:
                with transaction.atomic():
                    link.narrator = primary
                    link.save(update_fields=["narrator"])
            except IntegrityError:
                log.warning(
                    f"EsnadLink #{link.pk} in Esnad #{link.esnad_id} already has primary "
                    f"as narrator — link deleted to avoid duplication."
                )
                link.delete()

        for link in list(duplicate.template_appearances.all()):
            try:
                with transaction.atomic():
                    link.narrator = primary
                    link.save(update_fields=["narrator"])
            except IntegrityError:
                log.warning(
                    f"EsnadTemplateLink #{link.pk} already has primary as narrator — deleted."
                )
                link.delete()
    else:
        log.info(
            f"[DRY RUN] Would transfer sources, esnads, esnad links, template links."
        )

    if duplicate.user_id and duplicate.user_id != getattr(primary, "user_id", None):
        log.warning(
            f"Biography #{duplicate.pk} has a linked user account (user_id={duplicate.user_id}). "
            f"User accounts are not transferred automatically — please reassign manually."
        )
