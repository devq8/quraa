from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Reciter


@admin.register(Reciter)
class ReciterAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "birth_year", "death_year", "birthplace", "hometown")
    list_filter = ("birthplace", "hometown")
    search_fields = ("name", "title", "teachers", "students", "authored_books", "source")
    ordering = ("id", "name")
    list_editable = ()  # optional: add fields for quick edit
    readonly_fields = ("created", "updated")

    fieldsets = (
        (None, {"fields": ("name", "title")}),
        (
            _("Birth & origin"),
            {"fields": ("birth_year", "birthplace", "hometown", "school")},
        ),
        (
            _("Readings & path"),
            {"fields": ("teachers", "readings", "path", "location_of_reading")},
        ),
        (_("Students & works"), {"fields": ("students", "authored_books")}),
        (
            _("Death & source"),
            {"fields": ("death_year", "age", "death_location", "source")},
        ),
        (_("Meta"), {"fields": ("created", "updated")}),
    )
