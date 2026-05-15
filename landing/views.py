import logging
from itertools import groupby

from django.http import Http404
from django.shortcuts import get_object_or_404, render

from core.models import Biography
from core.search import normalize_arabic

logger = logging.getLogger(__name__)

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


HIJRI_MONTHS_AR = [
    "", "محرّم", "صفر", "ربيع الأول", "ربيع الآخر",
    "جمادى الأولى", "جمادى الآخرة", "رجب", "شعبان",
    "رمضان", "شوال", "ذو القعدة", "ذو الحجة",
]
HIJRI_MONTHS_EN = [
    "", "Muharram", "Safar", "Rabi' al-Awwal", "Rabi' al-Thani",
    "Jumada al-Ula", "Jumada al-Akhirah", "Rajab", "Sha'ban",
    "Ramadan", "Shawwal", "Dhul-Qa'dah", "Dhul-Hijjah",
]
GREG_MONTHS_AR = [
    "", "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]
GREG_MONTHS_EN = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _format_date(year, month, day, months_ar, months_en, era_ar, era_en, approximate):
    if not year:
        return None
    ar_parts, en_parts = [], []
    if day:
        ar_parts.append(str(day))
        en_parts.append(str(day))
    if month and 1 <= month <= 12:
        ar_parts.append(months_ar[month])
        en_parts.append(months_en[month])
    ar_parts.append(f"{year} {era_ar}")
    en_parts.append(f"{year} {era_en}")
    ar = " ".join(ar_parts)
    en = " ".join(en_parts)
    is_full = bool(year and month and day)
    if approximate and not is_full:
        ar = ar + " تقريباً"
        en = "c. " + en
    return {"ar": ar, "en": en}


def _bio_dates(bio):
    return {
        "birth_hijri": _format_date(
            bio.birth_hijri_year, bio.birth_hijri_month, bio.birth_hijri_day,
            HIJRI_MONTHS_AR, HIJRI_MONTHS_EN, "هـ", "AH", bio.birth_date_approximate,
        ),
        "birth_greg": _format_date(
            bio.birth_greg_year, bio.birth_greg_month, bio.birth_greg_day,
            GREG_MONTHS_AR, GREG_MONTHS_EN, "م", "CE", bio.birth_date_approximate,
        ),
        "death_hijri": _format_date(
            bio.death_hijri_year, bio.death_hijri_month, bio.death_hijri_day,
            HIJRI_MONTHS_AR, HIJRI_MONTHS_EN, "هـ", "AH", bio.death_date_approximate,
        ),
        "death_greg": _format_date(
            bio.death_greg_year, bio.death_greg_month, bio.death_greg_day,
            GREG_MONTHS_AR, GREG_MONTHS_EN, "م", "CE", bio.death_date_approximate,
        ),
    }


def biography_detail(request, pk):
    """Public biography detail page; unpublished entries are visible only to staff."""
    qs = Biography.objects.select_related(
        "birthplace", "hometown", "death_location",
    ).prefetch_related(
        "attributes",
        "sources",
        "esnads__links__narrator",
        "teacher_relationships__teacher",
        "student_relationships__student",
    )
    biography = get_object_or_404(qs, pk=pk)
    if not biography.published and not request.user.is_staff:
        raise Http404()

    teachers = list(biography.teacher_relationships.all())
    students = list(biography.student_relationships.all())
    sources = list(biography.sources.all())
    esnads = list(biography.esnads.all())

    site_settings = SiteSettings.objects.first()
    footer_columns = list(FooterColumn.objects.prefetch_related("links").all())

    context = {
        "biography": biography,
        "dates": _bio_dates(biography),
        "attributes": list(biography.attributes.all()),
        "teachers": teachers,
        "students": students,
        "sources": sources,
        "esnads": esnads,
        "site_settings": site_settings,
        "footer_columns": footer_columns,
        "user": request.user,
    }
    return render(request, "biography.html", context)


def biographies_alphabetical(request):
    """All published biographies sorted alphabetically by name."""
    biographies = list(
        Biography.objects.filter(published=True)
        .select_related("hometown")
        .order_by("full_name_ar", "full_name_en")
    )
    site_settings = SiteSettings.objects.first()
    footer_columns = list(FooterColumn.objects.prefetch_related("links").all())
    context = {
        "biographies": biographies,
        "site_settings": site_settings,
        "footer_columns": footer_columns,
        "user": request.user,
    }
    return render(request, "biographies-alphabetical.html", context)


def biographies_by_city(request):
    """Published biographies grouped by hometown city."""
    qs = (
        Biography.objects.filter(published=True)
        .select_related("hometown")
        .order_by("hometown__city_ar", "hometown__city_en", "full_name_ar")
    )
    groups = [
        {"location": loc, "biographies": list(bios)}
        for loc, bios in groupby(qs, key=lambda b: b.hometown)
    ]
    site_settings = SiteSettings.objects.first()
    footer_columns = list(FooterColumn.objects.prefetch_related("links").all())
    context = {
        "groups": groups,
        "site_settings": site_settings,
        "footer_columns": footer_columns,
        "user": request.user,
    }
    return render(request, "biographies-by-city.html", context)


def search_results(request):
    """Search published biographies by Arabic/English name and alias.

    Matching is tashkeel-insensitive and treats multi-word queries as AND:
    every word in the (normalized) query must appear somewhere in the
    biography's normalized name/alias text.
    """
    query = (request.GET.get("q") or "").strip()

    logger.debug("search_results raw query=%r", query)
    results = []
    if query:
        words = normalize_arabic(query).split()

        logger.debug("search_results normalized words=%r", words)
        if words:
            qs = Biography.objects.filter(published=True)
            for word in words:
                qs = qs.filter(name_search__icontains=word)

            logger.debug("search_results SQL=%s", qs.query)
            results = list(qs.select_related("hometown").order_by("full_name_ar"))

    logger.info("search_results query=%r matched %d biographies", query, len(results))
    site_settings = SiteSettings.objects.first()
    footer_columns = list(FooterColumn.objects.prefetch_related("links").all())
    context = {
        "query": query,
        "results": results,
        "site_settings": site_settings,
        "footer_columns": footer_columns,
        "user": request.user,
    }
    return render(request, "search-results.html", context)
