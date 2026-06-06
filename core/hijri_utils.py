"""
Hijri (Islamic) to Gregorian date conversion (approximate, no external packages).

- Year-only: approximate conversion using mean lunar/solar ratio.
- Full date and month+year: same mean lunar month/year lengths from 1 Muharram 1 AH epoch.
"""
import math
from dataclasses import dataclass
from datetime import date, timedelta


# Mean lunar year / mean Gregorian year ≈ 0.97023; epoch offset for 1 AH ≈ 622 CE
_HIJRI_TO_GREGORIAN_RATIO = 0.97023
_EPOCH_OFFSET = 621.57

# 1 Muharram 1 AH (approximate Gregorian date); mean lunar month ≈ 29.53059 days
_HIJRI_EPOCH = date(622, 7, 19)
_MEAN_LUNAR_MONTH_DAYS = 29.53059
_MEAN_LUNAR_YEAR_DAYS = 12 * _MEAN_LUNAR_MONTH_DAYS  # ~354.367


@dataclass(frozen=True)
class HijriToGregorianApprox:
    hijri_year: int
    gregorian_start_year: int
    gregorian_end_year: int
    label: str


def hijri_year_to_gregorian_years_approx(h_year: int) -> HijriToGregorianApprox:
    """
    Map a Hijri year to an approximate Gregorian year range (start/end).

    Returns a frozen dataclass with hijri_year, gregorian_start_year,
    gregorian_end_year (start + 1), and a human-readable label.
    """
    g_start = math.floor(h_year * _HIJRI_TO_GREGORIAN_RATIO + _EPOCH_OFFSET)
    g_end = g_start + 1
    return HijriToGregorianApprox(
        hijri_year=h_year,
        gregorian_start_year=g_start,
        gregorian_end_year=g_end,
        label=f"{h_year} AH ≈ {g_start}/{g_end} CE (approx)",
    )


def hijri_date_to_gregorian(
    h_year: int, h_month: int, h_day: int
) -> date:
    """
    Convert a full Hijri date (year, month, day) to an approximate Gregorian date.

    Uses mean lunar month/year from epoch 1 Muharram 1 AH ≈ 19 July 622 CE.
    No external packages; result is approximate.
    """
    days_since_epoch = (
        (h_year - 1) * _MEAN_LUNAR_YEAR_DAYS
        + (h_month - 1) * _MEAN_LUNAR_MONTH_DAYS
        + (h_day - 1)
    )
    return _HIJRI_EPOCH + timedelta(days=round(days_since_epoch))


@dataclass(frozen=True)
class HijriDate:
    year: int
    month: int
    day: int


def gregorian_date_to_hijri(g_year: int, g_month: int, g_day: int) -> HijriDate:
    """
    Convert a Gregorian date (year, month, day) to an approximate Hijri date.

    Inverse of hijri_date_to_gregorian using the same mean lunar month/year.
    Result is approximate; expect drift of a few days versus exact tabular
    calendars, especially far from the present.
    """
    g = date(g_year, g_month, g_day)
    days_since_epoch = (g - _HIJRI_EPOCH).days
    if days_since_epoch < 0:
        # Pre-Hijra Gregorian dates are not meaningful in this calendar.
        raise ValueError("Gregorian date precedes the Hijri epoch (622-07-19 CE).")
    year_float = days_since_epoch / _MEAN_LUNAR_YEAR_DAYS
    h_year = int(year_float) + 1
    remaining_days = days_since_epoch - (h_year - 1) * _MEAN_LUNAR_YEAR_DAYS
    h_month = int(remaining_days // _MEAN_LUNAR_MONTH_DAYS) + 1
    if h_month > 12:
        h_month = 12
    remaining_days -= (h_month - 1) * _MEAN_LUNAR_MONTH_DAYS
    h_day = int(round(remaining_days)) + 1
    if h_day < 1:
        h_day = 1
    if h_day > 30:
        h_day = 30
    return HijriDate(year=h_year, month=h_month, day=h_day)


@dataclass(frozen=True)
class HijriMonthToGregorianRange:
    """Gregorian date range for a Hijri month (first and last day of that month)."""

    hijri_year: int
    hijri_month: int
    gregorian_first_day: date
    gregorian_last_day: date

    @property
    def label(self) -> str:
        return (
            f"{self.hijri_year}-{self.hijri_month:02d} AH ≈ "
            f"{self.gregorian_first_day.isoformat()} – {self.gregorian_last_day.isoformat()} CE"
        )


def hijri_month_year_to_gregorian(
    h_year: int, h_month: int
) -> HijriMonthToGregorianRange:
    """
    Convert a Hijri month and year (no day) to the approximate Gregorian date range
    spanning the first and last day of that Hijri month.

    Uses the same mean lunar month/year as hijri_date_to_gregorian. No external packages.
    """
    first = hijri_date_to_gregorian(h_year, h_month, 1)
    if h_month == 12:
        first_of_next = hijri_date_to_gregorian(h_year + 1, 1, 1)
    else:
        first_of_next = hijri_date_to_gregorian(h_year, h_month + 1, 1)
    last = first_of_next - timedelta(days=1)
    return HijriMonthToGregorianRange(
        hijri_year=h_year,
        hijri_month=h_month,
        gregorian_first_day=first,
        gregorian_last_day=last,
    )
