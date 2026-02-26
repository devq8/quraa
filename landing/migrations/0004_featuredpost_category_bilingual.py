# Bilingual category for FeaturedPost (Arabic default, English optional)

from django.db import migrations, models


def copy_category_to_ar(apps, schema_editor):
    FeaturedPost = apps.get_model("landing", "FeaturedPost")
    for obj in FeaturedPost.objects.all():
        obj.category_ar = obj.category or ""
        obj.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("landing", "0003_featuredpost_bilingual"),
    ]

    operations = [
        migrations.AddField(
            model_name="featuredpost",
            name="category_ar",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="Category (Arabic)"),
        ),
        migrations.AddField(
            model_name="featuredpost",
            name="category_en",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="Category (English)"),
        ),
        migrations.RunPython(copy_category_to_ar, noop),
        migrations.RemoveField(
            model_name="featuredpost",
            name="category",
        ),
    ]
