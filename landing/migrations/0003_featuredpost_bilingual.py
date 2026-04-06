# Generated for FeaturedPost bilingual (Arabic mandatory, English optional)

from django.db import migrations, models


def copy_title_excerpt_to_ar(apps, schema_editor):
    FeaturedPost = apps.get_model("landing", "FeaturedPost")
    for obj in FeaturedPost.objects.all():
        obj.title_ar = obj.title or ""
        obj.excerpt_ar = obj.excerpt or ""
        obj.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("landing", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="featuredpost",
            name="title_ar",
            field=models.CharField(default="", max_length=255, verbose_name="Title (Arabic)"),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="featuredpost",
            name="title_en",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Title (English)"),
        ),
        migrations.AddField(
            model_name="featuredpost",
            name="excerpt_ar",
            field=models.TextField(blank=True, default="", verbose_name="Excerpt (Arabic)"),
        ),
        migrations.AddField(
            model_name="featuredpost",
            name="excerpt_en",
            field=models.TextField(blank=True, default="", verbose_name="Excerpt (English)"),
        ),
        migrations.RunPython(copy_title_excerpt_to_ar, noop),
        migrations.RemoveField(
            model_name="featuredpost",
            name="title",
        ),
        migrations.RemoveField(
            model_name="featuredpost",
            name="excerpt",
        ),
    ]
