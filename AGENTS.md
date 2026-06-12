# AGENTS.md — Quraa

> This file is written for AI coding agents that need to understand the project quickly. It describes the actual project structure, technology choices, build/test workflow, coding conventions, and security/deployment notes. It replaces any previous (empty) content in this file.

---

## Project overview

**Quraa** is the web platform for *The International Center for the History and Documentation of Quran Reciters* (المركز العالمي لتاريخ ووثائق القراء). It is a bilingual (Arabic/English) Django application whose main purpose is to collect, document, and publish biographies of Quran reciters, their teacher/student relationships, and their chains of Quranic transmission (*asanid* / إسناد).

Public functionality includes:

* A landing/home page with editable hero, services, and featured blog posts.
* Public biography detail pages (`/biography/<pk>/`).
* Alphabetical listing of published biographies (`/biographies/`).
* Biographies grouped by hometown city (`/biographies/by-city/`).
* Arabic/English name search with tashkeel-insensitive substring matching and fuzzy similarity fallback (`/search/`).
* Blog post detail pages (`/post/<pk>/`).
* A contact form endpoint (`/contact/`) that sends email via Django’s `send_mail`.

Administrators use Django admin (at `/admin/`) to manage:

* Biographies, locations, attributes, notes, sources.
* Teacher/student relationships.
* Esnads (chains of narrators) and Esnad templates.
* Site settings, hero section, services, and blog posts.

---

## Technology stack

* **Runtime:** Python 3.13+ (the checked-in `.venv` was created with Python 3.13.7).
* **Web framework:** Django 6.0.2.
* **Database:** SQLite when `DEBUG=True`; MySQL when `DEBUG=False`.
* **User uploads / media:** local filesystem in development; AWS S3 (`boto3` / `django-storages`) in production.
* **Frontend:** Tailwind CSS v3.4.1, FontAwesome, Material Design Icons, Tiny Slider, Tobii lightbox, Google Fonts (Noto Naskh Arabic, Rubik).
* **Rich text:** django-tinymce for translatable description/body fields.
* **Admin extensions:** `django-nested-admin`, `django-admin-sortable2`.
* **Date conversion:** `hijridate` with a fallback approximate converter in `core/hijri_utils.py`.
* **Environment loading:** `python-dotenv` reads a `.env` file at project root.

Key configuration files:

* `quraa/settings.py` — all Django settings, environment-driven.
* `quraa/urls.py` — root URL routing.
* `requirements.txt` — Python dependencies.
* `package.json` / `tailwind.config.js` — Tailwind build scripts and configuration.
* `.env` — environment variables (not committed; listed in `.gitignore`).

No `pyproject.toml`, `setup.py`, `pytest.ini`, `Dockerfile`, `Makefile`, or CI configuration files exist in the repository.

---

## Build and run commands

All commands assume you are in the project root and, ideally, inside the virtual environment.

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node dependencies (required for Tailwind builds)
npm install

# Apply database migrations
python manage.py migrate

# Create an admin user
python manage.py createsuperuser

# Run the development server
python manage.py runserver
```

The development server is available at `http://127.0.0.1:8000/`.

### Tailwind CSS build

The project ships a hand-tuned theme CSS file at `core/static/assets/css/tailwind.css` (base + components). Only the utility layer is regenerated from templates.

```bash
# One-off production build (minified)
npm run tw:build

# Watch mode for development
npm run tw:watch
```

Output file: `core/static/assets/css/tailwind-utilities.css`.

### Production/static assets

```bash
# Collect static files into STATIC_ROOT
python manage.py collectstatic --noinput
```

`STATIC_ROOT` is `staticfiles/`; `MEDIA_ROOT` is `media/`. Both are git-ignored.

---

## Code organization

```
quraa/                  # Django project package
  settings.py           # Environment-driven settings
  urls.py               # Root URLconf; overrides admin logout
  wsgi.py / asgi.py     # Standard WSGI/ASGI entrypoints

core/                   # Core domain app
  models.py             # Biography, Location, Attribute, Note, Source,
                        # Esnad, EsnadLink, EsnadTemplate, TeacherStudentRelationship
  admin.py              # Admin configuration, nested/sortable inlines,
                        # Esnad template application
  views.py              # Email-based login view
  backends.py           # EmailAuthenticationBackend
  search.py             # Arabic normalization and biography search text helper
  hijri_utils.py        # Approximate Hijri/Gregorian conversion utilities
  static/               # Theme assets (CSS, JS, images, fonts, libs)
  templates/registration/login.html   # Standalone login template

landing/                # Public site app
  models.py             # SiteSettings, HeroSlide, Service, Post
  views.py              # All public page views + search + contact form
  urls.py               # Public URL routes
  admin.py              # Admin for landing models
  templates/            # Public templates (base.html, home.html, biography.html, ...)

users/                  # Authentication app
  models.py             # Custom User model (email login, user_type)
  admin.py              # UserAdmin
  management/commands/  # Custom management commands

templates/              # Global templates
  admin/base_site.html              # Admin language switcher
  admin/core/biography/change_form.html   # Audit + template loader
  admin/core/esnad/change_form.html       # Template loader

locale/ar/LC_MESSAGES/django.po   # Arabic translations
media/                  # User uploads in development
tailwind/               # Tailwind input CSS
```

