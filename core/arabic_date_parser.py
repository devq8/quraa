"""
Parse mixed-format Arabic date strings into structured date components.

Handles Hijri and Gregorian dates, month names, day/month/year combinations,
and a variety of approximation qualifiers found in Islamic biographical sources.
"""

import re

# Arabic Hijri month names mapped to month numbers (1–12).
# Each entry lists all accepted spellings for that month.
_HIJRI_MONTHS = {
    "محرم": 1,
    "صفر": 2,
    "ربيع الأول": 3,
    "ربيع الآخر": 4,
    "ربيع الثاني": 4,
    "جمادى الأولى": 5,
    "جمادى الأول": 5,
    "جمادى الآخرة": 6,
    "جمادى الثانية": 6,
    "جمادى الثاني": 6,
    "رجب": 7,
    "شعبان": 8,
    "رمضان": 9,
    "شوال": 10,
    "ذو القعدة": 11,
    "ذى القعدة": 11,
    "ذي القعدة": 11,
    "ذو الحجة": 12,
    "ذى الحجة": 12,
    "ذي الحجة": 12,
}

# Sort by length descending so longer names are matched before shorter substrings.
_HIJRI_MONTH_PATTERNS = sorted(_HIJRI_MONTHS.keys(), key=len, reverse=True)

# Approximate qualifiers — presence of any of these marks the date as approximate.
_APPROXIMATE_MARKERS = [
    "نحو",
    "حوالي",
    "وقيل",
    "قيل",
    "بضع",
    "تقريبا",
    "تقريباً",
    "نحوه",
]

# Regex matching a Hijri year suffix (هـ) or common variants.
_HIJRI_RE = re.compile(r"(\d+)\s*ه[ـ]?")

# Regex matching a Gregorian year suffix (م) as a word boundary.
_GREG_RE = re.compile(r"(\d{4})\s*م(?:\b|$)")

# Regex matching a bare 4-digit number that looks like a Gregorian year (≥ 1900).
_BARE_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")

# Regex matching a leading day number before a month name.
_DAY_RE = re.compile(r"^\s*(\d{1,2})\s+")


def parse_arabic_date(text: str) -> dict:
    """
    Parse an Arabic date string into structured components.

    Returns a dict with keys:
        calendar  : 'hijri' | 'gregorian' | None
        year      : int | None
        month     : int | None   (1–12)
        day       : int | None
        approximate: bool
        raw       : str          (original input, always preserved)
    """
    raw = text.strip() if text else ""
    result = {
        "calendar": None,
        "year": None,
        "month": None,
        "day": None,
        "approximate": False,
        "raw": raw,
    }

    if not raw or raw in ("-", "–", "—", "?", "؟"):
        return result

    # --- Detect approximate qualifiers ---
    for marker in _APPROXIMATE_MARKERS:
        if marker in raw:
            result["approximate"] = True
            break

    # --- Detect calendar and extract year ---
    hijri_match = _HIJRI_RE.search(raw)
    greg_match = _GREG_RE.search(raw)

    if hijri_match:
        result["calendar"] = "hijri"
        result["year"] = int(hijri_match.group(1))
    elif greg_match:
        result["calendar"] = "gregorian"
        result["year"] = int(greg_match.group(1))
    else:
        bare = _BARE_YEAR_RE.search(raw)
        if bare:
            result["calendar"] = "gregorian"
            result["year"] = int(bare.group(1))
        elif _has_any_arabic(raw):
            # Free Arabic text with no detectable year — mark Hijri and approximate.
            result["calendar"] = "hijri"
            result["approximate"] = True
            return result
        else:
            return result

    # --- Extract month name ---
    remaining = raw
    for name in _HIJRI_MONTH_PATTERNS:
        if name in remaining:
            result["month"] = _HIJRI_MONTHS[name]
            # Check for a leading day number before the month name.
            before = remaining[: remaining.index(name)]
            day_match = _DAY_RE.search(before[::-1])  # search from right
            if not day_match:
                # Standard left-to-right scan of the text before the month.
                day_match = re.search(r"(\d{1,2})\s*$", before.strip())
            if day_match:
                result["day"] = int(day_match.group(1))
            break

    return result


def _has_any_arabic(text: str) -> bool:
    return bool(re.search(r"[؀-ۿ]", text))
