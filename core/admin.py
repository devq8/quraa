import nested_admin
from adminsortable2.admin import SortableAdminBase, SortableInlineAdminMixin
from django import forms
from django.contrib import admin
from django.contrib import messages
from django.db import models
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _, get_language
from . import csv_import
from .models import (
    Attribute, Biography,
    Esnad, EsnadLink,
    EsnadTemplate, EsnadTemplateLink,
    Location, Note, Source, TeacherStudentRelationship,
)


class CSVImportForm(forms.Form):
    """Upload form for the Biography importer (CSV or Excel .xlsx)."""
    csv_file = forms.FileField(
        label=_("CSV or Excel file"),
        help_text=_(
            "A UTF-8 CSV or an .xlsx file. Download the Excel template for "
            "dropdown lists of existing locations and attributes."
        ),
    )


def _lang_ordering(ar_fields, en_fields):
    """Return Arabic field tuple when the active UI language is Arabic, else English."""
    lang = get_language()
    return ar_fields if (lang and lang.startswith("ar")) else en_fields


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
    fields = ("teacher", "notes")
    autocomplete_fields = ("teacher", "notes")
    verbose_name = _("Teacher")
    verbose_name_plural = _("Teachers")


class StudentInline(nested_admin.NestedTabularInline):
    """Students of this biography (relationships where this bio is the teacher)."""
    model = TeacherStudentRelationship
    fk_name = "teacher"
    extra = 0
    fields = ("student", "notes")
    autocomplete_fields = ("student", "notes")
    verbose_name = _("Student")
    verbose_name_plural = _("Students")


