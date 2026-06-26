from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from tinymce.widgets import TinyMCE

from .models import (
    SiteSettings,
    HeroSlide,
    Service,
    Post,
)

# Description fields that should use the rich-text editor in the admin.
RICH_TEXT_FIELDS = (
    "about_description_ar", "about_description_en",
    "services_description_ar", "services_description_en",
    "blog_description_ar", "blog_description_en",
    "contact_description_ar", "contact_description_en",
)


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = "__all__"
        widgets = {
            name: TinyMCE(mce_attrs={"directionality": "rtl" if name.endswith("_ar") else "ltr"})
            for name in RICH_TEXT_FIELDS
        }


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    form = SiteSettingsForm
    list_display = ("site_name_ar", "site_name_en")

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
    fieldsets = (
        (None, {"fields": ("site_name_ar", "site_name_en", "logo", "logo_dark", "favicon", "favicon_dark")}),
        (_("About us section"), {"fields": ("about_heading_ar", "about_heading_en", "about_subheading_ar", "about_subheading_en", "about_description_ar", "about_description_en", "about_image", "about_url")}),
        (_("Services section header"), {"fields": ("services_heading_ar", "services_heading_en", "services_subheading_ar", "services_subheading_en", "services_description_ar", "services_description_en")}),
        (_("Donate section"), {"fields": ("donate_heading_ar", "donate_heading_en", "donate_subheading_ar", "donate_subheading_en", "donate_button_text_ar", "donate_button_text_en", "donate_button_link")}),
        (_("Blog section header"), {"fields": ("blog_heading_ar", "blog_heading_en", "blog_subheading_ar", "blog_subheading_en", "blog_description_ar", "blog_description_en")}),
        (_("Contact section"), {"fields": ("contact_heading_ar", "contact_heading_en", "contact_subheading_ar", "contact_subheading_en", "contact_description_ar", "contact_description_en", "contact_email", "contact_phone", "contact_address_ar", "contact_address_en")}),
        (_("Social media links"), {"fields": ("facebook_url", "twitter_url", "instagram_url")}),
        (_("Search"), {"fields": ("search_results_per_page",)}),
        (_("Copyright"), {"fields": ("copyright_ar", "copyright_en")}),
    )


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ("title_ar", "title_en")

    def has_add_permission(self, request):
        return not HeroSlide.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("title_ar", "title_en", "icon", "order")
    list_editable = ("order",)
    ordering = ("order",)



class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = "__all__"
        widgets = {
            "body_ar": TinyMCE(mce_attrs={"directionality": "rtl"}),
            "body_en": TinyMCE(mce_attrs={"directionality": "ltr"}),
        }


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    form = PostForm
    list_display = ("title_ar", "title_en", "category_ar", "category_en", "show_as_featured", "published_at", "order")
    list_editable = ("show_as_featured", "order")
    list_filter = ("category_ar", "show_as_featured")
    ordering = ("order",)
    date_hierarchy = "published_at"
