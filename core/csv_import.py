"""CSV import logic for Biography records.

The importer is intentionally self-contained: parsing, matching against
existing rows, building a website-vs-import diff, and committing all live here
so the admin view stays thin. See ``BiographyAdmin`` for how it is wired in.

Workflow
--------
1. Upload a CSV. ``parse_csv`` turns it into a list of plain dict rows.
2. ``analyze_rows`` classifies every row against the database:
   ``new`` / ``identical`` / ``conflict`` / ``ambiguous`` / ``error``.
3. The review page renders the diffs; the user resolves each conflict.
4. ``commit_rows`` re-runs the analysis and applies the chosen resolutions
   inside a single transaction.

Empty cells mean "no value provided" — they are never compared and never
overwrite existing data. This gives merge/upsert semantics rather than a
destructive replace.
"""

import csv
import difflib
import io
import re
import unicodedata

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .models import Attribute, Biography, Location


# --- Column definitions --------------------------------------------------

# (field name on Biography, type, human label). Order is preserved in the
# sample CSV header.
SCALAR_FIELDS = [
    ("full_name_ar", "str", _("Full Name (Arabic)")),
    ("full_name_en", "str", _("Full Name (English)")),
    ("alias_ar", "str", _("Alias (Arabic)")),
    ("alias_en", "str", _("Alias (English)")),
    ("birth_hijri_year", "int", _("Birth Year (Hijri)")),
    ("birth_hijri_month", "int", _("Birth Month (Hijri)")),
    ("birth_hijri_day", "int", _("Birth Day (Hijri)")),
    ("birth_greg_year", "int", _("Birth Year (Gregorian)")),
    ("birth_greg_month", "int", _("Birth Month (Gregorian)")),
    ("birth_greg_day", "int", _("Birth Day (Gregorian)")),
    ("death_hijri_year", "int", _("Death Year (Hijri)")),
    ("death_hijri_month", "int", _("Death Month (Hijri)")),
    ("death_hijri_day", "int", _("Death Day (Hijri)")),
    ("death_greg_year", "int", _("Death Year (Gregorian)")),
    ("death_greg_month", "int", _("Death Month (Gregorian)")),
    ("death_greg_day", "int", _("Death Day (Gregorian)")),
    ("comments_ar", "str", _("Comments (Arabic)")),
    ("comments_en", "str", _("Comments (English)")),
    ("published", "bool", _("Published")),
]

# Location FK fields and the CSV sub-columns each one expands into.
LOCATION_FIELDS = [
    ("birthplace", _("Birthplace")),
    ("hometown", _("Hometown")),
    ("death_location", _("Death Location")),
]
LOCATION_SUBCOLS = ["city_ar", "city_en", "country_ar", "country_en"]

# Attributes are matched by short name. Two input styles are supported and
# merged together:
#   * one combined "attributes" column, ';'-separated (compact, good for CSV);
#   * several "attribute_1".."attribute_N" columns, one value each — this is
#     what the Excel template uses so every cell can be a single-pick dropdown.
ATTRIBUTES_COLUMN = "attributes"
ATTRIBUTES_SEPARATOR = ";"
ATTRIBUTE_COLUMN_COUNT = 6
ATTRIBUTE_COLUMNS = [f"attribute_{i}" for i in range(1, ATTRIBUTE_COLUMN_COUNT + 1)]
_ATTRIBUTE_COLUMN_RE = re.compile(r"^attribute_(\d+)$")

# The field Biography rows are matched on when deciding new vs. existing.
MATCH_FIELD = "full_name_ar"

_TRUE_VALUES = {"1", "true", "yes", "y", "t", "نعم", "صح", "x", "✓"}
_FALSE_VALUES = {"0", "false", "no", "n", "f", "لا", "", "-"}


def sample_columns():
    """Ordered list of every CSV header, used for the downloadable template."""
    cols = [name for name, _type, _label in SCALAR_FIELDS]
    for fk_name, _label in LOCATION_FIELDS:
        cols += [f"{fk_name}_{sub}" for sub in LOCATION_SUBCOLS]
    cols += ATTRIBUTE_COLUMNS
    return cols