### Module responsibilities

* **`core`** — domain data and business rules for reciter biographies, locations, attributes, sources, and transmission chains.
* **`landing`** — CMS-style public pages (home, about, services, blog) and public biography browsing/search.
* **`users`** — custom user accounts, email authentication, and role types (`admin`, `staff`, `biography`).

---

## Settings and environment variables

`quraa/settings.py` loads a `.env` file and branches on `DEBUG`.

Required / used environment variables:

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Django secret key. |
| `DEBUG` | Set to `True` for development. |
| `ALLOWED_HOSTS` | Comma-separated list of production hosts. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | MySQL connection in production (`DEBUG=False`). |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | S3 credentials in production. |
| `AWS_STORAGE_BUCKET_NAME` | S3 bucket name (default: `quraa-bucket`). |
| `AWS_S3_REGION_NAME` | S3 region (default: `eu-north-1`). |

In development (`DEBUG=True`):

* Database: SQLite (`db.sqlite3`).
* Static/media: local filesystem.
* `STATIC_ROOT = BASE_DIR / 'staticfiles'`.
* `MEDIA_ROOT = BASE_DIR / 'media'`.

In production (`DEBUG=False`):

* Database: MySQL.
* User uploads: S3 via `S3Boto3Storage`.
* Static files: still local `StaticFilesStorage` (run `collectstatic`).

Current hardcoded items to be aware of:

* `CSRF_TRUSTED_ORIGINS = ['http://13.62.62.34']` — must be updated for the real production domain.
* `TIME_ZONE = 'Asia/Kuwait'`.
* `LANGUAGE_CODE = 'en-us'` with `LANGUAGES = [('en', 'English'), ('ar', 'العربية')]`.
* `LANGUAGE_BIDI = True` enables RTL support.

---

## Authentication and users

* Custom user model: `users.User` (`AUTH_USER_MODEL = "users.User"`).
* Login identifier is email (`USERNAME_FIELD = "email"`).
* A custom backend `core.backends.EmailAuthenticationBackend` authenticates by email/password.
* User types:
  * `admin` → `is_staff=True`, `is_superuser=True`.
  * `staff` → `is_staff=True`, `is_superuser=False`.
  * `biography` → regular user with limited access.
* `users/admin.py` restricts `user_type`, groups, and permissions editing to superusers.
* The root URLconf overrides `admin.site.logout` and the `/accounts/logout/` path so logout always redirects to the landing page.
* Login view is `core.views.login_view`, template `registration/login.html`.

---

## Data model highlights

### `core.Biography`

* Bilingual identity fields: `full_name_ar`, `full_name_en`, `alias_ar`, `alias_en`.
* Birth and death dates stored in both Hijri and Gregorian calendars with independent `*_approximate` flags.
* On `save()`, the model derives the partner calendar from whichever side was edited and refreshes `name_search`.
* Related to `Location` for birthplace, hometown, and death location.
* Related to `Attribute` (e.g., Quranic readings).
* Teacher/student relationships are stored through `TeacherStudentRelationship` (a self-referential M2M through model on `Biography`).
* `submitted_by` and `last_modified_by` track authorship; `user` can link a biography to a user account.
* `published` controls public visibility.

### `core.Esnad` and `core.EsnadLink`

* `Esnad` belongs to a biography (the chain holder).
* `EsnadLink` defines ordered narrators in the chain.
* `Esnad.isnad_rank` returns the number of intermediary narrators.
* `Esnad.chain_display()` renders the chain from holder to terminal narrator.
* Admin uses sortable nested inlines and a custom "Load from Template" action.

### `core.EsnadTemplate` / `EsnadTemplateLink`

* Reusable chain templates that can be applied to an existing `Esnad`, replacing its current links.

### `landing` models

* `SiteSettings` — singleton for site name, logo, favicon, about/services/donate/blog/contact sections, social links, and copyright.
* `HeroSlide` — singleton hero section (title, subtitle, optional video/image, search bar toggle).
* `Service` — ordered service cards on the home page.
* `Post` — blog posts, optionally featured on the home page.

---

## Frontend and templates

* Base template: `landing/templates/base.html`.
* Loads `core/static/assets/css/tailwind.css` (theme) then `tailwind-utilities.css` (generated utilities).
* Supports RTL/LTR via `dir="{% if LANGUAGE_BIDI %}rtl{% else %}ltr{% endif %}"`.
* Supports dark mode via `class="light/dark"` and a small script that reads the system preference before first paint.
* Uses Google Fonts: Noto Naskh Arabic for headings/paragraphs, Rubik for the navbar.
* Static assets live primarily under `core/static/`.

Admin templates (`templates/admin/`) add a language switcher and custom form blocks for biography/esnad template loading.

---

## Search implementation

Public biography search (`landing.views.search_results`) works as follows:

