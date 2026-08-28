import logging
from difflib import SequenceMatcher
from django.core.mail import send_mail

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import get_language

from core.models import Attribute, Biography, Location
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
    featured_biographies = list(
        Biography.objects.filter(published=True, is_featured=True)
        .select_related("death_location")
        .prefetch_related("hometown", "attributes")[:6]
    )

    context = {
        "site_settings": site_settings,
        "sections": sections,
        "hero": hero,
        "services": services,
        "featured_posts": featured_posts,
        "featured_biographies": featured_biographies,
    }
    return render(request, "home.html", context)


def blog(request):
    """List every blog post, with a category sidebar to filter the list."""
    active_category = (request.GET.get("category") or "").strip()
    lang = get_language() or ""
    is_ar = lang.startswith("ar")

    posts = Post.objects.all()
    if active_category:
        posts = posts.filter(
            Q(category_ar=active_category) | Q(category_en=active_category)
        )
    posts = list(posts)

    # Build the category list (display value in the active language) with counts,
    # keyed off every post so the sidebar is independent of the active filter.
    counts = {}
    total_posts_all = 0
    for post in Post.objects.all():
        total_posts_all += 1
        label = (post.category_ar if is_ar else post.category_en) or post.category_en or post.category_ar
        if not label:
            continue
        counts[label] = counts.get(label, 0) + 1
    categories = [
        {"label": label, "count": count}
        for label, count in sorted(counts.items(), key=lambda item: item[0])
    ]

    site_settings = SiteSettings.objects.first()
    context = {
        "posts": posts,
        "categories": categories,
        "active_category": active_category,
        "total_posts": len(posts),
        "total_posts_all": total_posts_all,
        "site_settings": site_settings,
        "user": request.user,
    }
    return render(request, "blog.html", context)


def post_detail(request, pk):
    """Single post page (Post by pk)."""
    post = get_object_or_404(Post, pk=pk)
    site_settings = SiteSettings.objects.first()
    related_posts = list(Post.objects.exclude(pk=post.pk)[:3])
    context = {
        "post": post,
        "related_posts": related_posts,
        "site_settings": site_settings,
        "user": request.user,
    }
    return render(request, "blog-detail.html", context)


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
        "birthplace", "death_location",
    ).prefetch_related(
        "hometown",
        "attributes",
        "sources",
        "esnads__links__narrator",
        "esnads__links__narrator__esnads__links__narrator",
        "teacher_relationships__teacher",
        "teacher_relationships__notes",
        "student_relationships__student",
        "student_relationships__notes",
    )
    biography = get_object_or_404(qs, pk=pk)

    teachers = list(biography.teacher_relationships.all())
    students = list(biography.student_relationships.all())
    sources = list(biography.sources.all())
    esnads = list(biography.esnads.all())

    for esnad in esnads:
        expanded = esnad.get_expanded_links()
        esnad.full_links = expanded
        esnad.reversed_links = list(reversed(expanded))
        esnad._isnad_rank_cache = len(expanded) - 1 if expanded else None
        esnad.expanded_terminal = expanded[-1] if expanded else None

    site_settings = SiteSettings.objects.first()

    lang = get_language() or "ar"
    if lang == "ar":
        share_title = (
            biography.alias_ar or biography.alias_en
            or biography.full_name_ar or biography.full_name_en or ""
        )
    else:
        share_title = (
            biography.alias_en or biography.alias_ar
            or biography.full_name_en or biography.full_name_ar or ""
        )

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
        "share_url": request.build_absolute_uri(request.path),
        "share_title": share_title,
    }
    return render(request, "biography.html", context)