def _example_row():
    """One fully-filled illustrative row, keyed by column name.

    Every column is populated so the format of each field (numeric dates,
    yes/no flags, ';'-separated attributes, the four location sub-columns) is
    self-documenting. Dates are plain numbers: years are full numbers, months
    are 1-12 and days are 1-31. You may fill only the Hijri or only the
    Gregorian side — the other is derived automatically on save.
    """
    return {
        "full_name_ar": "عاصم بن أبي النجود الأسدي",
        "full_name_en": "Asim ibn Abi al-Najud al-Asadi",
        "alias_ar": "عاصم الكوفي",
        "alias_en": "Asim al-Kufi",
        # Hijri birth (year/month/day). Leave the Gregorian side blank to have
        # it derived, or fill it in too as shown here.
        "birth_hijri_year": "60",
        "birth_hijri_month": "3",
        "birth_hijri_day": "15",
        "birth_greg_year": "680",
        "birth_greg_month": "1",
        "birth_greg_day": "5",
        "death_hijri_year": "127",
        "death_hijri_month": "10",
        "death_hijri_day": "20",
        "death_greg_year": "745",
        "death_greg_month": "8",
        "death_greg_day": "1",
        "comments_ar": "أحد القراء السبعة المشهورين بالكوفة",
        "comments_en": "One of the seven canonical reciters of Kufa",
        "published": "yes",
        # Each location needs at least the Arabic city + Arabic country; the
        # English fields are optional. Unknown locations are created on import.
        "birthplace_city_ar": "الكوفة",
        "birthplace_city_en": "Kufa",
        "birthplace_country_ar": "العراق",
        "birthplace_country_en": "Iraq",
        "hometown_city_ar": "الكوفة",
        "hometown_city_en": "Kufa",
        "hometown_country_ar": "العراق",
        "hometown_country_en": "Iraq",
        "death_location_city_ar": "الكوفة",
        "death_location_city_en": "Kufa",
        "death_location_country_ar": "العراق",
        "death_location_country_en": "Iraq",
        # One attribute per column (matched to existing attributes by short
        # name). The Excel template makes each of these a dropdown.
        "attribute_1": "١٠ك",
        "attribute_2": "قراء الأزهر",
    }


# --- Excel template (with dropdowns) and parsing -------------------------

# CSV sub-columns that should carry a dropdown in the Excel template, mapped to
# which list of existing values feeds them.
_CITY_AR_COLUMNS = [f"{fk}_city_ar" for fk, _l in LOCATION_FIELDS]
_COUNTRY_AR_COLUMNS = [f"{fk}_country_ar" for fk, _l in LOCATION_FIELDS]

# Number of data rows the dropdowns cover in the generated template.
_TEMPLATE_ROWS = 500