1. User query is normalized via `core.search.normalize_arabic`, which removes tashkeel, normalizes alef variants and hamza forms, lowercases, and collapses whitespace.
2. Each query word must appear as a substring of `Biography.name_search` (AND logic).
3. Exact substring hits are returned first.
4. Fuzzy matches are appended using `difflib.SequenceMatcher` per token; only scores ≥ `SIMILARITY_THRESHOLD` (0.8) are kept, capped at `SIMILARITY_MAX_RESULTS` (12).

`name_search` is recomputed on every `Biography.save()`.

---

## Hijri/Gregorian date handling

* `Biography.save()` calls `_fill_date("birth")` and `_fill_date("death")`.
* The primary converter is the `hijridate` package.
* If `hijridate` raises `OverflowError` or `ValueError`, the code falls back to the approximate arithmetic converters in `core.hijri_utils`.
* Approximate flags are per calendar side and are only updated when the user actually edits that side, preventing stale derived values from being marked exact.

---

## Testing instructions

The project currently has **no implemented tests**. Each app contains a `tests.py` file with only the placeholder:

```python
from django.test import TestCase

# Create your tests here.
```

Run the test suite with:

```bash
python manage.py test
```

This will succeed with zero tests. When adding tests, prefer Django’s `TestCase` and place them in each app’s `tests.py` (or split into `tests/` packages if the app grows).

---

## Code style guidelines

Observed conventions in the codebase:

* **Language:** code, docstrings, and comments are written in English. UI labels are wrapped with `gettext_lazy` (`_()`) for translation.
* **Imports:** standard library, then third-party, then Django, then local modules.
* **Model fields:** bilingual fields use `_ar` and `_en` suffixes. Translation strings are used for `verbose_name` values.
* **String representation:** models check `get_language()` and prefer the active language when available.
* **Admin ordering:** helper `_lang_ordering(ar_fields, en_fields)` returns Arabic or English ordering based on the active admin language.
* **Docstrings:** public classes and non-trivial methods include docstrings explaining behavior and edge cases.
* **Line length:** the codebase does not strictly enforce a limit; keep reasonably readable.

When adding features:

* Add new models to the appropriate app (`core` for domain data, `landing` for public-site CMS data, `users` for auth).
* Register new models in the corresponding `admin.py`.
* Add URL routes in the app’s `urls.py` and include them in `quraa/urls.py` if they are public/admin-facing.
* Keep bilingual fields paired (`_ar` / `_en`) and translatable labels.
* Update `locale/ar/LC_MESSAGES/django.po` via `python manage.py makemessages -l ar` and `python manage.py compilemessages` when adding user-facing strings.

---

## Security considerations

* **Secret key:** `SECRET_KEY` is read from the environment; never commit it.
* **Debug mode:** `DEBUG` is driven by the environment and must be `False` in production.
* **Allowed hosts:** `ALLOWED_HOSTS` is comma-separated from the environment; do not rely on defaults in production.
* **CSRF:** `CSRF_TRUSTED_ORIGINS` is currently hardcoded to `http://13.62.62.34`. Update it for the production domain and prefer loading it from the environment.
* **File uploads:** `DATA_UPLOAD_MAX_MEMORY_SIZE = 100 MB`, `FILE_UPLOAD_MAX_MEMORY_SIZE = 5 MB`. Ensure the reverse proxy (`nginx`, etc.) matches these limits.
* **AWS credentials:** stored in environment variables; the bucket ACL is disabled (`AWS_DEFAULT_ACL = None`) and file overwrite is disabled.
* **Email:** the contact form uses Django’s `send_mail` with a hardcoded recipient address. In production, configure `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and related settings via the environment or a local settings file.
* **Admin access:** the admin language switcher uses Django’s built-in `set_language` view. Keep CSRF protection enabled.
* **User permissions:** only superusers can change `user_type`, groups, and permissions. Non-superusers see those fields as read-only.
* **Environment file:** `.env` is git-ignored. Do not commit it or any other file containing credentials.

---

## Deployment notes

No container or platform-specific deployment files are present. A typical deployment looks like:

1. Provision a server with the environment variables listed above.
2. Install Python dependencies: `pip install -r requirements.txt`.
3. Run migrations: `python manage.py migrate`.
4. Collect static files: `python manage.py collectstatic --noinput`.
5. Serve with a WSGI server (e.g., Gunicorn) behind `nginx`.
6. Ensure the reverse proxy forwards the correct `Host` header and matches upload size limits.

`settings.py` configures console logging so Django request errors are visible even when `DEBUG=False`.

---

## Special management command

`users/management/commands/fix_inconsistent_migration_history.py` exists as a one-time repair command. It drops `django_admin_log` and removes `admin` rows from `django_migrations` so migrations can be re-applied in the correct order when `InconsistentMigrationHistory` occurs. Use it only when the standard migration path fails.

---

## Useful references

* `README.md` — project background, setup, and contact information.
* `quraa/settings.py` — authoritative source for settings and environment variables.
* `requirements.txt` — Python dependency versions.
* `package.json` / `tailwind.config.js` — frontend build configuration.
* `locale/ar/LC_MESSAGES/django.po` — Arabic translations.
