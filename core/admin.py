import nested_admin
from adminsortable2.admin import SortableAdminBase, SortableInlineAdminMixin
from django.contrib import admin
from django.contrib import messages
from django.db import models
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _

from .models import (
    Attribute, Biography,
    Esnad, EsnadLink,
    EsnadTemplate, EsnadTemplateLink,
    Location, Source, TeacherStudentRelationship,
)


class SourceInline(nested_admin.NestedTabularInline):
    model = Source
    extra = 0
    fields = ("name_ar", "name_en", "link")
    verbose_name = _("Source")
    verbose_name_plural = _("Sources")


class TeacherInline(nested_admin.NestedTabularInline):
    """Teachers of this biography (relationships where this bio is the student)."""
    model = TeacherStudentRelationship
    fk_name = "student"
    extra = 0
    fields = ("teacher", "notes_ar", "notes_en")
    autocomplete_fields = ("teacher",)
    verbose_name = _("Teacher")
    verbose_name_plural = _("Teachers")


class StudentInline(nested_admin.NestedTabularInline):
    """Students of this biography (relationships where this bio is the teacher)."""
    model = TeacherStudentRelationship
    fk_name = "teacher"
    extra = 0
    fields = ("student", "notes_ar", "notes_en")
    autocomplete_fields = ("student",)
    verbose_name = _("Student")
    verbose_name_plural = _("Students")


class EsnadLinkNestedInline(nested_admin.NestedTabularInline):
    model = EsnadLink
    extra = 0
    fields = ("narrator",)
    ordering = ("order",)
    sortable_field_name = "order"
    verbose_name = _("Narrator")
    verbose_name_plural = _("Narrators")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "narrator":
            biography_id = request.resolver_match.kwargs.get("object_id")
            if biography_id:
                kwargs["queryset"] = Biography.objects.exclude(pk=biography_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class EsnadInline(nested_admin.NestedStackedInline):
    model = Esnad
    extra = 0
    fields = ()
    show_change_link = True
    inlines = [EsnadLinkNestedInline]
    verbose_name = _("Esnad")
    verbose_name_plural = _("Asanid")


@admin.register(Biography)
class BiographyAdmin(nested_admin.NestedModelAdmin):
    list_display = (
        "id", "full_name_ar", "full_name_en", "alias_ar",
        "birth_hijri_year", "birth_greg_year", "birth_date_approximate",
        "death_hijri_year", "death_greg_year", "death_date_approximate",
        "birthplace", "hometown", "death_location",
    )
    list_filter = ("birthplace", "hometown", "death_location", "attributes", "published")
    search_fields = ("full_name_ar", "full_name_en", "alias_ar", "alias_en")
    ordering = ("id", "full_name_ar")
    readonly_fields = (
        "birth_date_approximate",
        "death_date_approximate",
        "submitted_by",
        "last_modified_by",
        "created", "updated",
    )
    inlines = [SourceInline, TeacherInline, StudentInline, EsnadInline]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.submitted_by = request.user
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)

    fieldsets = (
        (None, {
            "fields": (
                ("full_name_ar", "full_name_en"),
                ("alias_ar", "alias_en"),
                "attributes", "published",
                "user",
            ),
        }),
        (_("Birth"), {
            "fields": (
                "birthplace", "hometown",
                ("birth_hijri_year", "birth_hijri_month", "birth_hijri_day"),
                ("birth_greg_year",  "birth_greg_month",  "birth_greg_day"),
                "birth_date_approximate",
            ),
        }),
        (_("Death"), {
            "fields": (
                "death_location",
                ("death_hijri_year", "death_hijri_month", "death_hijri_day"),
                ("death_greg_year",  "death_greg_month",  "death_greg_day"),
                "death_date_approximate",
            ),
        }),
        (_("Audit"), {
            "classes": ("collapse",),
            "fields": ("submitted_by", "last_modified_by", "created", "updated"),
        }),
    )


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("id", "city_ar", "city_en", "country_ar", "country_en")
    list_filter = ("country_ar",)
    search_fields = ("city_ar", "city_en", "country_ar", "country_en")
    ordering = ("id", "country_ar", "city_ar")
    fieldsets = (
        (None, {
            "fields": (
                ("city_ar", "city_en"),
                ("country_ar", "country_en"),
            ),
        }),
    )


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ("id", "short_name_ar", "short_name_en", "long_name_ar")
    search_fields = ("short_name_ar", "short_name_en", "long_name_ar", "long_name_en")
    ordering = ("id", "short_name_ar")
    fieldsets = (
        (None, {
            "fields": (
                ("short_name_ar", "short_name_en"),
                ("long_name_ar", "long_name_en"),
                ("description_ar", "description_en"),
            ),
        }),
    )


