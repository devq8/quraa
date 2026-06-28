import json
import time

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class SiteSettings(models.Model):
    """Singleton-style settings: logo, site name, footer main block, copyright."""

    # General site info
    site_name_ar = models.CharField(_("Site name (Arabic)"), max_length=255, default="المركز العالمي لتاريخ ووثائق القرآء")
    site_name_en = models.CharField(_("Site name (English)"), max_length=255, default="The International Center for the History and Documentation of Quran Reciters")
    logo = models.ImageField(_("Logo"), upload_to="landing/logo", blank=True, null=True)
    logo_dark = models.ImageField(_("Logo (dark)"), upload_to="landing/logo", blank=True, null=True)
    favicon = models.ImageField(_("Favicon"), upload_to="landing/favicon", blank=True, null=True)
    favicon_dark = models.ImageField(_("Favicon (dark)"), upload_to="landing/favicon", blank=True, null=True)
    biography_placeholder_image = models.ImageField(
        _("Biography placeholder image"), upload_to="landing/biography_placeholder", blank=True, null=True
    )

    # About us section
    about_heading_ar = models.CharField(_("About us heading (Arabic)"), max_length=255, blank=True)
    about_heading_en = models.CharField(_("About us heading (English)"), max_length=255, blank=True)
    about_subheading_ar = models.CharField(_("About us subheading (Arabic)"), max_length=255, blank=True)
    about_subheading_en = models.CharField(_("About us subheading (English)"), max_length=255, blank=True)
    about_description_ar = models.TextField(_("About us description (Arabic)"), max_length=2000, blank=True)
    about_description_en = models.TextField(_("About us description (English)"), max_length=2000, blank=True)
    about_image = models.ImageField(_("About us image"), upload_to="landing/about", blank=True, null=True)
    about_url = models.URLField(_("About us URL"), blank=True)

    # Services section header
    services_heading_ar = models.CharField(_("Services heading (Arabic)"), max_length=255, blank=True)
    services_heading_en = models.CharField(_("Services heading (English)"), max_length=255, blank=True)
    services_subheading_ar = models.CharField(_("Services subheading (Arabic)"), max_length=255, blank=True)
    services_subheading_en = models.CharField(_("Services subheading (English)"), max_length=255, blank=True)
    services_description_ar = models.TextField(_("Services description (Arabic)"), max_length=2000, blank=True)
    services_description_en = models.TextField(_("Services description (English)"), max_length=2000, blank=True)

    # Donate section
    donate_heading_ar = models.CharField(_("Donate heading (Arabic)"), max_length=255, blank=True)
    donate_heading_en = models.CharField(_("Donate heading (English)"), max_length=255, blank=True)
    donate_subheading_ar = models.CharField(_("Donate subheading (Arabic)"), max_length=255, blank=True)
    donate_subheading_en = models.CharField(_("Donate subheading (English)"), max_length=255, blank=True)
    donate_button_text_ar = models.CharField(_("Donate button (Arabic)"), max_length=100, default="تبرّع الآن")
    donate_button_text_en = models.CharField(_("Donate button (English)"), max_length=100, default="Donate Now")
    donate_button_link = models.URLField(_("Donate button URL"), blank=True)

    # Blog section header
    blog_heading_ar = models.CharField(_("Blog heading (Arabic)"), max_length=255, blank=True)
    blog_heading_en = models.CharField(_("Blog heading (English)"), max_length=255, blank=True)
    blog_subheading_ar = models.CharField(_("Blog subheading (Arabic)"), max_length=255, blank=True)
    blog_subheading_en = models.CharField(_("Blog subheading (English)"), max_length=255, blank=True)
    blog_description_ar = models.TextField(_("Blog description (Arabic)"), max_length=2000, blank=True)
    blog_description_en = models.TextField(_("Blog description (English)"), max_length=2000, blank=True)

    # Featured biographies section header
    featured_biographies_heading_ar = models.CharField(_("Featured biographies heading (Arabic)"), max_length=255, blank=True)
    featured_biographies_heading_en = models.CharField(_("Featured biographies heading (English)"), max_length=255, blank=True)
    featured_biographies_subheading_ar = models.CharField(_("Featured biographies subheading (Arabic)"), max_length=255, blank=True)
    featured_biographies_subheading_en = models.CharField(_("Featured biographies subheading (English)"), max_length=255, blank=True)
    featured_biographies_description_ar = models.TextField(_("Featured biographies description (Arabic)"), max_length=2000, blank=True)
    featured_biographies_description_en = models.TextField(_("Featured biographies description (English)"), max_length=2000, blank=True)

    # Contact section
    contact_heading_ar = models.CharField(_("Contact heading (Arabic)"), max_length=255, blank=True)
    contact_heading_en = models.CharField(_("Contact heading (English)"), max_length=255, blank=True)
    contact_subheading_ar = models.CharField(_("Contact subheading (Arabic)"), max_length=255, blank=True)
    contact_subheading_en = models.CharField(_("Contact subheading (English)"), max_length=255, blank=True)
    contact_description_ar = models.TextField(_("Contact description (Arabic)"), max_length=2000, blank=True)
    contact_description_en = models.TextField(_("Contact description (English)"), max_length=2000, blank=True)
    contact_email = models.EmailField(_("Contact email"), blank=True)
    contact_phone = models.CharField(_("Contact phone"), max_length=50, blank=True)
    contact_address_ar = models.CharField(_("Contact address (Arabic)"), max_length=255, blank=True)
    contact_address_en = models.CharField(_("Contact address (English)"), max_length=255, blank=True)

    # Social media links (for icons in header and/or footer)
    facebook_url = models.URLField(_("Facebook URL"), blank=True)
    twitter_url = models.URLField(_("Twitter URL"), blank=True)
    instagram_url = models.URLField(_("Instagram URL"), blank=True)

    # Search
    search_results_per_page = models.PositiveIntegerField(
        _("Search results per page"),
        default=5,
        validators=[MinValueValidator(1)],
        help_text=_("Number of biographies shown per page on the search results page."),
    )

    # Copyright
    copyright_ar = models.CharField(_("Copyright (Arabic)"), max_length=255, default="المركز العالمي لتاريخ ووثائق القرآء. جميع الحقوق محفوظة.")
    copyright_en = models.CharField(_("Copyright (English)"), max_length=255, default="The International Center for the History and Documentation of Quran Reciters. All rights reserved.")

    class Meta:
        verbose_name = _("Site settings")
        verbose_name_plural = _("Site settings")

    def __str__(self):
        return str(_("Site settings"))

    def save(self, *args, **kwargs):
        # Keep only one instance (singleton)
        self.pk = 1
        super().save(*args, **kwargs)

