from django.db import migrations


def renumber_esnadlink_order(apps, schema_editor):
    EsnadLink = apps.get_model("core", "EsnadLink")
    Esnad = apps.get_model("core", "Esnad")

    for esnad_id in Esnad.objects.values_list("id", flat=True):
        links = list(
            EsnadLink.objects.filter(esnad_id=esnad_id).order_by("order", "id")
        )
        if not links:
            continue
        if links[0].order == 1 and all(
            link.order == i for i, link in enumerate(links, start=1)
        ):
            continue
        for i, link in enumerate(links, start=1):
            if link.order != i:
                link.order = i
        EsnadLink.objects.bulk_update(links, ["order"])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0025_biography_name_search"),
    ]

    operations = [
        migrations.RunPython(renumber_esnadlink_order, reverse_noop),
    ]
