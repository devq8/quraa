import json
import time

from django.db import models
from django.utils.translation import gettext_lazy as _


class SiteSettings(models.Model):
    """Singleton-style settings: logo, site name, footer main block, copyright."""
    site_name_ar = models.CharField(_("Site name (Arabic)"), max_length=255, default="المركز العالمي لتاريخ ووثائق القرآء")
    site_name_en = models.CharField(_("Site name (English)"), max_length=255, default="The International Center for the History and Documentation of Quran Reciters")
    logo = models.ImageField(_("Logo"), upload_to="landing/logo", blank=True, null=True)
    logo_dark = models.ImageField(_("Logo (dark)"), upload_to="landing/logo", blank=True, null=True)
    favicon = models.ImageField(_("Favicon"), upload_to="landing/favicon", blank=True, null=True)

    # Footer main block
    footer_title_ar = models.CharField(_("Footer title (Arabic)"), max_length=255, blank=True)
    footer_title_en = models.CharField(_("Footer title (English)"), max_length=255, blank=True)
    footer_description_ar = models.TextField(_("Footer description (Arabic)"), blank=True)
    footer_description_en = models.TextField(_("Footer description (English)"), blank=True)
    footer_button_text_ar = models.CharField(_("Footer button (Arabic)"), max_length=100, default="سجّل الآن")
    footer_button_text_en = models.CharField(_("Footer button (English)"), max_length=100, default="Register Now")
    footer_button_link = models.URLField(_("Footer button URL"), blank=True)

    # Copyright
    copyright_ar = models.CharField(_("Copyright (Arabic)"), max_length=255, default="المركز العالمي لتاريخ ووثائق القرآء. جميع الحقوق محفوظة.")
    copyright_en = models.CharField(_("Copyright (English)"), max_length=255, default="The International Center for the History and Documentation of Quran Reciters. All rights reserved.")

    class Meta:
        verbose_name = _("Site settings")
        verbose_name_plural = _("Site settings")

    def __str__(self):
        return "Site settings"

    def save(self, *args, **kwargs):
        # Keep only one instance (singleton)
        self.pk = 1
        super().save(*args, **kwargs)


class LandingSection(models.Model):
    """Editable headings and leads for each landing section (welcome, services, blog, clients, team)."""
    SLUG_CHOICES = [
        ("welcome", _("Welcome")),
        ("services", _("Services")),
        ("blog", _("Blog")),
        ("clients", _("Clients")),
        ("team", _("Team")),
    ]
    slug = models.SlugField(choices=SLUG_CHOICES, unique=True)
    heading_ar = models.CharField(_("Heading (Arabic)"), max_length=255)
    heading_en = models.CharField(_("Heading (English)"), max_length=255)
    lead_ar = models.CharField(_("Lead / subtitle (Arabic)"), max_length=500, blank=True)
    lead_en = models.CharField(_("Lead / subtitle (English)"), max_length=500, blank=True)

    class Meta:
        verbose_name = _("Section")
        verbose_name_plural = _("Sections")

    def __str__(self):
        return dict(self.SLUG_CHOICES).get(self.slug, self.slug)


class HeroSlide(models.Model):
    """Hero slider slides (title, subtitle, button, video or image)."""
    title_ar = models.CharField(_("Title (Arabic)"), max_length=255)
    title_en = models.CharField(_("Title (English)"), max_length=255)
    subtitle_ar = models.TextField(_("Subtitle (Arabic)"), blank=True)
    subtitle_en = models.TextField(_("Subtitle (English)"), blank=True)
    button_text_ar = models.CharField(_("Button text (Arabic)"), max_length=100, default="اكتشف المزيد")
    button_text_en = models.CharField(_("Button text (English)"), max_length=100, default="Explore more")
    button_link = models.CharField(_("Button link (URL or #anchor)"), max_length=500, default="#welcome")
    # Media: either video path (e.g. relative to static or full URL) or image
    video_url = models.CharField(
        _("Video URL or path"),
        max_length=500,
        blank=True,
        help_text=_("e.g. path under static like 'video/quran_video.mp4' or full URL"),
    )
    image = models.ImageField(_("Image (if no video)"), upload_to="landing/hero", blank=True, null=True)
    order = models.PositiveIntegerField(_("Order"), default=0)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        ordering = ["order"]
        verbose_name = _("Hero slide")
        verbose_name_plural = _("Hero slides")

    def __str__(self):
        return self.title_ar or self.title_en


class WelcomeSection(models.Model):
    """Welcome block: heading, subheading, and image (single row)."""
    heading_ar = models.CharField(_("Heading (Arabic)"), max_length=255)
    heading_en = models.CharField(_("Heading (English)"), max_length=255)
    lead_ar = models.CharField(_("Lead (Arabic)"), max_length=500, blank=True)
    lead_en = models.CharField(_("Lead (English)"), max_length=500, blank=True)
    image = models.ImageField(_("Image"), upload_to="landing/welcome", blank=True, null=True)

    class Meta:
        verbose_name = _("Welcome section")
        verbose_name_plural = _("Welcome section")

    def __str__(self):
        return self.heading_ar or self.heading_en

    def save(self, *args, **kwargs):
        # Single row: always pk=1
        self.pk = 1
        super().save(*args, **kwargs)


