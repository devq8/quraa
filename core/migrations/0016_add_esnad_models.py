import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_add_source_model"),
    ]

    operations = [
        migrations.CreateModel(
            name="Esnad",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name_ar", models.CharField(blank=True, max_length=500, verbose_name="Name (Arabic)")),
                ("name_en", models.CharField(blank=True, max_length=500, verbose_name="Name (English)")),
                ("description_ar", models.TextField(blank=True, verbose_name="Description (Arabic)")),
                ("description_en", models.TextField(blank=True, verbose_name="Description (English)")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "biography",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="esnads",
                        to="core.biography",
                        verbose_name="Biography",
                    ),
                ),
            ],
            options={
                "verbose_name": "Esnad",
                "verbose_name_plural": "Asanid",
                "ordering": ["biography", "id"],
            },
        ),
        migrations.CreateModel(
            name="EsnadLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order", models.PositiveSmallIntegerField(verbose_name="Order")),
                ("notes_ar", models.CharField(blank=True, max_length=500, verbose_name="Notes (Arabic)")),
                ("notes_en", models.CharField(blank=True, max_length=500, verbose_name="Notes (English)")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "esnad",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="links",
                        to="core.esnad",
                        verbose_name="Esnad",
                    ),
                ),
                (
                    "narrator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="esnad_appearances",
                        to="core.biography",
                        verbose_name="Narrator",
                    ),
                ),
            ],
            options={
                "verbose_name": "Esnad Link",
                "verbose_name_plural": "Esnad Links",
                "ordering": ["esnad", "order"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="esnadlink",
            unique_together={("esnad", "order"), ("esnad", "narrator")},
        ),
    ]
