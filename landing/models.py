from django.db import models


class SiteSettings(models.Model):
    """Singleton-style settings: logo, site name, footer main block, copyright."""
    site_name_ar = models.CharField("Site name (Arabic)", max_length=255, default="المركز العالمي لتاريخ ووثائق القرآء")
    site_name_en = models.CharField("Site name (English)", max_length=255, default="The International Center for the History and Documentation of Quran Reciters")
    logo = models.ImageField("Logo", upload_to="landing/logo", blank=True, null=True)
    logo_dark = models.ImageField("Logo (dark)", upload_to="landing/logo", blank=True, null=True)
    favicon = models.ImageField("Favicon", upload_to="landing/favicon", blank=True, null=True)

    # Footer main block
    footer_title_ar = models.CharField("Footer title (Arabic)", max_length=255, blank=True)
    footer_title_en = models.CharField("Footer title (English)", max_length=255, blank=True)
    footer_description_ar = models.TextField("Footer description (Arabic)", blank=True)
    footer_description_en = models.TextField("Footer description (English)", blank=True)
    footer_button_text_ar = models.CharField("Footer button (Arabic)", max_length=100, default="سجّل الآن")
    footer_button_text_en = models.CharField("Footer button (English)", max_length=100, default="Register Now")
    footer_button_link = models.URLField("Footer button URL", blank=True)

    # Copyright
    copyright_ar = models.CharField("Copyright (Arabic)", max_length=255, default="المركز العالمي لتاريخ ووثائق القرآء. جميع الحقوق محفوظة.")
    copyright_en = models.CharField("Copyright (English)", max_length=255, default="The International Center for the History and Documentation of Quran Reciters. All rights reserved.")

    class Meta:
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"

    def __str__(self):
        return "Site settings"

    def save(self, *args, **kwargs):
        # Keep only one instance (singleton)
        self.pk = 1
        super().save(*args, **kwargs)


class LandingSection(models.Model):
    """Editable headings and leads for each landing section (welcome, services, blog, clients, team)."""
    SLUG_CHOICES = [
        ("welcome", "Welcome"),
        ("services", "Services"),
        ("blog", "Blog"),
        ("clients", "Clients"),
        ("team", "Team"),
    ]
    slug = models.SlugField(choices=SLUG_CHOICES, unique=True)
    heading_ar = models.CharField("Heading (Arabic)", max_length=255)
    heading_en = models.CharField("Heading (English)", max_length=255)
    lead_ar = models.CharField("Lead / subtitle (Arabic)", max_length=500, blank=True)
    lead_en = models.CharField("Lead / subtitle (English)", max_length=500, blank=True)

    class Meta:
        verbose_name = "Section"
        verbose_name_plural = "Sections"

    def __str__(self):
        return dict(self.SLUG_CHOICES).get(self.slug, self.slug)


