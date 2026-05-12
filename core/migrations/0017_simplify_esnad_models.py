from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0016_add_esnad_models"),
    ]

    operations = [
        migrations.RemoveField(model_name="esnad", name="name_ar"),
        migrations.RemoveField(model_name="esnad", name="name_en"),
        migrations.RemoveField(model_name="esnad", name="description_ar"),
        migrations.RemoveField(model_name="esnad", name="description_en"),
        migrations.RemoveField(model_name="esnadlink", name="notes_ar"),
        migrations.RemoveField(model_name="esnadlink", name="notes_en"),
    ]
