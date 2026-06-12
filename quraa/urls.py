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
from django.shortcuts import redirect
from django.urls import path, include

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
    path("accounts/logout/", logout_redirect_landing, name="logout"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("landing.urls")),
]
# With DEBUG=False, uploads use S3; image URLs point to the bucket (no Django route).
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
