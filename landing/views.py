import logging
from difflib import SequenceMatcher
from itertools import groupby
from django.core.mail import send_mail

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render

from core.models import Biography
from core.search import normalize_arabic

logger = logging.getLogger(__name__)

from .models import (
    Post,
    HeroSlide,
    Service,
    SiteSettings,
)


def landing(request):
    """Landing page view: pass all editable content from models."""
    # Singleton / optional: use first() and allow None
    site_settings = SiteSettings.objects.first()

    # Sections headings (by slug); default None for missing so template can use {% if sections.welcome %}
    section_slugs = ["services", "blog", "clients", "team"]
    sections = {slug: None for slug in section_slugs}
    
    # Singleton hero section
    hero = HeroSlide.objects.first()
    # Ordered lists
    services = list(Service.objects.all())
    featured_posts = list(Post.objects.filter(show_as_featured=True))

    context = {
        "site_settings": site_settings,
        "sections": sections,
        "hero": hero,
        "services": services,
        "featured_posts": featured_posts,
    }
    return render(request, "home.html", context)


def post_detail(request, pk):
    """Single post page (Post by pk)."""
    post = get_object_or_404(Post, pk=pk)
    site_settings = SiteSettings.objects.first()
    context = {
        "post": post,
        "site_settings": site_settings,
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
    if approximate:
        ar = ar + " تقريباً"
        en = "c. " + en
    return {"ar": ar, "en": en, "approximate": bool(approximate)}


def _bio_dates(bio):
    return {
        "birth_hijri": _format_date(
            bio.birth_hijri_year, bio.birth_hijri_month, bio.birth_hijri_day,
            HIJRI_MONTHS_AR, HIJRI_MONTHS_EN, "هـ", "AH", bio.birth_hijri_approximate,
        ),
        "birth_greg": _format_date(
            bio.birth_greg_year, bio.birth_greg_month, bio.birth_greg_day,
            GREG_MONTHS_AR, GREG_MONTHS_EN, "م", "CE", bio.birth_greg_approximate,
        ),
        "death_hijri": _format_date(
            bio.death_hijri_year, bio.death_hijri_month, bio.death_hijri_day,
            HIJRI_MONTHS_AR, HIJRI_MONTHS_EN, "هـ", "AH", bio.death_hijri_approximate,
        ),
        "death_greg": _format_date(
            bio.death_greg_year, bio.death_greg_month, bio.death_greg_day,
            GREG_MONTHS_AR, GREG_MONTHS_EN, "م", "CE", bio.death_greg_approximate,
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
        "teacher_relationships__notes",
        "student_relationships__student",
        "student_relationships__notes",
    )
    biography = get_object_or_404(qs, pk=pk)
    if not biography.published and not request.user.is_staff:
        raise Http404()

    teachers = list(biography.teacher_relationships.all())
    students = list(biography.student_relationships.all())
    sources = list(biography.sources.all())
    esnads = list(biography.esnads.all())

    site_settings = SiteSettings.objects.first()

    context = {
        "biography": biography,
        "dates": _bio_dates(biography),
        "attributes": list(biography.attributes.all()),
        "teachers": teachers,
        "students": students,
        "sources": sources,
        "esnads": esnads,
        "site_settings": site_settings,
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
    context = {
        "biographies": biographies,
        "site_settings": site_settings,
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
    context = {
        "groups": groups,
        "site_settings": site_settings,
        "user": request.user,
    }
    return render(request, "biographies-by-city.html", context)


# Minimum token-similarity (0-1) for a biography to surface as a "similar"
# (fuzzy) match when it isn't an exact substring hit. Tuned to catch typos
# and spelling variants without flooding the page with unrelated names.
SIMILARITY_THRESHOLD = 0.8
# Cap on how many similar matches we show, best-scoring first.
SIMILARITY_MAX_RESULTS = 12


def _token_similarity(query_words, target_text):
    """Best average per-token similarity between the query and a target.

    For each query word we find the closest word in ``target_text`` (using
    :class:`difflib.SequenceMatcher`) and average those best scores. Returns a
    float in ``0..1``; higher means a closer fuzzy match.
    """
    target_words = target_text.split()
    if not query_words or not target_words:
        return 0.0
    total = 0.0
    for qw in query_words:
        total += max(
            SequenceMatcher(None, qw, tw).ratio() for tw in target_words
        )
    return total / len(query_words)


def search_results(request):
    """Search published biographies by Arabic/English name and alias.

    Matching is tashkeel-insensitive and treats multi-word queries as AND:
    every word in the (normalized) query must appear somewhere in the
    biography's normalized name/alias text. Biographies that don't match
    exactly are scored for fuzzy similarity and, when close enough, surfaced
    separately as "similar" results with a match percentage.
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

            # Fold in fuzzy "similar" matches: biographies that aren't exact
            # substring hits but are close enough in spelling. They're appended
            # after the exact matches, best similarity first.
            exact_ids = {bio.pk for bio in results}
            candidates = (
                Biography.objects.filter(published=True)
                .exclude(pk__in=exact_ids)
                .select_related("hometown")
            )
            scored = []
            for bio in candidates:
                score = _token_similarity(words, bio.name_search)
                if score >= SIMILARITY_THRESHOLD:
                    scored.append((score, bio))
            scored.sort(key=lambda item: item[0], reverse=True)
            results.extend(bio for _, bio in scored[:SIMILARITY_MAX_RESULTS])

    logger.info("search_results query=%r matched %d biographies", query, len(results))
    site_settings = SiteSettings.objects.first()
    context = {
        "query": query,
        "results": results,
        "site_settings": site_settings,
        "user": request.user,
    }
    return render(request, "search-results.html", context)

def contact_form(request):
    if request.method == 'POST':
        # Extract form data from request
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        comments = request.POST.get('comments')

        # Check if any field is empty
        if not all([name, email, subject, comments]):
            return JsonResponse({'error': 'Please fill out all fields.'}, status=400)

        # Send email
        send_mail(
            subject,
            comments,
            email,
            ['kalghanimdev@gmail.com'], #change email id 
            fail_silently=False,
        )

        return JsonResponse({'message': 'Success! Your message has been sent.'})

    # GET request or invalid form submission
    return JsonResponse({'error': 'Invalid request.'}, status=400)