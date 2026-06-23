from django.db import migrations, models


def copy_fk_to_m2m(apps, schema_editor):
    Biography = apps.get_model("core", "Biography")
    for bio in Biography.objects.filter(hometown_fk__isnull=False).iterator():
        bio.hometown.add(bio.hometown_fk_id)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0030_remove_note_description_ar_and_more"),
    ]

    operations = [
        # 1. Rename the existing FK so we can free the field name.
        migrations.RenameField(
            model_name="biography",
            old_name="hometown",
            new_name="hometown_fk",
        ),
        # 2. Add the new M2M field.
        migrations.AddField(
            model_name="biography",
            name="hometown",
            field=models.ManyToManyField(
                blank=True,
                related_name="hometown",
                to="core.location",
                verbose_name="Hometown",
            ),
        ),
        # 3. Migrate existing FK data into the M2M table.
        migrations.RunPython(copy_fk_to_m2m, migrations.RunPython.noop),
        # 4. Drop the old FK column.
        migrations.RemoveField(
            model_name="biography",
            name="hometown_fk",
        ),
    ]
