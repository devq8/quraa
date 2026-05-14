import math

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _, get_language


class Biography(models.Model):
    full_name_ar = models.CharField(_("Full Name (Arabic)"), max_length=300)
    full_name_en = models.CharField(_("Full Name (English)"), max_length=300, blank=True)
    alias_ar = models.CharField(_("Alias (Arabic)"), max_length=255, blank=True)
    alias_en = models.CharField(_("Alias (English)"), max_length=255, blank=True)

    birthplace = models.ForeignKey(
        "Location", on_delete=models.SET_NULL, null=True, blank=True, related_name="birthplace", verbose_name=_("Birthplace"),
    )
    birth_hijri_year = models.PositiveIntegerField(_("Birth Year (Hijri)"), null=True, blank=True)
    birth_hijri_month = models.PositiveSmallIntegerField(_("Birth Month (Hijri)"), null=True, blank=True)
    birth_hijri_day = models.PositiveSmallIntegerField(_("Birth Day (Hijri)"), null=True, blank=True)
    birth_greg_year = models.PositiveIntegerField(_("Birth Year (Gregorian)"), null=True, blank=True)
    birth_greg_month = models.PositiveSmallIntegerField(_("Birth Month (Gregorian)"), null=True, blank=True)
    birth_greg_day = models.PositiveSmallIntegerField(_("Birth Day (Gregorian)"), null=True, blank=True)
    birth_date_approximate = models.BooleanField(_("Birth Date Approximate"), default=False)

    hometown = models.ForeignKey(
        "Location", on_delete=models.SET_NULL, null=True, blank=True, related_name="hometown", verbose_name=_("Hometown"),
    )
    death_location = models.ForeignKey(
        "Location", on_delete=models.SET_NULL, null=True, blank=True, related_name="death_location", verbose_name=_("Death Location"),
    )
    death_hijri_year = models.PositiveIntegerField(_("Death Year (Hijri)"), null=True, blank=True)
    death_hijri_month = models.PositiveSmallIntegerField(_("Death Month (Hijri)"), null=True, blank=True)
    death_hijri_day = models.PositiveSmallIntegerField(_("Death Day (Hijri)"), null=True, blank=True)
    death_greg_year = models.PositiveIntegerField(_("Death Year (Gregorian)"), null=True, blank=True)
    death_greg_month = models.PositiveSmallIntegerField(_("Death Month (Gregorian)"), null=True, blank=True)
    death_greg_day = models.PositiveSmallIntegerField(_("Death Day (Gregorian)"), null=True, blank=True)
    death_date_approximate = models.BooleanField(_("Death Date Approximate"), default=False)

    attributes = models.ManyToManyField(
        "Attribute", blank=True, related_name="biographies",
        verbose_name=_("Attributes"),
    )
    teachers = models.ManyToManyField(
        "self",
        through="TeacherStudentRelationship",
        symmetrical=False,
        blank=True,
        related_name="students",
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="submitted_biographies",
        verbose_name=_("Submitted By"),
    )
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="modified_biographies",
        verbose_name=_("Last Modified By"),
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="biography",
        verbose_name=_("User Account"),
    )

    published = models.BooleanField(_("Published"), default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Biography")
        verbose_name_plural = _("Biographies")
        ordering = ["id", "full_name_ar"]

    def __str__(self):
        lang = get_language()
        if lang and lang.startswith("ar"):
            return self.full_name_ar or self.full_name_en
        return self.full_name_en or self.full_name_ar

    def clean(self):
        errors = {}
        for prefix, label in (("birth", _("Birth")), ("death", _("Death"))):
            for cal, cal_label in (("hijri", _("Hijri")), ("greg", _("Gregorian"))):
                year = getattr(self, f"{prefix}_{cal}_year")
                month = getattr(self, f"{prefix}_{cal}_month")
                day = getattr(self, f"{prefix}_{cal}_day")
                if day and not month:
                    errors[f"{prefix}_{cal}_day"] = _("%(label)s %(cal)s day requires a month.") % {"label": label, "cal": cal_label}
                if month and not year:
                    errors[f"{prefix}_{cal}_month"] = _("%(label)s %(cal)s month requires a year.") % {"label": label, "cal": cal_label}

        if errors:
            raise ValidationError(errors)

    def _fill_date(self, prefix):
        """Convert whichever calendar was provided into the other one."""
        from hijridate import Gregorian as HijriGregorian, Hijri

        hY = getattr(self, f"{prefix}_hijri_year")
        hM = getattr(self, f"{prefix}_hijri_month")
        hD = getattr(self, f"{prefix}_hijri_day")
        gY = getattr(self, f"{prefix}_greg_year")
        gM = getattr(self, f"{prefix}_greg_month")
        gD = getattr(self, f"{prefix}_greg_day")

        # Both calendars already have a year — nothing to derive.
        if hY and gY:
            return

        # hijridate only supports Hijri ~1356–1500 / Gregorian ~1937–2077.
        # Outside that window the library raises OverflowError; fall back to the
        # year-only linear approximation (and mark the date approximate).
        def approx_greg_from_hijri():
            setattr(self, f"{prefix}_greg_year", hY + 622 - math.floor(hY / 33))
            setattr(self, f"{prefix}_greg_month", None)
            setattr(self, f"{prefix}_greg_day", None)
            setattr(self, f"{prefix}_date_approximate", True)

        def approx_hijri_from_greg():
            setattr(self, f"{prefix}_hijri_year", gY - 622 + math.floor((gY - 622) / 32))
            setattr(self, f"{prefix}_hijri_month", None)
            setattr(self, f"{prefix}_hijri_day", None)
            setattr(self, f"{prefix}_date_approximate", True)

        if hY and hM and hD and not gY:
            try:
                g = Hijri(hY, hM, hD).to_gregorian()
                setattr(self, f"{prefix}_greg_year", g.year)
                setattr(self, f"{prefix}_greg_month", g.month)
                setattr(self, f"{prefix}_greg_day", g.day)
                setattr(self, f"{prefix}_date_approximate", False)
            except (OverflowError, ValueError):
                approx_greg_from_hijri()

        elif gY and gM and gD and not hY:
            try:
                h = HijriGregorian(gY, gM, gD).to_hijri()
                setattr(self, f"{prefix}_hijri_year", h.year)
                setattr(self, f"{prefix}_hijri_month", h.month)
                setattr(self, f"{prefix}_hijri_day", h.day)
                setattr(self, f"{prefix}_date_approximate", False)
            except (OverflowError, ValueError):
                approx_hijri_from_greg()

        elif hY and hM and not hD and not gY:
            try:
                g = Hijri(hY, hM, 1).to_gregorian()
                setattr(self, f"{prefix}_greg_year", g.year)
                setattr(self, f"{prefix}_greg_month", g.month)
                setattr(self, f"{prefix}_date_approximate", True)
            except (OverflowError, ValueError):
                approx_greg_from_hijri()

        elif gY and gM and not gD and not hY:
            try:
                h = HijriGregorian(gY, gM, 1).to_hijri()
                setattr(self, f"{prefix}_hijri_year", h.year)
                setattr(self, f"{prefix}_hijri_month", h.month)
                setattr(self, f"{prefix}_date_approximate", True)
            except (OverflowError, ValueError):
                approx_hijri_from_greg()

        elif hY and not gY:
            approx_greg_from_hijri()

        elif gY and not hY:
            approx_hijri_from_greg()

    def save(self, *args, **kwargs):
        self._fill_date("birth")
        self._fill_date("death")
        super().save(*args, **kwargs)


class Location(models.Model):
    city_ar = models.CharField(_("City (Arabic)"), max_length=255)
    city_en = models.CharField(_("City (English)"), max_length=255, blank=True)
    country_ar = models.CharField(_("Country (Arabic)"), max_length=255,)
    country_en = models.CharField(_("Country (English)"), max_length=255, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        lang = get_language()
        if lang and lang.startswith("ar"):
            return f"{self.city_ar} - {self.country_ar}"
        city = self.city_en or self.city_ar
        country = self.country_en or self.country_ar
        return f"{city} - {country}"

    class Meta:
        verbose_name = _("Location")
        verbose_name_plural = _("Locations")
        ordering = ["id", "country_ar", "city_ar"]
        constraints = [ models.UniqueConstraint(fields=["country_ar", "city_ar"], name="unique_location_ar") ]



# صفات وتصنيفات مثل ١٠ك (القراءات العشر الكبرى) ، ١٠ص (القراءات العشر الصغرى) ... إلخ
class Attribute(models.Model):
    short_name_ar = models.CharField(_("Short Name (Arabic)"), max_length=255)
    short_name_en = models.CharField(_("Short Name (English)"), max_length=255, blank=True)
    long_name_ar = models.CharField(_("Long Name (Arabic)"), max_length=255)
    long_name_en = models.CharField(_("Long Name (English)"), max_length=255, blank=True)
    description_ar = models.TextField(_("Description (Arabic)"), blank=True)
    description_en = models.TextField(_("Description (English)"), blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        lang = get_language()
        if lang and lang.startswith("ar"):
            return self.short_name_ar or self.short_name_en
        return self.short_name_en or self.short_name_ar

    class Meta:
        verbose_name = _("Attribute")
        verbose_name_plural = _("Attributes")
        ordering = ["id", "short_name_ar"]


class Source(models.Model):
    biography = models.ForeignKey(
        "Biography", on_delete=models.CASCADE, related_name="sources", verbose_name=_("Biography")
    )
    name_ar = models.CharField(_("Name (Arabic)"), max_length=500)
    name_en = models.CharField(_("Name (English)"), max_length=500, blank=True)
    link = models.URLField(_("Link"), blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        lang = get_language()
        if lang and lang.startswith("ar"):
            return self.name_ar or self.name_en
        return self.name_en or self.name_ar

    class Meta:
        verbose_name = _("Source")
        verbose_name_plural = _("Sources")
        ordering = ["biography", "id"]


class EsnadTemplate(models.Model):
    name_ar = models.CharField(_("Name (Arabic)"), max_length=500)
    name_en = models.CharField(_("Name (English)"), max_length=500, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Esnad Template")
        verbose_name_plural = _("Esnad Templates")
        ordering = ["name_ar"]

    def __str__(self):
        lang = get_language()
        if lang and lang.startswith("ar"):
            return self.name_ar or self.name_en
        return self.name_en or self.name_ar


class EsnadTemplateLink(models.Model):
    template = models.ForeignKey(
        "EsnadTemplate",
        on_delete=models.CASCADE,
        related_name="links",
        verbose_name=_("Template"),
    )
    narrator = models.ForeignKey(
        "Biography",
        on_delete=models.CASCADE,
        related_name="template_appearances",
        verbose_name=_("Narrator"),
    )
    order = models.PositiveSmallIntegerField(_("Order"))
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["template", "narrator"], name="unique_template_narrator"),
        ]
        verbose_name = _("Template Link")
        verbose_name_plural = _("Template Links")
        ordering = ["template", "order"]

    def __str__(self):
        return f"{self.template} → [{self.order}] {self.narrator}"


class Esnad(models.Model):
    biography = models.ForeignKey(
        "Biography",
        on_delete=models.CASCADE,
        related_name="esnads",
        verbose_name=_("Biography"),
    )
    narrators = models.ManyToManyField(
        "Biography",
        through="EsnadLink",
        through_fields=("esnad", "narrator"),
        related_name="esnads_as_narrator",   # different from EsnadLink.narrator's related_name
        blank=True,
        verbose_name=_("Narrators"),
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Esnad")
        verbose_name_plural = _("Asanid")
        ordering = ["biography", "id"]
    @property
    def isnad_rank(self):
        """Number of intermediary narrators between the esnad holder and the
        terminal narrator, excluding both endpoints. Returns None for empty chains."""
        count = getattr(self, "_links_count", None)
        if count is None:
            count = self.links.count()
        return count - 1 if count else None
    
    def __str__(self):
        lang = get_language()
         
        if lang and lang.startswith("ar"):
            rank = "رتبة " + (str(self.isnad_rank) if self.isnad_rank is not None else "سلسلة فارغة")
        else:
            rank = "Rank " + (str(self.isnad_rank) if self.isnad_rank is not None else "empty chain")
        return f"{self.biography} #{self.pk} - {rank}"

    def chain_display(self):
        lang = get_language()

        def name(bio):
            if lang and lang.startswith("ar"):
                return bio.alias_ar or bio.full_name_ar or bio.alias_en or bio.full_name_en
            return bio.alias_en or bio.full_name_en or bio.alias_ar or bio.full_name_ar

        parts = [name(self.biography)]
        links = list(self.links.all())   # ← uses prefetch cache
        for link in links[:-1]:
            parts.append(f"{link.order} {name(link.narrator)}")
        if links:
            parts.append(name(links[-1].narrator))
        return " ← ".join(parts)


    @property
    def terminal_link(self):
        """Last EsnadLink in this chain (highest order), or None if the chain is empty."""
        return (
            self.links.select_related("narrator").order_by("-order").first()
        )

    


class EsnadLink(models.Model):
    esnad = models.ForeignKey(
        "Esnad",
        on_delete=models.CASCADE,
        related_name="links",
        verbose_name=_("Esnad"),
    )
    narrator = models.ForeignKey(
        "Biography",
        on_delete=models.CASCADE,
        related_name="esnad_appearances",
        verbose_name=_("Narrator"),
    )
    order = models.PositiveSmallIntegerField(_("Order"), null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["esnad", "narrator"], name="unique_esnad_narrator"),
            # Note: NO unique constraint on (esnad, order).
            # Sortable inlines reorder by swapping order values, which Django's
            # per-form validate_unique() cannot handle (it sees stale DB state
            # before sibling forms have saved). Order uniqueness is maintained
            # by the drag-and-drop JS (sequential renumbering) and by save()
            # auto-assigning max+1 for new rows.
        ]
        verbose_name = _("Esnad Link")
        verbose_name_plural = _("Esnad Links")
        ordering = ["esnad", "order"]

    def save(self, *args, **kwargs):
        if self.order is None:
            last = EsnadLink.objects.filter(esnad=self.esnad).aggregate(
                models.Max("order")
            )["order__max"]
            self.order = (last or 0) + 1
        super().save(*args, **kwargs)

    def clean(self):
        if not self.esnad_id or not self.narrator_id:
            return
        if self.narrator_id == self.esnad.biography_id:
            raise ValidationError(
                {"narrator": _("The holder of this Esnad cannot appear as a narrator in their own chain.")}
            )

    def __str__(self):
        return f"[{self.order}] {self.narrator}"


class TeacherStudentRelationship(models.Model):
    teacher = models.ForeignKey(
        "Biography",
        on_delete=models.CASCADE,
        related_name="student_relationships",
        verbose_name=_("Teacher"),
    )
    student = models.ForeignKey(
        "Biography",
        on_delete=models.CASCADE,
        related_name="teacher_relationships",
        verbose_name=_("Student"),
    )
    notes_ar = models.CharField(_("Notes (Arabic)"), max_length=500, blank=True)
    notes_en = models.CharField(_("Notes (English)"), max_length=500, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["teacher", "student"], name="unique_teacher_student"),
        ]
        verbose_name = _("Teacher-Student Relationship")
        verbose_name_plural = _("Teacher-Student Relationships")
        ordering = ["teacher", "student"]

    def __str__(self):
        return f"{self.teacher} → {self.student}"
