from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "username", "user_type", "is_staff", "is_active", "date_joined")
    list_filter = ("user_type", "is_staff", "is_superuser", "is_active")
    search_fields = ("email", "username", "first_name", "last_name")
    ordering = ("-date_joined",)
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name")}),
        (
            _("Role & permissions"),
            {
                "fields": ("user_type", "is_active", "groups", "user_permissions"),
                "description": _(
                    "User type: Admin (full access), Staff (manage via groups above), Reciter (limited)."
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "user_type", "password1", "password2"),
            },
        ),
    )

    readonly_fields = ("last_login", "date_joined")

    def get_readonly_fields(self, request, obj=None):
        # Only superusers can change user_type and permissions
        if not request.user.is_superuser and obj is not None:
            return list(super().get_readonly_fields(request, obj)) + [
                "user_type",
                "groups",
                "user_permissions",
            ]
        return super().get_readonly_fields(request, obj)
