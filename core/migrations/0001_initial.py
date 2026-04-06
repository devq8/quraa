# Generated manually for Qari model (CSV: No., Name, Title, Birth Year, ...)

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Qari",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "number",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Display number from source (e.g. 1, 2, 3).",
                        null=True,
                        unique=True,
                        verbose_name="No.",
                    ),
                ),
                ("name", models.CharField(max_length=255, verbose_name="Name")),
                (
                    "title",
                    models.CharField(
                        blank=True,
                        help_text="e.g. علاَّمة كبير، إمام في القراءات بلا نظير",
                        max_length=500,
                        verbose_name="Title",
                    ),
                ),
                ("birth_year", models.PositiveIntegerField(blank=True, null=True, verbose_name="Birth year")),
                ("birthplace", models.CharField(blank=True, max_length=255, verbose_name="Birthplace")),
                ("hometown", models.CharField(blank=True, max_length=255, verbose_name="Home town")),
                ("school", models.CharField(blank=True, max_length=255, verbose_name="School")),
                (
                    "teachers",
                    models.TextField(
                        blank=True,
                        help_text="Comma-separated list of teachers.",
                        verbose_name="Teachers",
                    ),
                ),
                (
                    "readings",
                    models.TextField(
                        blank=True,
                        help_text="e.g. القراءات العشر الصغرى والكبرى، القراءات الشاذة",
                        verbose_name="Readings",
                    ),
                ),
                (
                    "path",
                    models.TextField(
                        blank=True,
                        help_text="e.g. الشاطبية، الدرة، طيبة النشر",
                        verbose_name="Path",
                    ),
                ),
                (
                    "location_of_reading",
                    models.CharField(
                        blank=True,
                        help_text="e.g. الأزهر، الجامعة الإسلامية بالمدينة، منزله",
                        max_length=255,
                        verbose_name="Location of reading",
                    ),
                ),
                (
                    "students",
                    models.TextField(
                        blank=True,
                        help_text="Comma-separated list of students.",
                        verbose_name="Students",
                    ),
                ),
                (
                    "authored_books",
                    models.TextField(
                        blank=True,
                        help_text="e.g. تنقيح فتح الكريم، شرح تنقيح فتح الكريم، تحقيق عمدة العرفان",
                        verbose_name="Authored books",
                    ),
                ),
                ("death_year", models.PositiveIntegerField(blank=True, null=True, verbose_name="Death year")),
                ("age", models.PositiveIntegerField(blank=True, null=True, verbose_name="Age (at death)")),
                ("death_location", models.CharField(blank=True, max_length=255, verbose_name="Death location")),
                (
                    "source",
                    models.CharField(
                        blank=True,
                        help_text="Reference source, e.g. كتاب هداية القاري إلى تجويد كلام الباري",
                        max_length=500,
                        verbose_name="Source",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Qari",
                "verbose_name_plural": "Qurra'",
                "ordering": ["number", "name"],
            },
        ),
    ]
