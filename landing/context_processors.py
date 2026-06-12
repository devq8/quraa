from .models import SiteSettings


def site_settings(request):
    """Expose the SiteSettings singleton to every template (navbar, footer, etc.)."""
    return {"site_settings": SiteSettings.objects.first()}
