import csv
import io

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from . import csv_import
from .models import Attribute, Biography, Location


class BiographyLiveDuplicateAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            email="admin-live@example.com",
            password="password",
            username="admin-live@example.com",
        )
        self.url = reverse("admin:core_biography_live_duplicates")
        self.biography = Biography.objects.create(
            full_name_ar="أحمد بن علي الشاطبي",
            full_name_en="Ahmad ibn Ali al-Shatibi",
            alias_ar="الشاطبي",
            alias_en="Al-Shatibi",
        )

    def test_duplicate_results_include_admin_change_url(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(self.url, {"q": "احمد بن علي الشاطبي"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["id"], self.biography.pk)
        self.assertEqual(
            data["results"][0]["url"],
            reverse("admin:core_biography_change", args=[self.biography.pk]),
        )

    def test_edit_mode_excludes_current_biography(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            self.url,
            {"q": "احمد بن علي الشاطبي", "exclude_id": self.biography.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_alias_input_returns_matches(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(self.url, {"q": "Al-Shatibi", "field": "alias_en"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["id"], self.biography.pk)

    def test_staff_without_view_permission_cannot_access_endpoint(self):
        User = get_user_model()
        staff_user = User.objects.create_user(
            email="staff-live@example.com",
            password="password",
            username="staff-live@example.com",
            is_staff=True,
        )
        self.client.force_login(staff_user)

        response = self.client.get(self.url, {"q": "احمد بن علي الشاطبي"})

        self.assertNotEqual(response.status_code, 200)

    def test_empty_and_short_queries_return_no_matches(self):
        self.client.force_login(self.admin_user)

        empty_response = self.client.get(self.url, {"q": ""})
        short_response = self.client.get(self.url, {"q": "ab"})

        self.assertEqual(empty_response.status_code, 200)
        self.assertEqual(short_response.status_code, 200)
        self.assertEqual(empty_response.json()["results"], [])
        self.assertEqual(short_response.json()["results"], [])


class BiographyExportAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="password",
            username="admin@example.com",
        )
        self.client.force_login(self.admin_user)

        self.kufa = Location.objects.create(
            city_ar="الكوفة",
            city_en="Kufa",
            country_ar="العراق",
            country_en="Iraq",
        )
        self.makkah = Location.objects.create(
            city_ar="مكة",
            city_en="Makkah",
            country_ar="الحجاز",
            country_en="Hijaz",
        )
        self.madinah = Location.objects.create(
            city_ar="المدينة",
            city_en="Madinah",
            country_ar="الحجاز",
            country_en="Hijaz",
        )
        self.attribute_10k = Attribute.objects.create(
            short_name_ar="١٠ك",
            short_name_en="10M",
            long_name_ar="القراءات العشر الكبرى",
            long_name_en="Ten Major Readings",
        )
        self.attribute_azhar = Attribute.objects.create(
            short_name_ar="أزهر",
            short_name_en="Azhar",
            long_name_ar="قراء الأزهر",
            long_name_en="Azhar Reciters",
        )

        self.published_biography = Biography.objects.create(
            full_name_ar="عاصم بن أبي النجود",
            full_name_en="Asim ibn Abi al-Najud",
            alias_ar="عاصم الكوفي",
            alias_en="Asim al-Kufi",
            birthplace=self.kufa,
            death_location=self.madinah,
            birth_hijri_year=60,
            birth_hijri_month=3,
            birth_hijri_day=15,
            birth_greg_year=680,
            birth_greg_month=1,
            birth_greg_day=5,
            death_hijri_year=127,
            death_hijri_month=10,
            death_hijri_day=20,
            death_greg_year=745,
            death_greg_month=8,
            death_greg_day=1,
            comments_ar="إمام مشهور",
            comments_en="A famous imam",
            published=True,
        )
        self.published_biography.hometown.set([self.kufa])
        self.published_biography.attributes.set([
            self.attribute_10k,
            self.attribute_azhar,
        ])

        self.draft_biography = Biography.objects.create(
            full_name_ar="قارئ غير منشور",
            full_name_en="Unpublished Reciter",
            birthplace=self.makkah,
            published=False,
        )

    def test_csv_export_uses_import_headers_and_utf8_bom(self):
        response = self.client.get(reverse("admin:core_biography_export_csv"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content[:3], b"\xef\xbb\xbf")
        self.assertIn(
            'attachment; filename="biographies_export_',
            response["Content-Disposition"],
        )

        text = response.content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)

        self.assertEqual(reader.fieldnames, csv_import.sample_columns())
        self.assertEqual(len(rows), 2)

        row = next(r for r in rows if r["full_name_ar"] == "عاصم بن أبي النجود")
        self.assertEqual(row["published"], "yes")
        self.assertEqual(row["birthplace_city_ar"], "الكوفة")
        self.assertEqual(row["hometown_country_en"], "Iraq")
        self.assertEqual(row["death_location_city_en"], "Madinah")
        self.assertEqual(row["attribute_1"], "١٠ك")
        self.assertEqual(row["attribute_2"], "أزهر")
        self.assertEqual(row["comments_ar"], "إمام مشهور")

    def test_xlsx_export_uses_import_headers_and_values(self):
        response = self.client.get(reverse("admin:core_biography_export_xlsx"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        workbook = load_workbook(io.BytesIO(response.content), read_only=True)
        worksheet = workbook["Biographies"]
        rows = list(worksheet.iter_rows(values_only=True))

        self.assertEqual(list(rows[0]), csv_import.sample_columns())
        values = dict(zip(rows[0], rows[1]))
        self.assertEqual(values["full_name_ar"], "عاصم بن أبي النجود")
        self.assertEqual(values["published"], "yes")
        self.assertEqual(values["birthplace_city_en"], "Kufa")
        self.assertEqual(values["hometown_city_ar"], "الكوفة")
        self.assertEqual(values["attribute_1"], "١٠ك")

    def test_csv_export_preserves_admin_filters(self):
        response = self.client.get(
            reverse("admin:core_biography_export_csv"),
            {"published__exact": "1"},
        )

        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["full_name_ar"], "عاصم بن أبي النجود")

    def test_changelist_export_links_preserve_querystring(self):
        response = self.client.get(
            reverse("admin:core_biography_changelist"),
            {"published__exact": "1", "q": "عاصم"},
        )

        self.assertContains(
            response,
            f'{reverse("admin:core_biography_export_csv")}?published__exact=1&amp;q=%D8%B9%D8%A7%D8%B5%D9%85',
        )
        self.assertContains(
            response,
            f'{reverse("admin:core_biography_export_xlsx")}?published__exact=1&amp;q=%D8%B9%D8%A7%D8%B5%D9%85',
        )


class BiographyImportRecitersAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            email="admin-import@example.com",
            password="password",
            username="admin-import@example.com",
        )
        self.client.force_login(self.admin_user)
        self.url = reverse("admin:core_biography_import_reciters")

    def test_commit_step_translates_unpublished_mode_in_arabic_admin(self):
        session = self.client.session
        session["reciters_import_wizard"] = {
            "published_mode": "unpublished",
            "rows": [{"full_name_ar": "قارئ تجريبي"}],
            "stats": {"total": 1},
            "date_decisions": {},
            "location_decisions": {},
            "attr_decisions": {},
        }
        session.save()

        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "ar"
        response = self.client.get(f"{self.url}?step=commit")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "غير منشور")
        self.assertNotContains(response, ">unpublished<")
