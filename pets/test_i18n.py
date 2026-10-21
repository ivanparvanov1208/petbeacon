
import pathlib
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from pets import i18n_tools
from pets.models import Pet, Reminder

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
LOCALE_DIR = BASE_DIR / "locale"

CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")


def po_path(code):
    return LOCALE_DIR / code / "LC_MESSAGES" / "django.po"


def setUpModule():
    translation.activate(settings.LANGUAGE_CODE)


def tearDownModule():
    translation.activate(settings.LANGUAGE_CODE)


class DefaultLanguageMixin:

    def setUp(self):
        super().setUp()
        self.addCleanup(translation.activate, settings.LANGUAGE_CODE)
        translation.activate(settings.LANGUAGE_CODE)


class CatalogueIntegrityTests(DefaultLanguageMixin, TestCase):

    def test_every_language_has_a_po_and_a_mo(self):
        for code, _name in settings.LANGUAGES:
            with self.subTest(code=code):
                self.assertTrue(po_path(code).exists(), f"missing {code}/django.po")
                self.assertTrue(
                    po_path(code).with_suffix(".mo").exists(), f"missing {code}/django.mo"
                )

    def test_english_catalogue_is_complete(self):
        catalogue = i18n_tools.parse_po(po_path("en"))
        untranslated = [e[1] for e in catalogue.entries if not e[3] or not e[3][0]]
        self.assertEqual(
            untranslated, [],
            f"{len(untranslated)} string(s) have no English translation: {untranslated}",
        )

    def test_catalogue_matches_the_current_source(self):
        stale = []
        for code, _name in settings.LANGUAGES:
            existing = i18n_tools.parse_po(po_path(code))
            found = []
            seen = set()
            for directory, files in (
                (i18n_tools._PY_SOURCE_DIRS, i18n_tools._PY_SOURCE_FILES),
                (i18n_tools._TEMPLATE_SOURCE_DIRS, None),
            ):
                for name in directory:
                    root = BASE_DIR / name
                    if not root.is_dir():
                        continue
                    paths = (
                        [root / f for f in files]
                        if files
                        else sorted(root.glob("**/*.html"))
                    )
                    for path in paths:
                        if not path.is_file():
                            continue
                        entries = (
                            i18n_tools.extract_from_python(path)
                            if path.suffix == ".py"
                            else i18n_tools.extract_from_template(path)
                        )
                        for entry in entries:
                            key = (entry[0], entry[1], entry[2])
                            if key not in seen:
                                seen.add(key)
                                found.append(entry)

            merged, removed = i18n_tools.merge(found, existing)
            for entry in merged:
                if not entry[3] or not entry[3][0]:
                    if code != settings.LANGUAGE_CODE:
                        stale.append(f"{code}: untranslated {entry[1]!r}")
            for entry in removed:
                stale.append(f"{code}: obsolete {entry[1]!r}")

        self.assertEqual(stale, [], "translation catalogues are out of date")


class LanguageSwitcherTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.addCleanup(translation.activate, settings.LANGUAGE_CODE)
        translation.activate(settings.LANGUAGE_CODE)

    def test_set_language_endpoint_is_reachable(self):
        self.assertEqual(reverse("set_language"), "/i18n/setlang/")

    def test_posting_switches_language_and_redirects_to_same_page(self):
        response = self.client.post(
            reverse("set_language"), {"next": "/bg/", "language": "en"}
        )
        self.assertRedirects(
            response, "/en/", fetch_redirect_response=False
        )
        self.assertEqual(response.cookies["django_language"].value, "en")

        html = self.client.get("/en/").content.decode()
        self.assertIn('<html lang="en"', html)
        self.assertIn("Get started for free", html)

    def test_switching_back_restores_bulgarian(self):
        self.client.post(reverse("set_language"), {"next": "/bg/", "language": "en"})
        self.client.post(reverse("set_language"), {"next": "/en/", "language": "bg"})

        html = self.client.get("/bg/").content.decode()
        self.assertIn('<html lang="bg"', html)
        self.assertIn("Започнете безплатно", html)

    def test_language_prefix_alone_selects_the_language(self):
        self.assertIn("Get started for free", self.client.get("/en/").content.decode())
        self.assertIn("Започнете безплатно", self.client.get("/bg/").content.decode())

    def test_switcher_is_rendered_for_anonymous_and_authenticated_users(self):
        html = self.client.get(reverse("pets:home")).content.decode()
        self.assertIn(reverse("set_language"), html)
        self.assertEqual(html.count('name="language" value="en"'), 2)
        self.assertEqual(html.count('name="language" value="bg"'), 0)
        self.assertIn("Започнете безплатно", html)

        user = User.objects.create_user(username="switcher", password="password123")
        self.client.force_login(user)
        html = self.client.get(reverse("pets:dashboard")).content.decode()
        self.assertIn(reverse("set_language"), html)
        self.assertEqual(html.count('name="language" value="en"'), 2)
        self.assertEqual(html.count('name="language" value="bg"'), 0)

    def test_switcher_marks_the_active_language_and_hides_it_from_tab_order(self):
        html = self.client.get("/en/").content.decode()
        self.assertIn('aria-current="true"', html)
        self.assertEqual(html.count('name="language" value="bg"'), 2)
        self.assertEqual(html.count('name="language" value="en"'), 0)
        self.assertIn("Български", html)

    def test_switcher_preserves_the_current_path_in_next(self):
        user = User.objects.create_user(username="nextpath", password="password123")
        pet = Pet.objects.create(owner=user, name="Рекс", species="dog")
        self.client.force_login(user)
        url = reverse("pets:pet_detail", kwargs={"pk": pet.pk})

        html = self.client.get(url).content.decode()
        self.assertIn(f'value="{url}"', html)

    def test_switcher_works_without_javascript(self):
        html = self.client.get("/bg/").content.decode()
        self.assertIn(f'<form method="POST" action="{reverse("set_language")}">', html)
        self.assertIn('type="submit" name="language"', html)

    def test_bare_root_redirects_to_the_default_language_prefix(self):
        response = self.client.get("/", follow=False)
        self.assertRedirects(
            response, f"/{settings.LANGUAGE_CODE}/", fetch_redirect_response=False
        )

    def test_admin_is_not_language_prefixed(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/admin/login/?next=/admin/")


@override_settings(LANGUAGES=[("bg", "Български"), ("en", "English")])
class TranslationRenderingTests(DefaultLanguageMixin, TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="render", password="password123")
        self.pet = Pet.objects.create(
            owner=self.user, name="Рекс", species="dog", weight="14.5"
        )
        Reminder.objects.create(
            owner=self.user, pet=self.pet, title="Ваксинация", due_date="2030-01-01"
        )

    def _unprefixed(self, patterns):
        with translation.override(settings.LANGUAGE_CODE):
            paths = [
                reverse(name, kwargs=kwargs) if kwargs else reverse(name)
                for name, kwargs in patterns
            ]
        prefix = f"/{settings.LANGUAGE_CODE}"
        return [path[len(prefix):] or "/" for path in paths]

    def _public_paths(self):
        return self._unprefixed([
            ("pets:home", None),
            ("accounts:login", None),
            ("accounts:register", None),
        ])

    def _private_paths(self):
        return self._unprefixed([
            ("pets:dashboard", None),
            ("pets:pet_list", None),
            ("pets:pet_detail", {"pk": self.pet.pk}),
            ("pets:pet_passport", {"pk": self.pet.pk}),
            ("pets:reminder_list", None),
            ("pets:pet_create", None),
            ("pets:vaccination_create", {"pet_pk": self.pet.pk}),
            ("accounts:profile", None),
        ])

    def test_every_page_renders_in_both_languages(self):
        for path in self._public_paths():
            for code in ("bg", "en"):
                with self.subTest(path=path, lang=code):
                    self.assertEqual(self.client.get(f"/{code}{path}").status_code, 200)

        self.client.force_login(self.user)
        for path in self._private_paths():
            for code in ("bg", "en"):
                with self.subTest(path=path, lang=code):
                    self.assertEqual(self.client.get(f"/{code}{path}").status_code, 200)

    def test_english_pages_contain_no_cyrillic_chrome(self):
        chrome = [
            "Табло", "Любимци", "Напомняния", "Назад", "Отказ", "Запази",
            "Моят профил", "Моите любимци", "Вход", "Изход", "Търсене",
            "Всички", "Мъжки", "Женски", "Чип", "Профил", "Всички любимци",
        ]
        paths = self._public_paths()
        self.client.force_login(self.user)
        paths += self._private_paths()

        for path in paths:
            html = self.client.get(f"/en{path}").content.decode()
            for phrase in chrome:
                with self.subTest(path=path, phrase=phrase):
                    self.assertNotIn(phrase, html)

    def test_bulgarian_pages_use_the_source_language(self):
        self.client.force_login(self.user)
        html = self.client.get(f"/bg{self._private_paths()[1]}").content.decode()
        for phrase in ("Моите домашни любимци", "Търсене", "Вид", "Профил"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, html)
    def test_switcher_next_never_double_prefixes_the_language(self):
        self.client.force_login(self.user)
        for code in ("bg", "en"):
            for path in self._private_paths():
                with self.subTest(path=path, lang=code):
                    html = self.client.get(f"/{code}{path}").content.decode()
                    expected = f'value="/{code}{path}"'
                    self.assertIn(expected, html)
                    self.assertNotIn(f"/{code}/{code}", html)

    def test_model_choices_translate(self):
        pet = self.pet
        with translation.override("bg"):
            self.assertEqual(pet.get_species_display(), "Куче")
        with translation.override("en"):
            self.assertEqual(pet.get_species_display(), "Dog")

    def test_model_help_text_translates(self):
        field = Pet._meta.get_field("approximate_age")
        with translation.override("bg"):
            self.assertIn("точната дата", str(field.help_text))
        with translation.override("en"):
            self.assertIn("date of birth", str(field.help_text))

    def test_age_display_uses_the_right_plural_forms(self):
        from datetime import date

        today = date.today()
        pet = self.pet
        with translation.override("en"):
            pet.birth_date = today.replace(year=today.year - 2)
            self.assertIn("yr", pet.age_display)
            pet.birth_date = today
            self.assertEqual(pet.age_display, "0 days")
            pet.birth_date = date(today.year - 1, today.month, today.day - 1) \
                if today.day > 1 else today
            self.assertRegex(pet.age_display, r"^1 yr$")


class FormTranslationTests(TestCase):

    def test_pet_form_placeholders_translate(self):
        from pets.forms import PetForm

        with translation.override("en"):
            widget = PetForm().fields["breed"].widget
            self.assertEqual(str(widget.attrs["placeholder"]), "e.g. German Shepherd, Siamese...")
        with translation.override("bg"):
            widget = PetForm().fields["breed"].widget
            self.assertIn("Немска овчарка", str(widget.attrs["placeholder"]))

    def test_validation_errors_translate(self):
        from pets.forms import PetForm

        with translation.override("en"):
            form = PetForm(data={"name": "Rex", "species": "dog", "weight": "-3",
                                 "approximate_age": "", "food_diet": "", "allergies": "",
                                 "special_notes": "", "breed": "", "gender": "unknown",
                                 "microchip_number": "", "passport_number": "",
                                 "birth_date": "", "is_neutered": ""})
            self.assertFalse(form.is_valid())
            errors = " ".join(form.errors.get("weight", []))
            self.assertIn("positive number", errors)
        with translation.override("bg"):
            form = PetForm(data={"name": "Рекс", "species": "dog", "weight": "-3",
                                 "approximate_age": "", "food_diet": "", "allergies": "",
                                 "special_notes": "", "breed": "", "gender": "unknown",
                                 "microchip_number": "", "passport_number": "",
                                 "birth_date": "", "is_neutered": ""})
            self.assertFalse(form.is_valid())
            errors = " ".join(form.errors.get("weight", []))
            self.assertIn("положително", errors)


class PoRoundTripTests(TestCase):

    def test_po_round_trip_preserves_contexts_and_plurals(self):
        original = i18n_tools.Catalogue([
            ("", "Hello", "", ["Hello there"]),
            ("greeting", "Bye", "", ["Goodbye"]),
            ("", "%(count)s item", "%(count)s items", ["%(count)s item", "%(count)s items"]),
        ])
        path = LOCALE_DIR.parent / "i18n_roundtrip_test.po"
        try:
            i18n_tools.write_po(path, original, code="xx", language_name="Test")
            reloaded = i18n_tools.parse_po(path)
            self.assertEqual(len(reloaded.entries), len(original.entries))
            self.assertEqual(
                sorted((e[0], e[1], e[2], tuple(e[3])) for e in reloaded.entries),
                sorted((e[0], e[1], e[2], tuple(e[3])) for e in original.entries),
            )
        finally:
            path.unlink(missing_ok=True)

    def test_mo_keys_match_python_gettext_conventions(self):
        from gettext import GNUTranslations

        catalogue = i18n_tools.Catalogue([
            ("", "One item", "Many items", ["%(count)s item", "%(count)s items"]),
            ("ctx", "Bye", "", ["Goodbye"]),
            ("", "Plain", "", ["Plain EN"]),
        ])
        mo_path = LOCALE_DIR.parent / "i18n_roundtrip_test.mo"
        try:
            i18n_tools.write_mo(catalogue, mo_path)
            with open(mo_path, "rb") as handle:
                translations = GNUTranslations(handle)
            self.assertEqual(translations.gettext("Plain"), "Plain EN")
            self.assertEqual(
                translations.ngettext("One item", "Many items", 1), "%(count)s item"
            )
            self.assertEqual(
                translations.ngettext("One item", "Many items", 3), "%(count)s items"
            )
            self.assertEqual(translations.gettext("ctx\x04Bye"), "Goodbye")
            self.assertEqual(translations.gettext("ctx\x04Missing"), "ctx\x04Missing")
        finally:
            mo_path.unlink(missing_ok=True)