class EsnadLinkNestedInline(nested_admin.SortableHiddenMixin, nested_admin.NestedTabularInline):
    model = EsnadLink
    extra = 0
    fields = ("narrator", "order")
    sortable_field_name = "order"
    autocomplete_fields = ("narrator",)
    verbose_name = _("Narrator")
    verbose_name_plural = _("Narrators")

    # def formfield_for_dbfield(self, db_field, request, **kwargs):
    #     if db_field.name == "order":
    #         kwargs["widget"] = forms.HiddenInput()
    #     return super().formfield_for_dbfield(db_field, request, **kwargs)

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
class BiographyAdmin(SortableAdminBase, nested_admin.NestedModelAdmin):
    list_display = (
        "id", "full_name_ar", "full_name_en", "alias_ar", "published",
        "birth_hijri_year", "birth_greg_year", 
        "death_hijri_year", "death_greg_year", 
        "birthplace", "hometown", "death_location",
        # "comments_ar", "comments_en",
    )
    list_filter = ("birthplace", "hometown", "death_location", "attributes", "published")
    search_fields = ("full_name_ar", "full_name_en", "alias_ar", "alias_en")
    readonly_fields = (
        "birth_hijri_approximate",
        "birth_greg_approximate",
        "death_hijri_approximate",
        "death_greg_approximate",
    )
    inlines = [TeacherInline, StudentInline, EsnadInline, SourceInline]
    change_form_template = "admin/core/biography/change_form.html"
    change_list_template = "admin/core/biography/change_list.html"

    # Session key holding the parsed-but-not-yet-committed CSV rows.
    _CSV_SESSION_KEY = "biography_csv_rows"

    # --- CSV import -----------------------------------------------------

    def get_urls(self):
        custom = [
            path(
                "import-csv/",
                self.admin_site.admin_view(self.import_csv_view),
                name="core_biography_import_csv",
            ),
            path(
                "import-csv/template-xlsx/",
                self.admin_site.admin_view(self.import_xlsx_template_view),
                name="core_biography_import_xlsx_template",
            ),
        ]
        return custom + super().get_urls()

    def import_xlsx_template_view(self, request):
        response = HttpResponse(
            csv_import.build_template_xlsx(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = "attachment; filename=biography_import_template.xlsx"
        return response

    def import_csv_view(self, request):
        if not self.has_add_permission(request):
            messages.error(request, _("You do not have permission to import biographies."))
            return HttpResponseRedirect(reverse("admin:core_biography_changelist"))

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": _("Import biographies from CSV"),
            "form": CSVImportForm(),
        }

        # Step 3: the user confirmed the review page — commit.
        if request.method == "POST" and request.POST.get("step") == "confirm":
            rows = request.session.get(self._CSV_SESSION_KEY)
            if not rows:
                messages.error(request, _("Your import session expired. Please upload the file again."))
                return HttpResponseRedirect(request.path)
            resolutions = {}
            location_choices = {}
            for key, value in request.POST.items():
                if key.startswith("resolve_"):
                    try:
                        resolutions[int(key[len("resolve_"):])] = value
                    except ValueError:
                        continue
                elif key.startswith("loc_"):
                    try:
                        location_choices[int(key[len("loc_"):])] = value
                    except ValueError:
                        continue
            summary = csv_import.commit_rows(
                rows, resolutions, request.user, location_choices
            )
            request.session.pop(self._CSV_SESSION_KEY, None)
            messages.success(
                request,
                _("Import complete: %(created)d created, %(updated)d updated, "
                  "%(skipped)d skipped, %(errors)d with errors.") % summary,
            )
            return HttpResponseRedirect(reverse("admin:core_biography_changelist"))

        # Step 2: a file was uploaded — parse, analyze, show the review page.
        if request.method == "POST":
            form = CSVImportForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    rows = csv_import.parse_upload(form.cleaned_data["csv_file"])
                except csv_import.CSVImportError as exc:
                    messages.error(request, str(exc))
                    context["form"] = form
                    return TemplateResponse(
                        request, "admin/core/biography/csv_import.html", context
                    )
                if not rows:
                    messages.warning(request, _("No data rows were found in the file."))
                    context["form"] = form
                    return TemplateResponse(
                        request, "admin/core/biography/csv_import.html", context
                    )
                request.session[self._CSV_SESSION_KEY] = rows
                plans = csv_import.analyze_rows(rows)
                location_specs = [
                    s for s in csv_import.collect_location_specs(plans)
                    if s["status"] == "new"
                ]
                context.update({
                    "plans": plans,
                    "new_plans": [p for p in plans if p.status == "new"],
                    "conflict_plans": [p for p in plans if p.status == "conflict"],
                    "identical_plans": [p for p in plans if p.status == "identical"],
                    "ambiguous_plans": [p for p in plans if p.status == "ambiguous"],
                    "error_plans": [p for p in plans if p.status == "error"],
                    "location_specs": location_specs,
                })
                return TemplateResponse(
                    request, "admin/core/biography/csv_import_review.html", context
                )
            context["form"] = form

        # Step 1: show the upload form.
        return TemplateResponse(request, "admin/core/biography/csv_import.html", context)

    def get_ordering(self, request):
        return _lang_ordering(("full_name_ar",), ("full_name_en", "full_name_ar"))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in ("birthplace", "hometown", "death_location"):
            ordering = _lang_ordering(
                ("country_ar", "city_ar"),
                ("country_en", "city_en", "country_ar", "city_ar"),
            )
            kwargs["queryset"] = Location.objects.order_by(*ordering)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    filter_horizontal = ("attributes",)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "attributes":
            ordering = _lang_ordering(
                ("short_name_ar",),
                ("short_name_en", "short_name_ar"),
            )
            kwargs["queryset"] = Attribute.objects.order_by(*ordering)
        formfield = super().formfield_for_manytomany(db_field, request, **kwargs)
        if db_field.name == "attributes":
            is_ar = (get_language() or "").startswith("ar")
            def _label(obj):
                long_name = (obj.long_name_ar if is_ar else obj.long_name_en) or obj.long_name_ar or obj.long_name_en or ""
                short_name = (obj.short_name_ar if is_ar else obj.short_name_en) or obj.short_name_ar or obj.short_name_en or ""
                if long_name and short_name:
                    return f"{long_name} ({short_name})"
                return long_name or short_name
            formfield.label_from_instance = _label
        return formfield

    def save_model(self, request, obj, form, change):
        if not change:
            obj.submitted_by = request.user
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            extra_context["biography_esnads"] = (
                Esnad.objects.filter(biography_id=object_id).order_by("id")
            )
            template_ordering = _lang_ordering(("name_ar",), ("name_en", "name_ar"))
            extra_context["esnad_templates"] = (
                EsnadTemplate.objects.only("id", "name_ar", "name_en").order_by(*template_ordering)
            )
        return super().changeform_view(request, object_id, form_url, extra_context)

    fieldsets = (
        (None, {
            "fields": (
                ("full_name_ar", "full_name_en"),
                ("alias_ar", "alias_en"),
                "attributes", "published",
                "comments_ar", "comments_en",
                "user",
            ),
        }),
        (_("Birth"), {
            "fields": (
                "birthplace", "hometown",
                ("birth_hijri_year", "birth_hijri_month", "birth_hijri_day"),
                ("birth_greg_year",  "birth_greg_month",  "birth_greg_day"),
                ("birth_hijri_approximate", "birth_greg_approximate"),
            ),
        }),
        (_("Death"), {
            "fields": (
                "death_location",
                ("death_hijri_year", "death_hijri_month", "death_hijri_day"),
                ("death_greg_year",  "death_greg_month",  "death_greg_day"),
                ("death_hijri_approximate", "death_greg_approximate"),
            ),
        }),
    )


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("id", "city_ar", "city_en", "country_ar", "country_en")
    list_filter = ("country_ar",)
    search_fields = ("city_ar", "city_en", "country_ar", "country_en")
    fieldsets = (
        (None, {
            "fields": (
                ("city_ar", "city_en"),
                ("country_ar", "country_en"),
            ),
        }),
    )

    def get_ordering(self, request):
        return _lang_ordering(
            ("country_ar", "city_ar"),
            ("country_en", "city_en", "country_ar", "city_ar"),
        )


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ("id", "short_name_ar", "short_name_en", "long_name_ar")
    search_fields = ("short_name_ar", "short_name_en", "long_name_ar", "long_name_en")
    fieldsets = (
        (None, {
            "fields": (
                ("short_name_ar", "short_name_en"),
                ("long_name_ar", "long_name_en"),
                ("description_ar", "description_en"),
            ),
        }),
    )

    def get_ordering(self, request):
        return _lang_ordering(("short_name_ar",), ("short_name_en", "short_name_ar"))


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("id", "short_name_ar", "short_name_en", "long_name_ar")
    search_fields = ("short_name_ar", "short_name_en", "long_name_ar", "long_name_en")
    fieldsets = (
        (None, {
            "fields": (
                ("short_name_ar", "short_name_en"),
                ("long_name_ar", "long_name_en"),
            ),
        }),
    )

    def get_ordering(self, request):
        return _lang_ordering(("short_name_ar",), ("short_name_en", "short_name_ar"))


class EsnadLinkInline(SortableInlineAdminMixin, admin.TabularInline):
    model = EsnadLink
    extra = 0
    fields = ("narrator", "order")
    ordering = ("order",)
    sortable_field_name = "order"
    autocomplete_fields = ("narrator",)
    verbose_name = _("Narrator")
    verbose_name_plural = _("Narrators")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "order":
            kwargs["widget"] = forms.HiddenInput()
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "narrator":
            esnad_id = request.resolver_match.kwargs.get("object_id")
            if esnad_id:
                holder_id = (
                    Esnad.objects
                    .filter(pk=esnad_id)
                    .values_list("biography_id", flat=True)
                    .first()
                )
                if holder_id:
                    kwargs["queryset"] = Biography.objects.exclude(pk=holder_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Esnad)
class EsnadAdmin(SortableAdminBase, admin.ModelAdmin):
    list_display = ("id", "biography", "chain_display", "created")
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
        if object_id:
            template_ordering = _lang_ordering(("name_ar",), ("name_en", "name_ar"))
            extra_context["esnad_templates"] = (
                EsnadTemplate.objects.only("id", "name_ar", "name_en").order_by(*template_ordering)
            )
        return super().changeform_view(request, object_id, form_url, extra_context)

    def apply_template_view(self, request, object_id):
        if request.method != "POST":
            return HttpResponseRedirect(reverse("admin:core_esnad_change", args=[object_id]))

        if not self.has_change_permission(request):
            messages.error(request, _("You do not have permission to modify this Esnad."))
            return HttpResponseRedirect(reverse("admin:core_esnad_changelist"))

        default_url = reverse("admin:core_esnad_change", args=[object_id])
        next_url = request.POST.get("next") or default_url
        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = default_url

        esnad = Esnad.objects.filter(pk=object_id).first()
        if not esnad:
            messages.error(request, _("Esnad not found."))
            return HttpResponseRedirect(reverse("admin:core_esnad_changelist"))

        template_id = request.POST.get("template_id")
        if not template_id:
            messages.warning(request, _("No template selected."))
            return HttpResponseRedirect(next_url)

        template = (
            EsnadTemplate.objects
            .filter(pk=template_id)
            .prefetch_related(
                models.Prefetch(
                    "links",
                    queryset=EsnadTemplateLink.objects.select_related("narrator").order_by("order"),
                )
            )
            .first()
        )
        if not template:
            messages.error(request, _("Template not found."))
            return HttpResponseRedirect(next_url)

        links = [l for l in template.links.all() if l.narrator_id != esnad.biography_id]

        from django.db import transaction
        with transaction.atomic():
            EsnadLink.objects.filter(esnad=esnad).delete()
            EsnadLink.objects.bulk_create([
                EsnadLink(esnad=esnad, narrator=link.narrator, order=i)
                for i, link in enumerate(links, start=1)
            ])

        messages.success(request, _('Template "%(name)s" applied.') % {"name": template})
        return HttpResponseRedirect(next_url)

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
    fields = ("narrator", "order")
    autocomplete_fields = ("narrator",)
    ordering = ("order",)
    sortable_field_name = "order"
    verbose_name = _("Narrator")
    verbose_name_plural = _("Narrators")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "order":
            kwargs["widget"] = forms.HiddenInput()
        return super().formfield_for_dbfield(db_field, request, **kwargs)

@admin.register(EsnadTemplate)
class EsnadTemplateAdmin(SortableAdminBase, admin.ModelAdmin):
    list_display = ("id", "name_ar", "name_en", "link_count", "created")
    search_fields = ("name_ar", "name_en")
    readonly_fields = ("created", "updated")
    inlines = [EsnadTemplateLinkInline]
    fieldsets = (
        (None, {"fields": (("name_ar", "name_en"),)}),
        (_("Audit"), {"classes": ("collapse",), "fields": ("created", "updated")}),
    )

    def get_ordering(self, request):
        return _lang_ordering(("name_ar",), ("name_en", "name_ar"))

    @admin.display(description=_("Narrators"))
    def link_count(self, obj):
        return obj.links.count()
