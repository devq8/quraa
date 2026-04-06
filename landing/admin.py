from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import (
    SiteSettings,
    LandingSection,
    HeroSlide,
    WelcomeSection,
    Service,
    StatCounter,
    FeaturedPost,
    Client,
    TeamMember,
    FooterColumn,
    FooterLink,
)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("site_name_ar", "site_name_en")

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()
    fieldsets = (
        (None, {"fields": ("site_name_ar", "site_name_en", "logo", "logo_dark", "favicon")}),
        (_("Footer main block"), {"fields": ("footer_title_ar", "footer_title_en", "footer_description_ar", "footer_description_en", "footer_button_text_ar", "footer_button_text_en", "footer_button_link")}),
        (_("Copyright"), {"fields": ("copyright_ar", "copyright_en")}),
    )


@admin.register(LandingSection)
class LandingSectionAdmin(admin.ModelAdmin):
    list_display = ("slug", "heading_ar", "heading_en")
    list_editable = ("heading_ar", "heading_en")


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ("title_ar", "title_en", "order", "is_active")
    list_editable = ("order", "is_active")
    list_filter = ("is_active",)
    ordering = ("order",)


@admin.register(WelcomeSection)
class WelcomeSectionAdmin(admin.ModelAdmin):
    list_display = ("heading_ar", "heading_en")

    def has_add_permission(self, request):
        return not WelcomeSection.objects.exists()


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("title_ar", "title_en", "icon", "order")
    list_editable = ("order",)
    ordering = ("order",)


@admin.register(StatCounter)
class StatCounterAdmin(admin.ModelAdmin):
    list_display = ("label_ar", "label_en", "value_to", "icon", "order")
    list_editable = ("value_to", "order")
    ordering = ("order",)


@admin.register(FeaturedPost)
class FeaturedPostAdmin(admin.ModelAdmin):
    list_display = ("title_ar", "title_en", "category_ar", "category_en", "published_at", "order")
    list_editable = ("order",)
    list_filter = ("category_ar",)
    ordering = ("order",)
    date_hierarchy = "published_at"


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    list_editable = ("order",)
    ordering = ("order",)


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "order")
    list_editable = ("order",)
    ordering = ("order",)
    search_fields = ("name", "role")


class FooterLinkInline(admin.TabularInline):
    model = FooterLink
    extra = 1
    ordering = ("order",)


@admin.register(FooterColumn)
class FooterColumnAdmin(admin.ModelAdmin):
    list_display = ("title_ar", "title_en", "title", "order")
    list_editable = ("order",)
    inlines = [FooterLinkInline]
    ordering = ("order",)


@admin.register(FooterLink)
class FooterLinkAdmin(admin.ModelAdmin):
    list_display = ("label_ar", "label_en", "column", "url", "order")
    list_editable = ("order",)
    list_filter = ("column",)
    ordering = ("order",)