class HeroSlide(models.Model):
    """Singleton hero section (title, subtitle, search bar, video or image)."""
    title_ar = models.CharField(_("Title (Arabic)"), max_length=255)
    title_en = models.CharField(_("Title (English)"), max_length=255)
    subtitle_ar = models.CharField(_("Subtitle (Arabic)"), max_length=255, blank=True)
    subtitle_en = models.CharField(_("Subtitle (English)"), max_length=255, blank=True)
    show_searchbar = models.BooleanField(_("Show search bar"), default=True)
    # Media: either video path (e.g. relative to static or full URL) or image
    video_url = models.CharField(
        _("Video URL or path"),
        max_length=500,
        blank=True,
        help_text=_("e.g. path under static like 'video/quran_video.mp4' or full URL"),
    )
    image = models.ImageField(_("Image (if no video)"), upload_to="landing/hero", blank=True, null=True)

    class Meta:
        verbose_name = _("Hero section")
        verbose_name_plural = _("Hero section")

    def __str__(self):
        return self.title_ar or self.title_en

    def save(self, *args, **kwargs):
        # Keep only one instance (singleton)
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

class Post(models.Model):
    """Blog posts shown on the landing page."""
    image = models.ImageField(_("Image"), upload_to="landing/blog", blank=True, null=True)
    category_ar = models.CharField(_("Category (Arabic)"), max_length=100, blank=True)
    category_en = models.CharField(_("Category (English)"), max_length=100, blank=True)
    title_ar = models.CharField(_("Title (Arabic)"), max_length=255)
    title_en = models.CharField(_("Title (English)"), max_length=255, blank=True)
    author_ar = models.CharField(_("Author (Arabic)"), max_length=255, blank=True)
    author_en = models.CharField(_("Author (English)"), max_length=255, blank=True)
    author_role_ar = models.CharField(_("Author role (Arabic)"), max_length=255, blank=True)
    author_role_en = models.CharField(_("Author role (English)"), max_length=255, blank=True)
    excerpt_ar = models.TextField(_("Excerpt (Arabic)"), blank=True)
    excerpt_en = models.TextField(_("Excerpt (English)"), blank=True)
    body_ar = models.TextField(_("Body (Arabic)"), blank=True)
    body_en = models.TextField(_("Body (English)"), blank=True)
    show_as_featured = models.BooleanField(_("Show as featured post"), default=False)
    published_at = models.DateField(_("Date"), null=True, blank=True)
    order = models.PositiveIntegerField(_("Order"), default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = _("Post")
        verbose_name_plural = _("Posts")

    def __str__(self):
        return self.title_ar or self.title_en