def build_template_xlsx():
    """Return the bytes of an .xlsx template whose location/attribute/published
    cells are real Excel dropdowns populated from the database.

    Dropdowns are advisory (no hard validation error) so a brand-new location
    can still be typed in. A hidden 'Lists' sheet holds the option values; the
    filled file can be uploaded straight back — :func:`parse_xlsx` reads it.
    """
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    cols = sample_columns()
    example = _example_row()

    wb = Workbook()
    ws = wb.active
    ws.title = "Biographies"
    ws.append(cols)
    ws.append([example.get(c, "") for c in cols])

    # Hidden sheet holding dropdown option lists.
    lists = wb.create_sheet("Lists")
    cities = sorted({c for c in Location.objects.values_list("city_ar", flat=True) if c})
    countries = sorted({c for c in Location.objects.values_list("country_ar", flat=True) if c})
    attr_names = sorted({
        (a.short_name_ar or a.short_name_en)
        for a in Attribute.objects.all()
        if (a.short_name_ar or a.short_name_en)
    })

    def _write_list(col_idx, header, values):
        letter = get_column_letter(col_idx)
        lists.cell(row=1, column=col_idx, value=header)
        for i, value in enumerate(values, start=2):
            lists.cell(row=i, column=col_idx, value=value)
        if not values:
            return None
        return f"Lists!${letter}$2:${letter}${len(values) + 1}"

    city_ref = _write_list(1, "cities", cities)
    country_ref = _write_list(2, "countries", countries)
    attr_ref = _write_list(3, "attributes", attr_names)
    yesno_ref = _write_list(4, "published", ["yes", "no"])
    lists.sheet_state = "hidden"

    last_row = _TEMPLATE_ROWS + 1  # +1 for the header row

    def _add_dropdown(column_name, source_ref):
        if not source_ref or column_name not in cols:
            return
        letter = get_column_letter(cols.index(column_name) + 1)
        dv = DataValidation(
            type="list", formula1=source_ref, allow_blank=True,
            showErrorMessage=False,  # advisory only — new values may be typed
        )
        dv.add(f"{letter}2:{letter}{last_row}")
        ws.add_data_validation(dv)

    for column_name in _CITY_AR_COLUMNS:
        _add_dropdown(column_name, city_ref)
    for column_name in _COUNTRY_AR_COLUMNS:
        _add_dropdown(column_name, country_ref)
    for column_name in ATTRIBUTE_COLUMNS:
        _add_dropdown(column_name, attr_ref)
    _add_dropdown("published", yesno_ref)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _cell_to_str(value):
    """Render an openpyxl cell value as the trimmed string the parser expects.

    Integers and integer-valued floats lose their decimal point so a year typed
    as 60 doesn't arrive as '60.0'.
    """
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def parse_xlsx(uploaded_file):
    """Read an uploaded .xlsx into the same ``[{header: cell}]`` shape as
    :func:`parse_csv`. Reads the 'Biographies' sheet if present, else the
    first sheet."""
    from openpyxl import load_workbook

    try:
        wb = load_workbook(uploaded_file, read_only=True, data_only=True)
    except Exception:
        raise CSVImportError(_("The file could not be read as an Excel workbook."))

    ws = wb["Biographies"] if "Biographies" in wb.sheetnames else wb.worksheets[0]
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header = next(rows_iter)
    except StopIteration:
        raise CSVImportError(_("The file is empty."))

    headers = [_cell_to_str(h) for h in header]
    if MATCH_FIELD not in headers:
        raise CSVImportError(
            _("The sheet must contain a '%(col)s' column.") % {"col": MATCH_FIELD}
        )

    rows = []
    for raw in rows_iter:
        row = {}
        for key, value in zip(headers, raw):
            if not key:
                continue
            row[key] = _cell_to_str(value)
        if any(row.values()):
            rows.append(row)
    return rows


def parse_upload(uploaded_file):
    """Dispatch to the CSV or XLSX parser based on the uploaded file's name."""
    name = (getattr(uploaded_file, "name", "") or "").lower()
    if name.endswith(".xlsx"):
        return parse_xlsx(uploaded_file)
    return parse_csv(uploaded_file)


# --- Parsing -------------------------------------------------------------

class CSVImportError(Exception):
    """Raised for problems that abort the whole import (bad file/headers)."""


def parse_csv(uploaded_file):
    """Read an uploaded CSV into a list of ``{header: cell}`` dicts.

    Uses ``utf-8-sig`` so files exported from Excel (which prepend a BOM) work.
    Raises :class:`CSVImportError` for unreadable files or a missing match
    column.
    """
    try:
        raw = uploaded_file.read()
        text = raw.decode("utf-8-sig")
    except (UnicodeDecodeError, AttributeError):
        raise CSVImportError(_("The file could not be read as UTF-8 text."))

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise CSVImportError(_("The file is empty."))

    headers = [(h or "").strip() for h in reader.fieldnames]
    if MATCH_FIELD not in headers:
        raise CSVImportError(
            _("The CSV must contain a '%(col)s' column.") % {"col": MATCH_FIELD}
        )

    rows = []
    for raw_row in reader:
        # Normalise keys (strip header whitespace/BOM) and values.
        row = {}
        for key, value in raw_row.items():
            if key is None:
                continue
            row[key.strip()] = (value or "").strip()
        # Skip fully blank lines.
        if any(row.values()):
            rows.append(row)
    return rows


