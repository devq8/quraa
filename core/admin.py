import nested_admin
from adminsortable2.admin import SortableAdminBase, SortableInlineAdminMixin
from django import forms
from django.contrib import admin
from django.contrib import messages
from django.db import models
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _, get_language
from . import biography_export, csv_import
from .models import (
    Attribute, Biography,
    Esnad, EsnadLink,
    EsnadTemplate, EsnadTemplateLink,
    Location, Reading, Source, TeacherStudentRelationship,
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


def _published_mode_label(mode):
    """Return the human-facing label for the import wizard's published mode."""
    labels = {
        "unpublished": _("Unpublished"),
        "published": _("Published"),
        "column": _("Use status column"),
    }
    return labels.get(mode, mode or "")


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
    verbose_name = _("Notable Teacher")
    verbose_name_plural = _("Notable Teachers")


class StudentInline(nested_admin.NestedTabularInline):
    """Students of this biography (relationships where this bio is the teacher)."""
    model = TeacherStudentRelationship
    fk_name = "teacher"
    extra = 0
    fields = ("student", "notes")
    autocomplete_fields = ("student", "notes")
    verbose_name = _("Notable Student")
    verbose_name_plural = _("Notable Students")


class HometownInlineForm(forms.ModelForm):
    class Meta:
        model = Biography.hometown.through
        fields = ("location",)
        labels = {"location": _("Location")}


class HometownInline(nested_admin.NestedTabularInline):
    model = Biography.hometown.through
    form = HometownInlineForm
    extra = 0
    autocomplete_fields = ("location",)
    verbose_name = _("Hometown")
    verbose_name_plural = _("Hometowns")


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
    verbose_name_plural = _("Transmission Chains")


@admin.register(Biography)
class BiographyAdmin(SortableAdminBase, nested_admin.NestedModelAdmin):
    list_display = (
        "id", "full_name_ar", "full_name_en", "alias_ar", "published", "is_featured",
        "birth_hijri_year", "birth_greg_year",
        "death_hijri_year", "death_greg_year",
        "birthplace", "get_hometowns", "death_location",
    )
    list_filter = ("birthplace", "hometown", "death_location", "attributes", "published", "is_featured")
    search_fields = ("full_name_ar", "full_name_en", "alias_ar", "alias_en")

    @admin.display(description=_("Hometown"))
    def get_hometowns(self, obj):
        return ", ".join(str(loc) for loc in obj.hometown.all())
    inlines = [TeacherInline, StudentInline, HometownInline, EsnadInline, SourceInline]
    change_form_template = "admin/core/biography/change_form.html"
    change_list_template = "admin/core/biography/change_list.html"

    # Session key holding the parsed-but-not-yet-committed CSV rows.
    _CSV_SESSION_KEY = "biography_csv_rows"
    # Session key for the multi-step reciters import wizard.
    _RECITERS_SESSION = "reciters_import_wizard"

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
            path(
                "export-csv/",
                self.admin_site.admin_view(self.export_csv_view),
                name="core_biography_export_csv",
            ),
            path(
                "export-xlsx/",
                self.admin_site.admin_view(self.export_xlsx_view),
                name="core_biography_export_xlsx",
            ),
            path(
                "find-duplicates/",
                self.admin_site.admin_view(self.find_duplicates_view),
                name="core_biography_find_duplicates",
            ),
            path(
                "live-duplicates/",
                self.admin_site.admin_view(self.live_duplicates_view),
                name="core_biography_live_duplicates",
            ),
            path(
                "merge-confirm/",
                self.admin_site.admin_view(self.merge_confirm_view),
                name="core_biography_merge_confirm",
            ),
            path(
                "import-reciters/",
                self.admin_site.admin_view(self.import_reciters_view),
                name="core_biography_import_reciters",
            ),
        ]
        return custom + super().get_urls()

    def _export_queryset(self, request):
        """Return the current admin changelist queryset with filters applied."""
        changelist = self.get_changelist_instance(request)
        return changelist.get_queryset(request)

    def _export_filename(self, extension):
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        return f"biographies_export_{timestamp}.{extension}"

    def export_csv_view(self, request):
        if not self.has_view_permission(request):
            messages.error(request, _("You do not have permission to export biographies."))
            return HttpResponseRedirect(reverse("admin:core_biography_changelist"))

        response = HttpResponse(
            biography_export.build_csv(self._export_queryset(request)),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{self._export_filename("csv")}"'
        )
        return response

    def export_xlsx_view(self, request):
        if not self.has_view_permission(request):
            messages.error(request, _("You do not have permission to export biographies."))
            return HttpResponseRedirect(reverse("admin:core_biography_changelist"))

        response = HttpResponse(
            biography_export.build_xlsx(self._export_queryset(request)),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{self._export_filename("xlsx")}"'
        )
        return response

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
                    "potential_duplicate_plans": [p for p in plans if p.status == "potential_duplicate"],
                    "error_plans": [p for p in plans if p.status == "error"],
                    "location_specs": location_specs,
                })
                return TemplateResponse(
                    request, "admin/core/biography/csv_import_review.html", context
                )
            context["form"] = form

        # Step 1: show the upload form.
        return TemplateResponse(request, "admin/core/biography/csv_import.html", context)

    # --- Find duplicates / merge ----------------------------------------

    @admin.action(description=_("Merge selected biographies (select exactly 2)"))
    def merge_biographies_action(self, request, queryset):
        if queryset.count() != 2:
            self.message_user(
                request,
                _("Please select exactly 2 biographies to merge."),
                level=messages.ERROR,
            )
            return
        ids = list(queryset.values_list("pk", flat=True))
        url = reverse("admin:core_biography_merge_confirm")
        return HttpResponseRedirect(f"{url}?ids={ids[0]},{ids[1]}")

    actions = ["merge_biographies_action"]

    def find_duplicates_view(self, request):
        if not self.has_change_permission(request):
            messages.error(request, _("You do not have permission to view duplicates."))
            return HttpResponseRedirect(reverse("admin:core_biography_changelist"))

        from .merge_utils import build_duplicate_candidates

        fuzzy = request.GET.get("fuzzy") == "1"
        candidates = build_duplicate_candidates(fuzzy=fuzzy)

        for c in candidates:
            c.similarity_pct = int(c.similarity * 100)

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": _("Find Duplicate Biographies"),
            "candidates": candidates,
            "exact_candidates": [c for c in candidates if c.match_type == "exact"],
            "cross_candidates": [c for c in candidates if c.match_type == "cross_field"],
            "partial_candidates": [c for c in candidates if c.match_type == "partial"],
            "fuzzy_candidates": [c for c in candidates if c.match_type == "fuzzy"],
            "fuzzy": fuzzy,
        }
        return TemplateResponse(
            request, "admin/core/biography/find_duplicates.html", context
        )

    def live_duplicates_view(self, request):
        if not self.has_view_permission(request):
            return JsonResponse({"error": str(_("Permission denied."))}, status=403)

        from .merge_utils import find_similar_to
        from .search import normalize_arabic

        query = request.GET.get("q", "")
        if len(normalize_arabic(query)) < 3:
            return JsonResponse({"results": []})

        try:
            exclude_pk = int(request.GET.get("exclude_id") or 0) or None
        except (TypeError, ValueError):
            exclude_pk = None

        results = []
        for bio, match_type, match_fields, similarity in find_similar_to(
            query, exclude_pk=exclude_pk
        )[:8]:
            results.append({
                "id": bio.pk,
                "full_name_ar": bio.full_name_ar,
                "full_name_en": bio.full_name_en,
                "alias_ar": bio.alias_ar,
                "alias_en": bio.alias_en,
                "match_type": match_type,
                "match_fields": match_fields,
                "similarity": int(similarity * 100),
                "url": reverse("admin:core_biography_change", args=[bio.pk]),
            })

        return JsonResponse({"results": results})

    def merge_confirm_view(self, request):
        if not self.has_change_permission(request):
            messages.error(request, _("You do not have permission to merge biographies."))
            return HttpResponseRedirect(reverse("admin:core_biography_changelist"))

        raw = request.GET.get("ids") or request.POST.get("ids", "")
        try:
            id_a, id_b = [int(x.strip()) for x in raw.split(",")]
        except (ValueError, TypeError):
            messages.error(request, _("Invalid biography selection."))
            return HttpResponseRedirect(reverse("admin:core_biography_changelist"))

        try:
            bio_a = Biography.objects.get(pk=id_a)
            bio_b = Biography.objects.get(pk=id_b)
        except Biography.DoesNotExist:
            messages.error(request, _("One or both biographies could not be found."))
            return HttpResponseRedirect(reverse("admin:core_biography_changelist"))

        if request.method == "POST" and request.POST.get("step") == "confirm":
            try:
                primary_id = int(request.POST.get("primary_id", 0))
                duplicate_id = int(request.POST.get("duplicate_id", 0))
            except (ValueError, TypeError):
                messages.error(request, _("Invalid merge selection."))
                return HttpResponseRedirect(reverse("admin:core_biography_changelist"))

            try:
                primary = Biography.objects.get(pk=primary_id)
                duplicate = Biography.objects.get(pk=duplicate_id)
            except Biography.DoesNotExist:
                messages.error(request, _("One or both biographies could not be found."))
                return HttpResponseRedirect(reverse("admin:core_biography_changelist"))

            field_choices = {}
            for key, value in request.POST.items():
                if key.startswith("choice_") and value in ("a", "b"):
                    field_name = key[len("choice_"):]
                    field_choices[field_name] = value

            from .merge_utils import merge_biographies as do_merge
            log = do_merge(primary, duplicate, field_choices, dry_run=False)

            for level, msg in log:
                if level == "warning":
                    messages.warning(request, msg)
                elif level == "error":
                    messages.error(request, msg)

            messages.success(
                request,
                _("Biography #%(dup)d merged into #%(pri)d successfully.")
                % {"dup": duplicate_id, "pri": primary_id},
            )
            return HttpResponseRedirect(
                reverse("admin:core_biography_change", args=[primary_id])
            )

        # GET — show the confirmation form
        from .merge_utils import compute_field_resolutions

        resolutions = compute_field_resolutions(bio_a, bio_b)

        def _count_display(count):
            return str(count) if count else "—"

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": _("Merge Biographies"),
            "bio_a": bio_a,
            "bio_b": bio_b,
            "ids": raw,
            "resolutions": resolutions,
            "attributes_a": ", ".join(str(a) for a in bio_a.attributes.all()) or "—",
            "attributes_b": ", ".join(str(a) for a in bio_b.attributes.all()) or "—",
            "hometown_a": ", ".join(str(h) for h in bio_a.hometown.all()) or "—",
            "hometown_b": ", ".join(str(h) for h in bio_b.hometown.all()) or "—",
            "teachers_a": _count_display(bio_a.teacher_relationships.count()),
            "teachers_b": _count_display(bio_b.teacher_relationships.count()),
            "students_a": _count_display(bio_a.student_relationships.count()),
            "students_b": _count_display(bio_b.student_relationships.count()),
            "sources_a": _count_display(bio_a.sources.count()),
            "sources_b": _count_display(bio_b.sources.count()),
            "esnads_a": _count_display(bio_a.esnads.count()),
            "esnads_b": _count_display(bio_b.esnads.count()),
        }
        return TemplateResponse(
            request, "admin/core/biography/merge_confirm.html", context
        )

    def import_reciters_view(self, request):  # noqa: C901
        """Multi-step wizard for importing biographies from a custom Arabic CSV."""
        from . import import_reciters_wizard as wiz

        if not self.has_add_permission(request):
            messages.error(request, _("You do not have permission to import biographies."))
            return HttpResponseRedirect(reverse("admin:core_biography_changelist"))

        def redirect_to(s):
            return HttpResponseRedirect(f"{request.path}?step={s}")

        def save_session(data):
            request.session[self._RECITERS_SESSION] = data
            request.session.modified = True

        session = request.session.get(self._RECITERS_SESSION) or {}
        step = request.GET.get("step", "upload")

        base_ctx = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "wizard_url": request.path,
        }

        # ── POST handlers ──────────────────────────────────────────────────────
        if request.method == "POST":
            post_step = request.POST.get("step", step)

            if post_step == "upload":
                upload = request.FILES.get("csv_file")
                published_mode = request.POST.get("published_mode", "unpublished")
                if not upload:
                    messages.error(request, _("Please select a CSV file."))
                    return redirect_to("upload")
                try:
                    rows, stats, _csv_text = wiz.scan_csv_file(upload)
                except Exception as exc:
                    messages.error(request, f"Error reading file: {exc}")
                    return redirect_to("upload")
                if not rows:
                    messages.error(request, _("No data rows found in the file."))
                    return redirect_to("upload")
                save_session({
                    "published_mode": published_mode,
                    "rows": rows,
                    "stats": stats,
                    "date_decisions": {},
                    "location_decisions": {},
                    "attr_decisions": {},
                })
                return redirect_to("scan")

            # All subsequent steps require an active session.
            if not session or "rows" not in session:
                messages.error(request, _("Session expired. Please upload the file again."))
                return redirect_to("upload")

            rows = session["rows"]
            stats = session.get("stats", {})

            if post_step == "scan":
                if stats.get("ambiguous_dates", 0) > 0:
                    return redirect_to("dates")
                if stats.get("missing_countries", 0) > 0:
                    return redirect_to("locations")
                if stats.get("fuzzy_attrs", 0) + stats.get("missing_attrs", 0) > 0:
                    return redirect_to("attributes")
                return redirect_to("commit")

            elif post_step == "dates":
                date_decisions = {}
                for idx, row in enumerate(rows):
                    for prefix in ("birth", "death"):
                        if not row.get(f"{prefix}_needs_confirm"):
                            continue
                        parsed = dict(row[f"{prefix}_parsed"])
                        action = request.POST.get(f"date_{idx}_{prefix}_action", "keep")
                        if action == "empty":
                            parsed["calendar"] = None
                            parsed["year"] = None
                        elif action == "alt":
                            import re as _re2
                            m = _re2.search(r"وقيل\s+(\d+)هـ", parsed.get("raw", ""))
                            if m:
                                parsed["year"] = int(m.group(1))
                                parsed["approximate"] = True
                        elif action == "manual":
                            year_str = request.POST.get(f"date_{idx}_{prefix}_year", "")
                            cal_str = request.POST.get(f"date_{idx}_{prefix}_cal", "hijri")
                            approx = request.POST.get(f"date_{idx}_{prefix}_approx") == "1"
                            if year_str.isdigit():
                                parsed["year"] = int(year_str)
                                parsed["calendar"] = cal_str
                                parsed["approximate"] = approx
                            else:
                                parsed["calendar"] = None
                                parsed["year"] = None
                        date_decisions[f"{idx}_{prefix}"] = parsed
                session["date_decisions"] = date_decisions
                save_session(session)
                if stats.get("missing_countries", 0) > 0:
                    return redirect_to("locations")
                if stats.get("fuzzy_attrs", 0) + stats.get("missing_attrs", 0) > 0:
                    return redirect_to("attributes")
                return redirect_to("commit")

            elif post_step == "locations":
                unique_cities = wiz.get_unique_missing_cities(rows)
                location_decisions = {}
                for i, city in enumerate(unique_cities):
                    loc_type = request.POST.get(f"loc_{i}_type", "city")
                    if loc_type == "region":
                        location_decisions[city] = {"city_ar": "", "country_ar": city}
                    elif loc_type == "new":
                        new_city = request.POST.get(f"loc_{i}_new_city", "").strip()
                        new_country = request.POST.get(f"loc_{i}_new_country", "").strip()
                        location_decisions[city] = {"city_ar": new_city, "country_ar": new_country}
                    else:  # "city"
                        country = request.POST.get(f"loc_{i}_country", "").strip()
                        location_decisions[city] = {"city_ar": city, "country_ar": country}
                session["location_decisions"] = location_decisions
                save_session(session)
                if stats.get("fuzzy_attrs", 0) + stats.get("missing_attrs", 0) > 0:
                    return redirect_to("attributes")
                return redirect_to("commit")

            elif post_step == "attributes":
                fuzzy_attrs = wiz.get_unique_fuzzy_attrs(rows)
                missing_attrs = wiz.get_unique_missing_attrs(rows)
                attr_decisions = {}
                for i, item in enumerate(fuzzy_attrs):
                    action = request.POST.get(f"fuzzy_{i}_action", "accept")
                    attr_decisions[item["name"]] = {
                        "action": action,
                        "match_pk": item["match_pk"],
                        "long_name": item["name"],
                    }
                for i, name in enumerate(missing_attrs):
                    skip = request.POST.get(f"missing_{i}_skip") == "1"
                    if skip:
                        attr_decisions[name] = {"action": "skip"}
                    else:
                        long_name = (
                            request.POST.get(f"missing_{i}_long_name", "").strip() or name
                        )
                        attr_decisions[name] = {"action": "create", "long_name": long_name}
                session["attr_decisions"] = attr_decisions
                save_session(session)
                return redirect_to("commit")

            elif post_step == "commit":
                try:
                    phase3_stats, bio_map = wiz.commit_phase3(
                        rows,
                        session.get("published_mode", "unpublished"),
                        session.get("date_decisions", {}),
                        session.get("location_decisions", {}),
                        session.get("attr_decisions", {}),
                    )
                except Exception as exc:
                    messages.error(request, f"Import failed: {exc}")
                    return redirect_to("commit")
                phase4_scan = wiz.pre_scan_phase4(rows, bio_map)
                session["phase3_stats"] = phase3_stats
                session["bio_map"] = bio_map
                session["phase4_scan"] = phase4_scan
                save_session(session)
                return redirect_to("relationships")

            elif post_step == "relationships":
                fuzzy_matches = session.get("phase4_scan", {}).get("fuzzy_matches", [])
                unmatched = session.get("phase4_scan", {}).get("unmatched", [])
                rel_decisions = {"fuzzy": {}, "unmatched": {}}
                for i, item in enumerate(fuzzy_matches):
                    action = request.POST.get(f"fuzzy_{i}_action", "link")
                    rel_decisions["fuzzy"][item["person_name"]] = {
                        "action": action,
                        "matched_pk": item["matched_pk"],
                    }
                for i, item in enumerate(unmatched):
                    action = request.POST.get(f"unmatched_{i}_action", "stub")
                    rel_decisions["unmatched"][item["person_name"]] = {"action": action}
                try:
                    phase4_stats = wiz.commit_phase4(
                        rows,
                        session.get("bio_map", {}),
                        rel_decisions,
                    )
                except Exception as exc:
                    messages.error(request, f"Relationship linking failed: {exc}")
                    return redirect_to("relationships")
                combined = {**session.get("phase3_stats", {})}
                for k, v in phase4_stats.items():
                    combined[k] = combined.get(k, 0) + v
                session["results"] = combined
                save_session(session)
                return redirect_to("results")

        # ── GET handlers ───────────────────────────────────────────────────────
        if step == "upload":
            return TemplateResponse(request, "admin/core/biography/import_reciters_upload.html", {
                **base_ctx, "title": _("Import Reciters CSV"),
            })

        if not session or "rows" not in session:
            messages.error(request, _("Session expired. Please start the import again."))
            return redirect_to("upload")

        rows = session.get("rows", [])
        stats = session.get("stats", {})

        if step == "scan":
            published_mode = session.get("published_mode")
            return TemplateResponse(request, "admin/core/biography/import_reciters_scan.html", {
                **base_ctx,
                "title": _("Import — Scan Results"),
                "stats": stats,
                "published_mode": published_mode,
                "published_mode_label": _published_mode_label(published_mode),
            })

        if step == "dates":
            import re as _re3
            ambiguous = []
            for idx, row in enumerate(rows):
                for prefix in ("birth", "death"):
                    if not row.get(f"{prefix}_needs_confirm"):
                        continue
                    parsed = row[f"{prefix}_parsed"]
                    raw_text = parsed.get("raw", "")
                    alt_m = _re3.search(r"وقيل\s+(\d+)هـ", raw_text)
                    ambiguous.append({
                        "idx": idx,
                        "prefix": prefix,
                        "name": row["full_name_ar"],
                        "label": _("Birth") if prefix == "birth" else _("Death"),
                        "raw": raw_text,
                        "year": parsed.get("year"),
                        "calendar": parsed.get("calendar"),
                        "approximate": parsed.get("approximate"),
                        "alt_year": int(alt_m.group(1)) if alt_m else None,
                    })
            return TemplateResponse(request, "admin/core/biography/import_reciters_dates.html", {
                **base_ctx,
                "title": _("Import — Resolve Ambiguous Dates"),
                "ambiguous_dates": ambiguous,
            })

        if step == "locations":
            unique_cities = wiz.get_unique_missing_cities(rows)
            all_locations = Location.objects.values_list("country_ar", flat=True)
            existing_countries = sorted({c.strip() for c in all_locations if c and c.strip()})
            return TemplateResponse(request, "admin/core/biography/import_reciters_locations.html", {
                **base_ctx,
                "title": _("Import — Resolve Missing Countries"),
                "unique_cities": list(enumerate(unique_cities)),
                "existing_countries": existing_countries,
            })

        if step == "attributes":
            fuzzy_attrs = wiz.get_unique_fuzzy_attrs(rows)
            missing_attrs = wiz.get_unique_missing_attrs(rows)
            return TemplateResponse(request, "admin/core/biography/import_reciters_attributes.html", {
                **base_ctx,
                "title": _("Import — Resolve Attributes"),
                "fuzzy_attrs": list(enumerate(fuzzy_attrs)),
                "missing_attrs": list(enumerate(missing_attrs)),
            })

        if step == "commit":
            published_mode = session.get("published_mode")
            return TemplateResponse(request, "admin/core/biography/import_reciters_commit.html", {
                **base_ctx,
                "title": _("Import — Ready to Commit"),
                "stats": stats,
                "published_mode": published_mode,
                "published_mode_label": _published_mode_label(published_mode),
                "date_decisions_count": len(session.get("date_decisions", {})),
                "location_decisions_count": len(session.get("location_decisions", {})),
                "attr_decisions_count": len(session.get("attr_decisions", {})),
            })

        if step == "relationships":
            phase4_scan = session.get("phase4_scan", {})
            return TemplateResponse(
                request,
                "admin/core/biography/import_reciters_relationships.html",
                {
                    **base_ctx,
                    "title": _("Import — Confirm Relationships"),
                    "fuzzy_matches": list(enumerate(phase4_scan.get("fuzzy_matches", []))),
                    "unmatched": list(enumerate(phase4_scan.get("unmatched", []))),
                    "detected_readings": phase4_scan.get("detected_readings", []),
                    "phase3_stats": session.get("phase3_stats", {}),
                },
            )

        if step == "results":
            results = session.get("results", {})
            bio_pks = list(session.get("bio_map", {}).values())
            request.session.pop(self._RECITERS_SESSION, None)
            _MAX_SHOWN = 300
            imported_bios = list(
                Biography.objects.filter(pk__in=bio_pks)
                .values("pk", "full_name_ar", "alias_ar",
                        "death_hijri_year", "death_greg_year", "published")
                .order_by("full_name_ar")[:_MAX_SHOWN]
            )
            return TemplateResponse(request, "admin/core/biography/import_reciters_results.html", {
                **base_ctx,
                "title": _("Import — Complete"),
                "results": results,
                "imported_bios": imported_bios,
                "imported_bios_total": len(bio_pks),
                "imported_bios_truncated": len(bio_pks) > _MAX_SHOWN,
            })

        return redirect_to("upload")

    def get_ordering(self, request):
        return _lang_ordering(("full_name_ar",), ("full_name_en", "full_name_ar"))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in ("birthplace", "death_location"):
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
                ("is_female", "published", "is_featured"),
                "image",
                ("featured_summary_ar", "featured_summary_en"),
                "comments_ar", "comments_en",
                "attributes", "user",
            ),
        }),
        (_("Birth"), {
            "fields": (
                "birthplace",
                ("birth_hijri_year", "birth_hijri_month", "birth_hijri_day"),
                ("birth_greg_year",  "birth_greg_month",  "birth_greg_day"),
                ("birth_hijri_approximate", "birth_greg_approximate"),
                "birth_date_raw_ar",
            ),
        }),
        (_("Death"), {
            "fields": (
                "death_location",
                ("death_hijri_year", "death_hijri_month", "death_hijri_day"),
                ("death_greg_year",  "death_greg_month",  "death_greg_day"),
                ("death_hijri_approximate", "death_greg_approximate"),
                "death_date_raw_ar",
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


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ("id", "description_ar", "description_en")
    search_fields = ("description_ar", "description_en")
    fieldsets = (
        (None, {
            "fields": (
                "description_ar",
                "description_en",
            ),
        }),
    )


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