def biographies(request):
    """Browse every published biography with the same faceted filters,
    sorting and pagination as the search page (but no text query)."""
    hometown_id = (request.GET.get("hometown") or "").strip()
    birthplace_id = (request.GET.get("birthplace") or "").strip()
    death_location_id = (request.GET.get("death_location") or "").strip()
    attribute_id = (request.GET.get("attribute") or "").strip()
    sort = request.GET.get("sort") or "name_asc"
    if sort not in SORT_OPTIONS or sort == "relevance":
        sort = "name_asc"
    has_filters = any([hometown_id, birthplace_id, death_location_id, attribute_id])

    qs = Biography.objects.filter(published=True)
    if hometown_id:
        qs = qs.filter(hometown__id=hometown_id)
    if birthplace_id:
        qs = qs.filter(birthplace_id=birthplace_id)
    if death_location_id:
        qs = qs.filter(death_location_id=death_location_id)
    if attribute_id:
        qs = qs.filter(attributes__id=attribute_id)

    results = list(
        qs.prefetch_related("hometown", "esnads__links__narrator", "esnads__links__narrator__esnads__links__narrator")
        .distinct()
        .order_by("full_name_ar")
    )

    # Strongest (shortest) chain per biography, using expanded links.
    for bio in results:
        ranks = []
        for esnad in bio.esnads.all():
            expanded = esnad.get_expanded_links()
            if expanded:
                ranks.append(len(expanded) - 1)
        bio.best_isnad_rank = min(ranks) if ranks else None

    _sort_results(results, sort)

    site_settings = SiteSettings.objects.first()
    per_page = getattr(site_settings, "search_results_per_page", 5) or 5
    paginator = Paginator(results, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Filter dropdown options, limited to values referenced by published bios.
    published = Biography.objects.filter(published=True)
    hometown_options = Location.objects.filter(hometown__in=published).distinct()
    birthplace_options = Location.objects.filter(birthplace__in=published).distinct()
    death_location_options = Location.objects.filter(death_location__in=published).distinct()
    attribute_options = Attribute.objects.filter(biographies__in=published).distinct()

    params = request.GET.copy()
    params.pop("page", None)
    querystring = params.urlencode()

    context = {
        "results": page_obj,
        "page_obj": page_obj,
        "total_results": paginator.count,
        "site_settings": site_settings,
        "user": request.user,
        "has_filters": has_filters,
        "sort": sort,
        "querystring": querystring,
        "hometown_options": hometown_options,
        "birthplace_options": birthplace_options,
        "death_location_options": death_location_options,
        "attribute_options": attribute_options,
        "active_hometown": hometown_id,
        "active_birthplace": birthplace_id,
        "active_death_location": death_location_id,
        "active_attribute": attribute_id,
    }
    return render(request, "biographies.html", context)


# Minimum token-similarity (0-1) for a biography to surface as a "similar"
# (fuzzy) match when it isn't an exact substring hit. Tuned to catch typos
# and spelling variants without flooding the page with unrelated names.
SIMILARITY_THRESHOLD = 0.8
# Cap on how many similar matches we show, best-scoring first.
SIMILARITY_MAX_RESULTS = 12

# Allowed values for the ?sort= query param on the search page.
SORT_OPTIONS = {"relevance", "name_asc", "name_desc", "death_asc", "death_desc", "rank"}


def _name_sort_key(bio):
    """Display-name sort key, picking the active language's name first."""
    lang = get_language() or ""
    if lang.startswith("ar"):
        name = bio.full_name_ar or bio.full_name_en
    else:
        name = bio.full_name_en or bio.full_name_ar
    return (name or "").strip()


def _sort_results(results, sort):
    """Re-order the in-memory results list per the chosen ``sort`` mode.

    ``relevance`` (the default) leaves the existing order untouched: exact
    matches first (alphabetical), then fuzzy matches by descending similarity.
    Entries missing the sort key (no death year / no isnad rank) sort last.
    """
    if sort == "name_asc":
        results.sort(key=_name_sort_key)
    elif sort == "name_desc":
        results.sort(key=_name_sort_key, reverse=True)
    elif sort == "death_asc":
        results.sort(key=lambda b: (b.death_hijri_year is None, b.death_hijri_year or 0))
    elif sort == "death_desc":
        results.sort(key=lambda b: (b.death_hijri_year is None, -(b.death_hijri_year or 0)))
    elif sort == "rank":
        results.sort(key=lambda b: (b.best_isnad_rank is None, b.best_isnad_rank or 0))
    return results


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

    # Faceted filters (Location / Attribute primary keys, as raw strings) and
    # the chosen ordering. Filters may drive the results on their own, even
    # without a text query.
    hometown_id = (request.GET.get("hometown") or "").strip()
    birthplace_id = (request.GET.get("birthplace") or "").strip()
    death_location_id = (request.GET.get("death_location") or "").strip()
    attribute_id = (request.GET.get("attribute") or "").strip()
    sort = request.GET.get("sort") or "relevance"
    if sort not in SORT_OPTIONS:
        sort = "relevance"
    has_filters = any([hometown_id, birthplace_id, death_location_id, attribute_id])

    def apply_filters(qs):
        if hometown_id:
            qs = qs.filter(hometown__id=hometown_id)
        if birthplace_id:
            qs = qs.filter(birthplace_id=birthplace_id)
        if death_location_id:
            qs = qs.filter(death_location_id=death_location_id)
        if attribute_id:
            qs = qs.filter(attributes__id=attribute_id)
        return qs

    logger.debug("search_results raw query=%r", query)
    results = []
    if query or has_filters:
        words = normalize_arabic(query).split() if query else []

        logger.debug("search_results normalized words=%r", words)
        qs = Biography.objects.filter(published=True)
        for word in words:
            qs = qs.filter(name_search__icontains=word)
        qs = apply_filters(qs).distinct()

        logger.debug("search_results SQL=%s", qs.query)
        results = list(
            qs.prefetch_related("hometown", "esnads__links__narrator", "esnads__links__narrator__esnads__links__narrator")
            .order_by("full_name_ar")
        )

        # Fold in fuzzy "similar" matches: biographies that aren't exact
        # substring hits but are close enough in spelling. Only meaningful when
        # there's a text query; the active filters apply to candidates too.
        if words:
            exact_ids = {bio.pk for bio in results}
            candidates = (
                apply_filters(
                    Biography.objects.filter(published=True).exclude(pk__in=exact_ids)
                )
                .prefetch_related("hometown", "esnads__links__narrator", "esnads__links__narrator__esnads__links__narrator")
                .distinct()
            )
            scored = []
            for bio in candidates:
                score = _token_similarity(words, bio.name_search)
                if score >= SIMILARITY_THRESHOLD:
                    scored.append((score, bio))
            scored.sort(key=lambda item: item[0], reverse=True)
            results.extend(bio for _, bio in scored[:SIMILARITY_MAX_RESULTS])

    # Surface the strongest (shortest) chain each biography holds: the lowest
    # isnad_rank across its esnads. Uses expanded links (recursive) to count
    # all intermediaries through the terminal narrator's chains.
    for bio in results:
        ranks = []
        for esnad in bio.esnads.all():
            expanded = esnad.get_expanded_links()
            if expanded:
                ranks.append(len(expanded) - 1)
        bio.best_isnad_rank = min(ranks) if ranks else None

    _sort_results(results, sort)

    logger.info("search_results query=%r matched %d biographies", query, len(results))

    site_settings = SiteSettings.objects.first()
    per_page = getattr(site_settings, "search_results_per_page", 5) or 5

    paginator = Paginator(results, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Filter dropdown options, limited to locations/attributes that are actually
    # referenced by published biographies so the menus stay useful.
    published = Biography.objects.filter(published=True)
    hometown_options = Location.objects.filter(hometown__in=published).distinct()
    birthplace_options = Location.objects.filter(birthplace__in=published).distinct()
    death_location_options = Location.objects.filter(death_location__in=published).distinct()
    attribute_options = Attribute.objects.filter(biographies__in=published).distinct()

    # Querystring for pagination links: everything except the page number, so
    # the active query/filters/sort survive page changes.
    params = request.GET.copy()
    params.pop("page", None)
    querystring = params.urlencode()

    context = {
        "query": query,
        "results": page_obj,
        "page_obj": page_obj,
        "total_results": paginator.count,
        "site_settings": site_settings,
        "user": request.user,
        "has_filters": has_filters,
        "sort": sort,
        "querystring": querystring,
        "hometown_options": hometown_options,
        "birthplace_options": birthplace_options,
        "death_location_options": death_location_options,
        "attribute_options": attribute_options,
        "active_hometown": hometown_id,
        "active_birthplace": birthplace_id,
        "active_death_location": death_location_id,
        "active_attribute": attribute_id,
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