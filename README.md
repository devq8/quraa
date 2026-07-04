# Quraa

**المركز العالمي لتاريخ ووثائق القراء**  
**The International Center for the History and Documentation of Quran Reciters**

---

## Our Motto

**نعتني بتاريخ أهل القرآن**  
*We care about the history of Quran reciters.*

---

## About

Islamic history is the soul of the nation, the vessel of its civilization, and its living memory that preserves its identity. At the heart of this great history is a distinguished group whom Allah Almighty chose to preserve His book: **the reciters of the Quran and its teachers**.

The renowned reciters of the Noble Quran are the blessed hands that conveyed the Book of our Lord to us in the most complete way. The Quranic revival we witness today is the fruit of their noble efforts and sacrifices. Therefore, the highest degrees of appreciation and honor for these illuminated stars are embodied in nothing greater than **collecting their history, documenting their biographies, and acquainting the nation with their virtues**.

This work is not merely a civilizational project, but a debt owed by the nation that must be fulfilled, and an obligatory advice for the Book of Allah Almighty and for Muslims. *Quraa* is a digital platform that serves as a pioneering beacon in collecting, studying, and documenting the history of the noble Quran reciters—from the documents of famous men of the Quranic chains of transmission (أسانيد).

---

## Vision

**التميز عالميا في جمع وتوثيق تاريخ القراء**  
*Global excellence in collecting and documenting the history of Quran reciters.*

---

## General Objectives

- **جمع (Collection)** — Collecting biographies of ancient and contemporary Quran reciters from various countries and in different languages.
- **تنقية (Purification)** — Purifying published biographies of reciters from misconceptions and errors.
- **مساعدة (Assistance)** — Assisting researchers in excavating rare and scarce biographies of reciters.
- **توثيق (Documentation)** — Documenting reciters’ biographies using all possible means of documentation.
- **جمع وحفظ (Collection & Preservation)** — Collecting and preserving documents of reciters and teachers of the Quran.
- **رعاية (Sponsorship)** — Sponsoring and supporting distinguished senior reciters.

---

## Key Initiatives

| Initiative | Description |
|------------|-------------|
| **تقديم (Offering)** | Scientific courses in the art of biographies of Quranic reciters (collection, study, and formulation). |
| **رعاية (Sponsorship)** | Support for distinguished researchers in the biographies of reciters. |
| **جمع (Collection)** | Collection of rare oral history of the reciters of the Holy Quran. |
| **فهرسة (Indexing)** | Comprehensive indexing of the names of the narrators in Quranic chains of transmission (Isnad). |
| **تأسيس (Establishment)** | A distinctive database on the history of Quranic reciters. |
| **إتاحة (Availability)** | Making this historical content available to researchers and people of the Quran. |

---

## Current Services

1. **جمع ترجمة لمقرئ** — Collection and compilation of a biography for a reciter.
2. **مراجعة تراجم قراء** — Review of biographies of reciters prepared by others.
3. **توثيق ترجمة مقرئ** — Documentation and authentication of a reciter’s biography.
4. **توفير مصادر ووثائق** — Providing sources and documents for creating a biography for a reciter.
5. **تصوير وثائق القراء** — Photography and digitization of reciters’ documents with the latest means and highest accuracy.
6. **التحكيم العلمي** — Scientific arbitration for academic research in the history, biographies, and chains of transmission (Isnad) of reciters.

---

## This Project

*Quraa* is the web application and database platform for the Center. It is built with **Django** and is intended to support:

- Managing and publishing biographies of Quran reciters.
- Cataloging and preserving documents and chains of transmission.
- Making historical content available to researchers and people of the Quran.

### Requirements

- Python 3.x  
- Django 6.x (see `requirements.txt`)

### Setup

```bash
# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create a superuser (optional)
python manage.py createsuperuser

# Run the development server
python manage.py runserver
```

Then open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your browser.

### Biography Import and Export

Administrators can manage bulk Biography data from the Django admin changelist:

- **Import CSV** accepts UTF-8 CSV files and `.xlsx` workbooks that match the downloadable template.
- **Export CSV** and **Export XLSX** download the current admin changelist queryset, including active search, filters, and ordering.
- Exported files use the same import-compatible columns as the import template, so they can be edited and uploaded again.
- The import-compatible format includes one hometown location and up to six attributes per Biography. Teachers, students, sources, and esnad chains are not included in this export.
- CSV exports include a UTF-8 byte-order mark so Arabic text opens correctly in spreadsheet tools.

### Biography Duplicate Review

When administrators add or edit a Biography, the admin form checks for possible duplicate biographies while typing in the Arabic name, English name, Arabic alias, or English alias fields.

- Matches use the same Arabic normalization and similarity logic as the duplicate/import tooling.
- Possible duplicates appear as links to the existing Biography admin change pages.
- Duplicate links open in a new browser tab so the current add/edit form remains open.
- The warning is advisory only and does not block saving.

### Translation Maintenance

The Arabic locale catalog lives in `locale/ar/LC_MESSAGES/django.po` and is compiled to `django.mo`. When adding public-site or admin labels, wrap static text with Django translation tags/functions, refresh messages with `python manage.py makemessages -l ar`, fill any missing Arabic translations, then run `python manage.py compilemessages`.

Admin pages that store internal option keys, such as Biography import modes, should render translated display labels instead of the stored key values.

### Project Structure

- **quraa/** — Django project settings and root URL configuration.
- **core/** — Core application (main models and logic).
- **users/** — User management and authentication.

---

## Contact

**اتصل بنا | Contact us**

- **Telegram:** [@trajemqurraa](https://t.me/trajemqurraa) · [@trajemqurraa1](https://t.me/trajemqurraa1)
- **Email:** [trajemqurraa@gmail.com](mailto:trajemqurraa@gmail.com)
- **Facebook:** المركز العالمي لتاريخ ووثائق القراء

---

## Founder

**د. مصطفى بن شعبان الوراقي**  
*Dr. Mustafa bin Sha'ban Al-Waraqi*  
مؤسس المركز — Founder of the Center

---

*May Allah bless this unique scientific edifice, and may it remain a lighthouse illuminating the paths of researchers and elevate the status of the guardians of the Wise Remembrance. اللهم آمين.*
