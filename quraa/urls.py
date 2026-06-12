"""quraa URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import logout
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.urls import path, include, reverse_lazy

from core import views as core_views


def logout_redirect_landing(request):
    """Log out and always redirect to the landing page (no 'Logged out' template)."""
    logout(request)
    return redirect("/")


def admin_logout_redirect(request, extra_context=None):
    """Log out and always redirect to the landing page (no 'Logged out' template)."""
    return logout_redirect_landing(request)


admin.site.logout = admin_logout_redirect

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("tinymce/", include("tinymce.urls")),
    path("admin/", admin.site.urls),
    path("accounts/login/", core_views.login_view, name="login"),
    path("accounts/signup/", core_views.signup_view, name="signup"),
    path("accounts/logout/", logout_redirect_landing, name="logout"),
    # Password reset flow (Django's built-in, secure token-based views) styled
    # with project templates. Defined before the auth-urls include so these
    # names resolve to our templates rather than Django's defaults.
    path(
        "accounts/password_reset/",
        auth_views.PasswordResetView.as_view(
            template_name="reset-password.html",
            email_template_name="reset-password-email.html",
            subject_template_name="reset-password-subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "accounts/password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="reset-password-done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="reset-password-confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="reset-password-complete.html"
        ),
        name="password_reset_complete",
    ),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("landing.urls")),
]
# With DEBUG=False, uploads use S3; image URLs point to the bucket (no Django route).
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
