"""Backfill the normalized ``Country`` / ``City`` rows from the existing
``Location`` text columns and link each ``Location`` to them.

Non-destructive and reversible: the ``city_ar`` / ``country_ar`` / ``city_en`` /
``country_en`` columns are left untouched (they remain correct for display), and
the reverse operation merely nulls the FKs it set.
"""

from django.db import migrations


def _clean(value):
    return (value or "").strip()


def backfill(apps, schema_editor):
    Country = apps.get_model("core", "Country")
    City = apps.get_model("core", "City")
    Location = apps.get_model("core", "Location")

    country_by_name = {}   # name_ar -> Country
    city_by_key = {}       # (country_id, name_ar) -> City

    for loc in Location.objects.all().iterator():
        country_ar = _clean(loc.country_ar)
        city_ar = _clean(loc.city_ar)

        country = None
        if country_ar:
            country = country_by_name.get(country_ar)
            if country is None:
                country, _created = Country.objects.get_or_create(
                    name_ar=country_ar,
                    defaults={"name_en": _clean(loc.country_en)},
                )
                country_by_name[country_ar] = country

        city = None
        if city_ar:
            key = (country.id if country else None, city_ar)
            city = city_by_key.get(key)
            if city is None:
                city, _created = City.objects.get_or_create(
                    country=country, name_ar=city_ar,
                    defaults={"name_en": _clean(loc.city_en)},
                )
                city_by_key[key] = city

        updates = {}
        if country is not None and loc.country_id != country.id:
            updates["country"] = country
        if city is not None and loc.city_id != city.id:
            updates["city"] = city
        if updates:
            for field, obj in updates.items():
                setattr(loc, field, obj)
            loc.save(update_fields=list(updates.keys()))


def unbackfill(apps, schema_editor):
    Location = apps.get_model("core", "Location")
    Location.objects.update(city=None, country=None)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0039_city_country_location_city_city_country_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