@admin.register(TeacherStudentRelationship)
class TeacherStudentRelationshipAdmin(admin.ModelAdmin):
    list_display = ("id", "teacher", "student", "created")
    list_filter = ()
    search_fields = (
        "teacher__full_name_ar", "teacher__full_name_en",
        "student__full_name_ar", "student__full_name_en",
    )
    ordering = ("teacher", "student")
    autocomplete_fields = ("teacher", "student")
    readonly_fields = ("created", "updated")
    fieldsets = (
        (None, {
            "fields": (
                ("teacher", "student"),
                ("notes_ar", "notes_en"),
            ),
        }),
        (_("Audit"), {
            "classes": ("collapse",),
            "fields": ("created", "updated"),
        }),
    )


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("id", "biography", "name_ar", "name_en", "link")
    search_fields = (
        "name_ar", "name_en",
        "biography__full_name_ar", "biography__full_name_en",
    )
    autocomplete_fields = ("biography",)
    readonly_fields = ("created", "updated")
    fieldsets = (
        (None, {
            "fields": (
                "biography",
                ("name_ar", "name_en"),
                "link",
            ),
        }),
        (_("Audit"), {
            "classes": ("collapse",),
            "fields": ("created", "updated"),
        }),
    )


class EsnadLinkInline(SortableInlineAdminMixin, admin.TabularInline):
    model = EsnadLink
    extra = 0
    fields = ("narrator",)
    ordering = ("order",)
    verbose_name = _("Narrator")
    verbose_name_plural = _("Narrators")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "narrator":
            esnad_id = request.resolver_match.kwargs.get("object_id")
            if esnad_id:
                try:
                    holder_id = Esnad.objects.values_list("biography_id", flat=True).get(pk=esnad_id)
                    kwargs["queryset"] = Biography.objects.exclude(pk=holder_id)
                except Esnad.DoesNotExist:
                    pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Esnad)
class EsnadAdmin(SortableAdminBase, admin.ModelAdmin):
    list_display = ("id", "chain_display", "created")
    search_fields = ("biography__full_name_ar", "biography__full_name_en")
    ordering = ("biography", "id")
    autocomplete_fields = ("biography",)
    readonly_fields = ("chain_display", "created", "updated")
    inlines = [EsnadLinkInline]
    change_form_template = "admin/core/esnad/change_form.html"
    fieldsets = (
        (None, {"fields": ("biography", "chain_display")}),
        (_("Audit"), {"classes": ("collapse",), "fields": ("created", "updated")}),
    )

    def get_urls(self):
        custom = [
            path(
                "<int:object_id>/apply-template/",
                self.admin_site.admin_view(self.apply_template_view),
                name="core_esnad_apply_template",
            ),
        ]
        return custom + super().get_urls()

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["esnad_templates"] = EsnadTemplate.objects.all()
        return super().changeform_view(request, object_id, form_url, extra_context)

    def apply_template_view(self, request, object_id):
        esnad = Esnad.objects.filter(pk=object_id).first()
        if not esnad:
            messages.error(request, _("Esnad not found."))
            return HttpResponseRedirect(reverse("admin:core_esnad_changelist"))

        template_id = request.POST.get("template_id")
        if not template_id:
            messages.warning(request, _("No template selected."))
            return HttpResponseRedirect(reverse("admin:core_esnad_change", args=[object_id]))

        template = EsnadTemplate.objects.filter(pk=template_id).prefetch_related(
            models.Prefetch(
                "links",
                queryset=EsnadTemplateLink.objects.select_related("narrator").order_by("order"),
            )
        ).first()
        if not template:
            messages.error(request, _("Template not found."))
            return HttpResponseRedirect(reverse("admin:core_esnad_change", args=[object_id]))

        links = [
            link for link in template.links.all()
            if link.narrator_id != esnad.biography_id
        ]
        EsnadLink.objects.filter(esnad=esnad).delete()
        EsnadLink.objects.bulk_create([
            EsnadLink(esnad=esnad, narrator=link.narrator, order=i)
            for i, link in enumerate(links, start=1)
        ])
        messages.success(request, _('Template "%(name)s" applied.') % {"name": template})
        return HttpResponseRedirect(reverse("admin:core_esnad_change", args=[object_id]))

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related(
                models.Prefetch(
                    "links",
                    queryset=EsnadLink.objects.select_related("narrator").order_by("order"),
                )
            )
        )

    @admin.display(description=_("Chain"))
    def chain_display(self, obj):
        return obj.chain_display()


class EsnadTemplateLinkInline(SortableInlineAdminMixin, admin.TabularInline):
    model = EsnadTemplateLink
    extra = 0
    fields = ("narrator",)
    autocomplete_fields = ("narrator",)
    ordering = ("order",)
    verbose_name = _("Narrator")
    verbose_name_plural = _("Narrators")


@admin.register(EsnadTemplate)
class EsnadTemplateAdmin(SortableAdminBase, admin.ModelAdmin):
    list_display = ("id", "name_ar", "name_en", "link_count", "created")
    search_fields = ("name_ar", "name_en")
    ordering = ("name_ar",)
    readonly_fields = ("created", "updated")
    inlines = [EsnadTemplateLinkInline]
    fieldsets = (
        (None, {"fields": (("name_ar", "name_en"),)}),
        (_("Audit"), {"classes": ("collapse",), "fields": ("created", "updated")}),
    )

    @admin.display(description=_("Narrators"))
    def link_count(self, obj):
        return obj.links.count()
