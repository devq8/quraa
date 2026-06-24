"""Export helpers for Biography records.

The export format intentionally mirrors the CSV/XLSX import template defined
in :mod:`core.csv_import` so administrators can export, edit, and re-import
Biography data with minimal column translation.
"""

import csv
import io

from openpyxl import Workbook

from . import csv_import


SHEET_NAME = "Biographies"


def export_columns():
    """Return the ordered import-compatible export columns."""
    return csv_import.sample_columns()


def optimized_queryset(queryset):
    """Apply relationship loading needed by the exporter."""
    return queryset.select_related("birthplace", "death_location").prefetch_related(
        "hometown", "attributes"
    )


def biography_to_row(biography):
    """Serialize one Biography as an import-compatible plain dict."""
    row = {column: "" for column in export_columns()}

    for field_name, field_type, _label in csv_import.SCALAR_FIELDS:
        value = getattr(biography, field_name)
        row[field_name] = _format_scalar(value, field_type)

    _write_location(row, "birthplace", biography.birthplace)
    _write_location(row, "death_location", biography.death_location)
    _write_location(row, "hometown", _first_hometown(biography))

    attributes = list(biography.attributes.all())[: csv_import.ATTRIBUTE_COLUMN_COUNT]
    for index, attribute in enumerate(attributes, start=1):
        row[f"attribute_{index}"] = attribute.short_name_ar or attribute.short_name_en

    return row


def rows_for_queryset(queryset):
    """Return serialized rows for an optimized Biography queryset."""
    return [biography_to_row(biography) for biography in optimized_queryset(queryset)]


def build_csv(queryset):
    """Return UTF-8-SIG CSV bytes for the supplied Biography queryset."""
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.DictWriter(output, fieldnames=export_columns(), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows_for_queryset(queryset))
    return output.getvalue().encode("utf-8")


def build_xlsx(queryset):
    """Return XLSX bytes for the supplied Biography queryset."""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = SHEET_NAME

    columns = export_columns()
    worksheet.append(columns)
    for row in rows_for_queryset(queryset):
        worksheet.append([row[column] for column in columns])

    worksheet.freeze_panes = "A2"
    for column_cells in worksheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column_cells)
        worksheet.column_dimensions[column_cells[0].column_letter].width = min(
            max(max_length + 2, 12),
            40,
        )

    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def _format_scalar(value, field_type):
    if value in (None, ""):
        return ""
    if field_type == "bool":
        return "yes" if value else "no"
    return value


def _write_location(row, prefix, location):
    if not location:
        return
    row[f"{prefix}_city_ar"] = location.city_ar
    row[f"{prefix}_city_en"] = location.city_en
    row[f"{prefix}_country_ar"] = location.country_ar
    row[f"{prefix}_country_en"] = location.country_en


def _first_hometown(biography):
    """Return the first hometown supported by the import-compatible schema."""
    hometowns = list(biography.hometown.all())
    return hometowns[0] if hometowns else None
