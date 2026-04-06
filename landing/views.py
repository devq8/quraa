from django.shortcuts import get_object_or_404, render

from .models import (
    Client,
    FeaturedPost,
    FooterColumn,
    HeroSlide,
    LandingSection,
    Service,
    SiteSettings,
    StatCounter,
    TeamMember,
    WelcomeSection,
)


def landing(request):
    """Landing page view: pass all editable content from models."""
    # Singleton / optional: use first() and allow None
    site_settings = SiteSettings.objects.first()
    welcome_section = WelcomeSection.objects.first()

    # Sections headings (by slug); default None for missing so template can use {% if sections.welcome %}
    section_slugs = ["welcome", "services", "blog", "clients", "team"]
    sections = {slug: None for slug in section_slugs}
    for s in LandingSection.objects.filter(slug__in=section_slugs):
        sections[s.slug] = s

    # Ordered lists
    hero_slides = list(HeroSlide.objects.filter(is_active=True))
    services = list(Service.objects.all())
    stat_counters = list(StatCounter.objects.all())
    featured_posts = list(FeaturedPost.objects.all())
    clients = list(Client.objects.all())
    team_members = list(TeamMember.objects.all())
    footer_columns = list(FooterColumn.objects.prefetch_related("links").all())

    context = {
        "site_settings": site_settings,
        "welcome_section": welcome_section,
        "sections": sections,
        "hero_slides": hero_slides,
        "services": services,
        "stat_counters": stat_counters,
        "featured_posts": featured_posts,
        "clients": clients,
        "team_members": team_members,
        "footer_columns": footer_columns,
    }
    return render(request, "landing.html", context)


def contact_us(request):
    """Contact us page."""
    site_settings = SiteSettings.objects.first()
    footer_columns = list(FooterColumn.objects.prefetch_related("links").all())
    context = {
        "site_settings": site_settings,
        "footer_columns": footer_columns,
        "user": request.user,
    }
    return render(request, "contact-us.html", context)


def post_detail(request, pk):
    """Single featured post page (FeaturedPost by pk)."""
    post = get_object_or_404(FeaturedPost, pk=pk)
    site_settings = SiteSettings.objects.first()
    footer_columns = list(FooterColumn.objects.prefetch_related("links").all())
    context = {
        "post": post,
        "site_settings": site_settings,
        "footer_columns": footer_columns,
        "user": request.user,
    }
    return render(request, "post.html", context)