# --- Value coercion ------------------------------------------------------

def _coerce(value, field_type):
    """Return ``(parsed, provided, error)`` for a single cell.

    ``provided`` is False for empty cells, which are then ignored everywhere.
    """
    if value is None or value.strip() == "":
        return None, False, None
    value = value.strip()
    if field_type == "int":
        try:
            return int(value), True, None
        except ValueError:
            return None, True, _("'%(v)s' is not a whole number.") % {"v": value}
    if field_type == "bool":
        low = value.casefold()
        if low in _TRUE_VALUES:
            return True, True, None
        if low in _FALSE_VALUES:
            return False, True, None
        return None, True, _("'%(v)s' is not a yes/no value.") % {"v": value}
    return value, True, None


def _location_from_row(row, fk_name):
    """Extract a location spec for ``fk_name`` from a row.

    Returns ``(spec, error)`` where ``spec`` is a dict of the four sub-fields
    or None if no location was provided for this FK.
    """
    sub = {col: row.get(f"{fk_name}_{col}", "").strip() for col in LOCATION_SUBCOLS}
    if not any(sub.values()):
        return None, None
    if not sub["city_ar"] or not sub["country_ar"]:
        return None, _(
            "%(fk)s needs both an Arabic city and Arabic country."
        ) % {"fk": fk_name}
    return sub, None


def _location_label(spec):
    return f"{spec['city_ar']} - {spec['country_ar']}"


def _existing_location_label(loc):
    if loc is None:
        return ""
    return f"{loc.city_ar} - {loc.country_ar}"


# --- Fuzzy location matching --------------------------------------------

# Below this combined similarity an existing location is not offered as a
# candidate for a typed-but-unmatched location.
LOCATION_MATCH_THRESHOLD = 0.8


def _normalize_ar(text):
    """Normalise Arabic text for typo-tolerant matching.

    Strips diacritics and tatweel, unifies alef/hamza/ya/ta-marbuta variants,
    and drops a leading definite article ('ال') so that e.g. 'قاهرة' and
    'القاهرة' compare equal.
    """
    if not text:
        return ""
    text = text.strip()
    # Decompose then drop combining marks — this also folds أ إ آ ؤ ئ to bare forms.
    text = "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )
    text = (
        text.replace("ى", "ي")
        .replace("ة", "ه")
        .replace("ـ", "")  # tatweel
    )
    if text.startswith("ال") and len(text) > 3:
        text = text[2:]
    return text.casefold()


def _get_or_create_location(spec):
    loc, _created = Location.objects.get_or_create(
        country_ar=spec["country_ar"],
        city_ar=spec["city_ar"],
        defaults={
            "city_en": spec.get("city_en", ""),
            "country_en": spec.get("country_en", ""),
        },
    )
    return loc


def _find_location_candidates(spec, all_locations, limit=5):
    """Return ``[(score, normalized_exact, Location), ...]`` for existing
    locations similar to ``spec`` (city weighted more than country)."""
    ncity = _normalize_ar(spec["city_ar"])
    ncountry = _normalize_ar(spec["country_ar"])
    scored = []
    for loc in all_locations:
        lc_city = _normalize_ar(loc.city_ar)
        lc_country = _normalize_ar(loc.country_ar)
        norm_exact = (ncity == lc_city and ncountry == lc_country)
        if norm_exact:
            score = 1.0
        else:
            city_ratio = difflib.SequenceMatcher(None, ncity, lc_city).ratio()
            country_ratio = difflib.SequenceMatcher(None, ncountry, lc_country).ratio()
            score = city_ratio * 0.7 + country_ratio * 0.3
        if score >= LOCATION_MATCH_THRESHOLD:
            scored.append((score, norm_exact, loc))
    scored.sort(key=lambda row: row[0], reverse=True)
    return scored[:limit]


