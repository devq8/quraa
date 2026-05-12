import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_simplify_esnad_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="EsnadTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name_ar", models.CharField(max_length=500, verbose_name="Name (Arabic)")),
                ("name_en", models.CharField(blank=True, max_length=500, verbose_name="Name (English)")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Esnad Template",
                "verbose_name_plural": "Esnad Templates",
                "ordering": ["name_ar"],
            },
        ),
        migrations.CreateModel(
            name="EsnadTemplateLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order", models.PositiveSmallIntegerField(verbose_name="Order")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "narrator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="template_appearances",
                        to="core.biography",
                        verbose_name="Narrator",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="links",
                        to="core.esnadtemplate",
                        verbose_name="Template",
                    ),
                ),
            ],
            options={
                "verbose_name": "Template Link",
                "verbose_name_plural": "Template Links",
                "ordering": ["template", "order"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="esnadtemplatelink",
            unique_together={("template", "order"), ("template", "narrator")},
        ),
    ]