class Service(models.Model):
    """Services section items (icon, title, description, link)."""
    icon = models.CharField(
        _("Icon class (FontAwesome)"),
        max_length=100,
        help_text=_("e.g. fa fa-book, fa fa-clipboard-check"),
    )
    title_ar = models.CharField(_("Title (Arabic)"), max_length=255)
    title_en = models.CharField(_("Title (English)"), max_length=255)
    description_ar = models.CharField(_("Description (Arabic)"), max_length=500, blank=True)
    description_en = models.CharField(_("Description (English)"), max_length=500, blank=True)
    link = models.URLField(_("Link"), blank=True)
    order = models.PositiveIntegerField(_("Order"), default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = _("Service")
        verbose_name_plural = _("Services")

    def __str__(self):
        return self.title_ar or self.title_en


class StatCounter(models.Model):
    """Stats/counters section (icon, value, label)."""
    icon = models.CharField(
        _("Icon class (FontAwesome)"),
        max_length=100,
        help_text=_("e.g. fa fa-3x fa-book"),
    )
    value_from = models.PositiveIntegerField(_("Animate from"), default=0)
    value_to = models.PositiveIntegerField(_("Value to display"))
    label_ar = models.CharField(_("Label (Arabic)"), max_length=255)
    label_en = models.CharField(_("Label (English)"), max_length=255)
    order = models.PositiveIntegerField(_("Order"), default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = _("Stat counter")
        verbose_name_plural = _("Stat counters")

    def __str__(self):
        return f"{self.value_to} – {self.label_ar or self.label_en}"


class FeaturedPost(models.Model):
    """Blog/featured posts shown on the landing page."""
    image = models.ImageField(_("Image"), upload_to="landing/blog", blank=True, null=True)
    category_ar = models.CharField(_("Category (Arabic)"), max_length=100, blank=True)
    category_en = models.CharField(_("Category (English)"), max_length=100, blank=True)
    title_ar = models.CharField(_("Title (Arabic)"), max_length=255)
    title_en = models.CharField(_("Title (English)"), max_length=255, blank=True)
    excerpt_ar = models.TextField(_("Excerpt (Arabic)"), blank=True)
    excerpt_en = models.TextField(_("Excerpt (English)"), blank=True)
    url = models.URLField(_("Link"), blank=True)
    published_at = models.DateField(_("Date"), null=True, blank=True)
    order = models.PositiveIntegerField(_("Order"), default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = _("Featured post")
        verbose_name_plural = _("Featured posts")

    def __str__(self):
        return self.title_ar or self.title_en


class Client(models.Model):
    """Client/partner logos."""
    name = models.CharField(_("Name (alt text)"), max_length=255)
    logo = models.ImageField(_("Logo"), upload_to="landing/clients")
    link = models.URLField(_("Link"), blank=True)
    order = models.PositiveIntegerField(_("Order"), default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = _("Client")
        verbose_name_plural = _("Clients")

    def __str__(self):
        return self.name


class TeamMember(models.Model):
    """Team section members."""
    name = models.CharField(_("Name"), max_length=255)
    role = models.CharField(_("Role / title"), max_length=255)
    bio = models.TextField(_("Short bio"), blank=True)
    image = models.ImageField(_("Photo"), upload_to="landing/team", blank=True, null=True)
    facebook_url = models.URLField(_("Facebook"), blank=True)
    twitter_url = models.URLField(_("Twitter"), blank=True)
    instagram_url = models.URLField(_("Instagram"), blank=True)
    email = models.EmailField(_("Email"), blank=True)
    order = models.PositiveIntegerField(_("Order"), default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = _("Team member")
        verbose_name_plural = _("Team members")

    def __str__(self):
        return self.name


class FooterColumn(models.Model):
    """Footer link column (e.g. Discover, Features, Pages, Support)."""
    title = models.CharField(_("Column title (legacy)"), max_length=100, blank=True, help_text=_("Fallback if Arabic/English not set"))
    title_ar = models.CharField(_("Column title (Arabic)"), max_length=100, blank=True)
    title_en = models.CharField(_("Column title (English)"), max_length=100, blank=True)
    order = models.PositiveIntegerField(_("Order"), default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = _("Footer column")
        verbose_name_plural = _("Footer columns")

    def __str__(self):
        return self.title_ar or self.title_en or self.title or str(_("Footer column"))


class FooterLink(models.Model):
    """Single link under a footer column."""
    column = models.ForeignKey(FooterColumn, on_delete=models.CASCADE, related_name="links")
    label = models.CharField(_("Label (legacy)"), max_length=255, blank=True, help_text=_("Fallback if Arabic/English not set"))
    label_ar = models.CharField(_("Label (Arabic)"), max_length=255, blank=True)
    label_en = models.CharField(_("Label (English)"), max_length=255, blank=True)
    url = models.URLField(_("URL"), blank=True)
    order = models.PositiveIntegerField(_("Order"), default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = _("Footer link")
        verbose_name_plural = _("Footer links")

    def __str__(self):
        label = self.label_ar or self.label_en or self.label
        return f"{self.column}: {label}"