def collect_location_specs(plans):
    """Gather every distinct location typed across all importable rows and
    classify each as an exact DB match or a new one (with fuzzy suggestions).

    Returns an ordered list of dicts with stable ``index`` values so the review
    form and the commit step agree on which choice maps to which location.
    """
    seen = {}
    for plan in plans:
        if plan.status in ("error", "ambiguous"):
            continue
        for _fk_name, spec in plan.locations.items():
            seen[(spec["country_ar"], spec["city_ar"])] = spec

    all_locations = list(Location.objects.all())
    specs = []
    for index, key in enumerate(sorted(seen.keys())):
        spec = seen[key]
        exact = next(
            (l for l in all_locations
             if l.country_ar == spec["country_ar"] and l.city_ar == spec["city_ar"]),
            None,
        )
        if exact is not None:
            specs.append({"index": index, "key": key, "spec": spec,
                          "status": "exact", "existing": exact,
                          "candidates": [], "suggested": None})
            continue
        scored = _find_location_candidates(spec, all_locations)
        suggested = next((loc for _s, norm_exact, loc in scored if norm_exact), None)
        specs.append({
            "index": index, "key": key, "spec": spec, "status": "new",
            "label": _location_label(spec),
            "candidates": [{"score": round(s, 2), "loc": loc} for s, _ne, loc in scored],
            "suggested": suggested,
        })
    return specs


def resolve_locations(plans, location_choices):
    """Build a ``{(country_ar, city_ar): Location}`` map applying the user's
    per-location choices. ``location_choices`` maps a spec index to ``"new"``
    or an existing Location pk."""
    resolved = {}
    for s in collect_location_specs(plans):
        if s["status"] == "exact":
            resolved[s["key"]] = s["existing"]
            continue
        choice = location_choices.get(s["index"])
        if choice is None:
            # Match the review page default: prefer a typo-equivalent existing
            # location, otherwise create a new one.
            resolved[s["key"]] = s["suggested"] or _get_or_create_location(s["spec"])
        elif choice == "new":
            resolved[s["key"]] = _get_or_create_location(s["spec"])
        else:
            loc = Location.objects.filter(pk=choice).first()
            resolved[s["key"]] = loc or _get_or_create_location(s["spec"])
    return resolved


# --- Analysis ------------------------------------------------------------

class RowPlan:
    """Classified, validated view of one CSV row."""

    def __init__(self, index, name):
        self.index = index          # 1-based, for display
        self.name = name
        self.status = "new"         # new|identical|conflict|ambiguous|potential_duplicate|error
        self.errors = []
        self.warnings = []
        self.scalars = {}           # field -> parsed value (provided only)
        self.locations = {}         # fk_name -> spec dict (provided only)
        self.attribute_names = []   # raw names requested
        self.existing_pk = None
        self.diffs = []             # [{label, existing, importv}] for conflicts


def _collect_attribute_names(row):
    """Gather attribute short names from a row, merging the combined
    ';'-separated ``attributes`` column with the per-cell ``attribute_N``
    columns. Order follows the combined column then ascending N; duplicates
    (case-insensitive) are dropped."""
    names, seen = [], set()

    def add(raw):
        for part in (raw or "").split(ATTRIBUTES_SEPARATOR):
            part = part.strip()
            if part and part.casefold() not in seen:
                seen.add(part.casefold())
                names.append(part)

    add(row.get(ATTRIBUTES_COLUMN, ""))
    numbered = []
    for key, value in row.items():
        match = _ATTRIBUTE_COLUMN_RE.match(key or "")
        if match:
            numbered.append((int(match.group(1)), value))
    for _n, value in sorted(numbered, key=lambda pair: pair[0]):
        add(value)
    return names