class HeroSlide(models.Model):
    """Hero slider slides (title, subtitle, button, video or image)."""
    title_ar = models.CharField("Title (Arabic)", max_length=255)
    title_en = models.CharField("Title (English)", max_length=255)
    subtitle_ar = models.TextField("Subtitle (Arabic)", blank=True)
    subtitle_en = models.TextField("Subtitle (English)", blank=True)
    button_text_ar = models.CharField("Button text (Arabic)", max_length=100, default="اكتشف المزيد")
    button_text_en = models.CharField("Button text (English)", max_length=100, default="Explore more")
    button_link = models.CharField("Button link (URL or #anchor)", max_length=500, default="#welcome")
    # Media: either video path (e.g. relative to static or full URL) or image
    video_url = models.CharField(
        "Video URL or path",
        max_length=500,
        blank=True,
        help_text="e.g. path under static like 'video/quran_video.mp4' or full URL",
    )
    image = models.ImageField("Image (if no video)", upload_to="landing/hero", blank=True, null=True)
    order = models.PositiveIntegerField("Order", default=0)
    is_active = models.BooleanField("Active", default=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "Hero slide"
        verbose_name_plural = "Hero slides"

    def __str__(self):
        return self.title_ar or self.title_en


class WelcomeSection(models.Model):
    """Welcome block: heading, subheading, and image (single row)."""
    heading_ar = models.CharField("Heading (Arabic)", max_length=255)
    heading_en = models.CharField("Heading (English)", max_length=255)
    lead_ar = models.CharField("Lead (Arabic)", max_length=500, blank=True)
    lead_en = models.CharField("Lead (English)", max_length=500, blank=True)
    image = models.ImageField("Image", upload_to="landing/welcome", blank=True, null=True)

    class Meta:
        verbose_name = "Welcome section"
        verbose_name_plural = "Welcome section"

    def __str__(self):
        return self.heading_ar or self.heading_en

    def save(self, *args, **kwargs):
        # Single row: always pk=1
        self.pk = 1
        super().save(*args, **kwargs)


class Service(models.Model):
    """Services section items (icon, title, description, link)."""
    icon = models.CharField(
        "Icon class (FontAwesome)",
        max_length=100,
        help_text="e.g. fa fa-book, fa fa-clipboard-check",
    )
    title_ar = models.CharField("Title (Arabic)", max_length=255)
    title_en = models.CharField("Title (English)", max_length=255)
    description_ar = models.CharField("Description (Arabic)", max_length=500, blank=True)
    description_en = models.CharField("Description (English)", max_length=500, blank=True)
    link = models.URLField("Link", blank=True)
    order = models.PositiveIntegerField("Order", default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "Service"
        verbose_name_plural = "Services"

    def __str__(self):
        return self.title_ar or self.title_en


class StatCounter(models.Model):
    """Stats/counters section (icon, value, label)."""
    icon = models.CharField(
        "Icon class (FontAwesome)",
        max_length=100,
        help_text="e.g. fa fa-3x fa-book",
    )
    value_from = models.PositiveIntegerField("Animate from", default=0)
    value_to = models.PositiveIntegerField("Value to display")
    label_ar = models.CharField("Label (Arabic)", max_length=255)
    label_en = models.CharField("Label (English)", max_length=255)
    order = models.PositiveIntegerField("Order", default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "Stat counter"
        verbose_name_plural = "Stat counters"

    def __str__(self):
        return f"{self.value_to} – {self.label_ar or self.label_en}"


class FeaturedPost(models.Model):
    """Blog/featured posts shown on the landing page."""
    image = models.ImageField("Image", upload_to="landing/blog", blank=True, null=True)
    category_ar = models.CharField("Category (Arabic)", max_length=100, blank=True)
    category_en = models.CharField("Category (English)", max_length=100, blank=True)
    title_ar = models.CharField("Title (Arabic)", max_length=255)
    title_en = models.CharField("Title (English)", max_length=255, blank=True)
    excerpt_ar = models.TextField("Excerpt (Arabic)", blank=True)
    excerpt_en = models.TextField("Excerpt (English)", blank=True)
    url = models.URLField("Link", blank=True)
    published_at = models.DateField("Date", null=True, blank=True)
    order = models.PositiveIntegerField("Order", default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "Featured post"
        verbose_name_plural = "Featured posts"

    def __str__(self):
        return self.title_ar or self.title_en


class Client(models.Model):
    """Client/partner logos."""
    name = models.CharField("Name (alt text)", max_length=255)
    logo = models.ImageField("Logo", upload_to="landing/clients")
    link = models.URLField("Link", blank=True)
    order = models.PositiveIntegerField("Order", default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "Client"
        verbose_name_plural = "Clients"

    def __str__(self):
        return self.name


class TeamMember(models.Model):
    """Team section members."""
    name = models.CharField("Name", max_length=255)
    role = models.CharField("Role / title", max_length=255)
    bio = models.TextField("Short bio", blank=True)
    image = models.ImageField("Photo", upload_to="landing/team", blank=True, null=True)
    facebook_url = models.URLField("Facebook", blank=True)
    twitter_url = models.URLField("Twitter", blank=True)
    instagram_url = models.URLField("Instagram", blank=True)
    email = models.EmailField("Email", blank=True)
    order = models.PositiveIntegerField("Order", default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "Team member"
        verbose_name_plural = "Team members"

    def __str__(self):
        return self.name


class FooterColumn(models.Model):
    """Footer link column (e.g. Discover, Features, Pages, Support)."""
    title = models.CharField("Column title (legacy)", max_length=100, blank=True, help_text="Fallback if Arabic/English not set")
    title_ar = models.CharField("Column title (Arabic)", max_length=100, blank=True)
    title_en = models.CharField("Column title (English)", max_length=100, blank=True)
    order = models.PositiveIntegerField("Order", default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "Footer column"
        verbose_name_plural = "Footer columns"

    def __str__(self):
        return self.title_ar or self.title_en or self.title or "Footer column"


class FooterLink(models.Model):
    """Single link under a footer column."""
    column = models.ForeignKey(FooterColumn, on_delete=models.CASCADE, related_name="links")
    label = models.CharField("Label (legacy)", max_length=255, blank=True, help_text="Fallback if Arabic/English not set")
    label_ar = models.CharField("Label (Arabic)", max_length=255, blank=True)
    label_en = models.CharField("Label (English)", max_length=255, blank=True)
    url = models.URLField("URL", blank=True)
    order = models.PositiveIntegerField("Order", default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "Footer link"
        verbose_name_plural = "Footer links"

    def __str__(self):
        label = self.label_ar or self.label_en or self.label
        return f"{self.column}: {label}"
