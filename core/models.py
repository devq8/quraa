from django.db import models
from django.utils.translation import gettext_lazy as _


class Reciter(models.Model):
    """
    Scholar/reciter (قارئ) — represents a Quran recitation scholar with biography,
    teachers, readings, students, and authored works.
    """
    name = models.CharField(_("Name"), max_length=255)
    title = models.CharField(
        _("Title"),
        max_length=500,
        blank=True,
        help_text=_("e.g. علاَّمة كبير، إمام في القراءات بلا نظير"),
    )
    birth_year = models.PositiveIntegerField(_("Birth year"), null=True, blank=True)
    birthplace = models.CharField(_("Birthplace"), max_length=255, blank=True)
    hometown = models.CharField(_("Home town"), max_length=255, blank=True)
    school = models.CharField(_("School"), max_length=255, blank=True)

    # Comma-separated in CSV; stored as text for flexibility
    teachers = models.TextField(
        _("Teachers"),
        blank=True,
        help_text=_("Comma-separated list of teachers."),
    )
    readings = models.TextField(
        _("Readings"),
        blank=True,
        help_text=_("e.g. القراءات العشر الصغرى والكبرى، القراءات الشاذة"),
    )
    path = models.TextField(
        _("Path"),
        blank=True,
        help_text=_("e.g. الشاطبية، الدرة، طيبة النشر"),
    )
    location_of_reading = models.CharField(
        _("Location of reading"),
        max_length=255,
        blank=True,
        help_text=_("e.g. الأزهر، الجامعة الإسلامية بالمدينة، منزله"),
    )
    students = models.TextField(
        _("Students"),
        blank=True,
        help_text=_("Comma-separated list of students."),
    )
    authored_books = models.TextField(
        _("Authored books"),
        blank=True,
        help_text=_("e.g. تنقيح فتح الكريم، شرح تنقيح فتح الكريم، تحقيق عمدة العرفان"),
    )

    death_year = models.PositiveIntegerField(_("Death year"), null=True, blank=True)
    age = models.PositiveIntegerField(_("Age (at death)"), null=True, blank=True)
    death_location = models.CharField(_("Death location"), max_length=255, blank=True)
    source = models.CharField(
        _("Source"),
        max_length=500,
        blank=True,
        help_text=_("Reference source, e.g. كتاب هداية القاري إلى تجويد كلام الباري"),
    )

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Reciter")
        verbose_name_plural = _("Reciters")
        ordering = ["id", "name"]

    def __str__(self):
        return self.name