def _match_attributes(names):
    """Resolve attribute short names to Attribute objects.

    Returns ``(objects, missing_names)``. Matching is case-insensitive against
    both the Arabic and English short names.
    """
    objects, missing = [], []
    for name in names:
        obj = (
            Attribute.objects.filter(short_name_ar__iexact=name).first()
            or Attribute.objects.filter(short_name_en__iexact=name).first()
        )
        if obj:
            objects.append(obj)
        else:
            missing.append(name)
    return objects, missing


def analyze_rows(rows):
    """Classify every parsed row against the database. Returns a list of
    :class:`RowPlan`. This is pure analysis — no writes occur here."""
    plans = []
    for i, row in enumerate(rows, start=1):
        name = row.get(MATCH_FIELD, "").strip()
        plan = RowPlan(i, name)

        if not name:
            plan.status = "error"
            plan.errors.append(_("Missing '%(col)s'.") % {"col": MATCH_FIELD})
            plans.append(plan)
            continue

        # Scalar fields.
        for field, ftype, _label in SCALAR_FIELDS:
            parsed, provided, error = _coerce(row.get(field, ""), ftype)
            if error:
                plan.errors.append(f"{field}: {error}")
            elif provided:
                plan.scalars[field] = parsed

        # Locations.
        for fk_name, _label in LOCATION_FIELDS:
            spec, error = _location_from_row(row, fk_name)
            if error:
                plan.errors.append(error)
            elif spec:
                plan.locations[fk_name] = spec

        # Attributes (warn-only when unmatched).
        plan.attribute_names = _collect_attribute_names(row)
        if plan.attribute_names:
            _objs, missing = _match_attributes(plan.attribute_names)
            for m in missing:
                plan.warnings.append(
                    _("Attribute '%(name)s' not found — it will be skipped.")
                    % {"name": m}
                )

        if plan.errors:
            plan.status = "error"
            plans.append(plan)
            continue

        # Match against existing biographies.
        matches = list(Biography.objects.filter(**{MATCH_FIELD: name}))
        if len(matches) > 1:
            plan.status = "ambiguous"
            plan.warnings.append(
                _("%(n)d existing biographies share this name — row skipped.")
                % {"n": len(matches)}
            )
            plans.append(plan)
            continue
        if not matches:
            # Check for partial / cross-field / fuzzy near-matches so the user
            # can review potential duplicates before committing a new record.
            from .merge_utils import find_similar_to
            similar = find_similar_to(name)
            if similar:
                plan.status = "potential_duplicate"
                for bio, match_type, match_fields, similarity in similar[:3]:
                    sim_pct = int(similarity * 100)
                    plan.warnings.append(
                        _(
                            "Similar biography already exists: #%(id)d %(name)s"
                            " (match: %(type)s, %(pct)d%%)"
                        ) % {
                            "id": bio.pk,
                            "name": bio.full_name_ar,
                            "type": match_type,
                            "pct": sim_pct,
                        }
                    )
                plan.similar_bios = [(bio, match_type, match_fields, similarity)
                                     for bio, match_type, match_fields, similarity in similar[:3]]
            else:
                plan.status = "new"
            plans.append(plan)
            continue

        existing = matches[0]
        plan.existing_pk = existing.pk
        plan.diffs = _build_diffs(plan, existing)
        plan.status = "conflict" if plan.diffs else "identical"
        plans.append(plan)

    return plans


def _build_diffs(plan, existing):
    """Compare provided values against ``existing``; return changed fields."""
    diffs = []

    for field, ftype, label in SCALAR_FIELDS:
        if field not in plan.scalars:
            continue
        new_val = plan.scalars[field]
        old_val = getattr(existing, field)
        if _normalize(old_val, ftype) != _normalize(new_val, ftype):
            diffs.append({
                "label": label,
                "existing": _display(old_val, ftype),
                "importv": _display(new_val, ftype),
            })

    for fk_name, label in LOCATION_FIELDS:
        if fk_name not in plan.locations:
            continue
        spec = plan.locations[fk_name]
        old_loc = getattr(existing, fk_name)
        if _existing_location_label(old_loc) != _location_label(spec):
            diffs.append({
                "label": label,
                "existing": _existing_location_label(old_loc) or "—",
                "importv": _location_label(spec),
            })

    if plan.attribute_names:
        objs, _missing = _match_attributes(plan.attribute_names)
        new_set = sorted(o.pk for o in objs)
        old_set = sorted(existing.attributes.values_list("pk", flat=True))
        if new_set != old_set:
            diffs.append({
                "label": _("Attributes"),
                "existing": ", ".join(str(a) for a in existing.attributes.all()) or "—",
                "importv": ", ".join(str(o) for o in objs) or "—",
            })

    return diffs


def _normalize(value, ftype):
    if ftype == "bool":
        return bool(value)
    if ftype == "int":
        return value if value is not None else None
    return (value or "").strip()


def _display(value, ftype):
    if ftype == "bool":
        return _("Yes") if value else _("No")
    if value in (None, ""):
        return "—"
    return str(value)


# --- Commit --------------------------------------------------------------

def _apply_plan(plan, instance, user, location_map):
    """Write a plan's provided values onto ``instance`` (unsaved/loaded).

    ``location_map`` maps a ``(country_ar, city_ar)`` key to the resolved
    Location chosen during review. Returns (attrs, hometown_loc) where attrs
    is the list of Attribute objects to set after save (M2M requires a PK) and
    hometown_loc is the resolved Location for the hometown M2M field (or None).
    """
    for field, value in plan.scalars.items():
        setattr(instance, field, value)

    hometown_loc = None
    for fk_name, spec in plan.locations.items():
        key = (spec["country_ar"], spec["city_ar"])
        loc = location_map.get(key) or _get_or_create_location(spec)
        if fk_name == "hometown":
            hometown_loc = loc
        else:
            setattr(instance, fk_name, loc)

    if instance.pk is None:
        instance.submitted_by = user
    instance.last_modified_by = user

    attrs, _missing = _match_attributes(plan.attribute_names)
    return attrs, hometown_loc


def commit_rows(rows, resolutions, user, location_choices=None):
    """Apply the import. ``resolutions`` maps a row index (int) to one of
    ``"import"`` / ``"existing"`` / ``"skip"``; new rows use ``"import"`` to
    create or ``"skip"`` to omit. ``location_choices`` maps a location spec
    index to ``"new"`` or an existing Location pk.

    Returns a summary dict with created/updated/skipped/error counts.
    """
    plans = analyze_rows(rows)
    location_map = resolve_locations(plans, location_choices or {})
    created = updated = skipped = errors = 0

    with transaction.atomic():
        for plan in plans:
            if plan.status == "error" or plan.status == "ambiguous":
                errors += 1 if plan.status == "error" else 0
                skipped += 1 if plan.status == "ambiguous" else 0
                continue

            if plan.status == "identical":
                skipped += 1
                continue

            choice = resolutions.get(
                plan.index,
                "import" if plan.status in ("new", "potential_duplicate") else "existing",
            )

            if plan.status in ("new", "potential_duplicate"):
                if choice != "import":
                    skipped += 1
                    continue
                instance = Biography()
                attrs, hometown_loc = _apply_plan(plan, instance, user, location_map)
                instance.save()
                if plan.attribute_names:
                    instance.attributes.set(attrs)
                if hometown_loc is not None:
                    instance.hometown.set([hometown_loc])
                created += 1
                continue

            # conflict
            if choice != "import":
                skipped += 1
                continue
            instance = Biography.objects.get(pk=plan.existing_pk)
            attrs, hometown_loc = _apply_plan(plan, instance, user, location_map)
            instance.save()
            if plan.attribute_names:
                instance.attributes.set(attrs)
            if hometown_loc is not None:
                instance.hometown.set([hometown_loc])
            updated += 1

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "total": len(plans),
    }
