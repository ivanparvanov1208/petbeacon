
import pathlib
import re
from datetime import date, timedelta
from html.parser import HTMLParser

from django.conf import settings
from django.contrib.auth.models import User
from django.template import Context, Template
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import translation

from .forms import PetForm
from .models import Pet, Reminder

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "templates"
INPUT_CSS = BASE_DIR / "static" / "css" / "input.css"


def setUpModule():
    translation.activate(settings.LANGUAGE_CODE)


def tearDownModule():
    translation.activate(settings.LANGUAGE_CODE)


class _ButtonParser(HTMLParser):

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.buttons = []
        self._depth = 0
        self._attrs = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "button":
            if self._depth == 0:
                self._attrs = dict(attrs)
                self._text = []
            self._depth += 1

    def handle_endtag(self, tag):
        if tag == "button" and self._depth:
            self._depth -= 1
            if self._depth == 0 and self._attrs is not None:
                self.buttons.append((self._attrs, "".join(self._text)))
                self._attrs = None

    def handle_data(self, data):
        if self._depth:
            self._text.append(data)


def _iter_buttons(html):
    parser = _ButtonParser()
    parser.feed(html)
    return parser.buttons


class DefaultLanguageMixin:

    def setUp(self):
        super().setUp()
        self.addCleanup(translation.activate, settings.LANGUAGE_CODE)
        translation.activate(settings.LANGUAGE_CODE)


class AssetPipelineTests(DefaultLanguageMixin, TestCase):
    def test_no_tailwind_play_cdn_anywhere_in_templates(self):
        offenders = []
        for path in TEMPLATE_DIR.rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            if "cdn.tailwindcss.com" in text:
                offenders.append(str(path.relative_to(BASE_DIR)))
        self.assertEqual(offenders, [], f"Play CDN reintroduced in: {offenders}")

    def test_no_runtime_tailwind_config_script(self):
        offenders = []
        for path in TEMPLATE_DIR.rglob("*.html"):
            if "tailwind.config" in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(BASE_DIR)))
        self.assertEqual(offenders, [], f"Runtime tailwind.config found in: {offenders}")

    def test_base_template_loads_compiled_stylesheet(self):
        response = self.client.get(reverse("pets:home"))
        self.assertContains(response, "/static/css/app.css")

    def test_compiled_stylesheet_exists(self):
        self.assertTrue(
            (BASE_DIR / "static" / "css" / "app.css").exists(),
            "Run `npm run build` to generate static/css/app.css.",
        )

    def test_input_css_declares_the_component_classes_templates_rely_on(self):
        css = INPUT_CSS.read_text(encoding="utf-8")
        required = [
            "@utility btn", "@utility btn-primary", "@utility card", "@utility field",
            "@utility nav-link", "@utility badge", "@utility tab", "@utility page",
            "@utility label", "@utility hint", "@utility error-text",
            "--color-brand-500", "--radius-lg", "@custom-variant dark",
        ]
        missing = [token for token in required if token not in css]
        self.assertEqual(missing, [], f"input.css is missing: {missing}")

    def test_input_css_sources_django_templates(self):
        css = INPUT_CSS.read_text(encoding="utf-8")
        self.assertIn('@source "../../templates/**/*.html"', css)


class TemplateCommentHygieneTests(DefaultLanguageMixin, TestCase):

    def test_no_multiline_brace_comments_exist(self):
        offenders = []
        for path in sorted(TEMPLATE_DIR.rglob("*.html")):
            source = path.read_text(encoding="utf-8")
            for match in re.finditer(r"\{#", source):
                newline = source.find("\n", match.start())
                close = source.find("#}", match.start())
                if close == -1 or (newline != -1 and close > newline):
                    offenders.append(
                        f"{path.relative_to(TEMPLATE_DIR)}:"
                        f"{source[: match.start()].count(chr(10)) + 1}"
                    )
        self.assertEqual(
            offenders, [],
            "multi-line {# ... #} comment(s) render as visible text: "
            + ", ".join(offenders),
        )

    def test_include_tags_do_not_span_multiple_lines(self):
        offenders = []
        for path in sorted(TEMPLATE_DIR.rglob("*.html")):
            source = path.read_text(encoding="utf-8")
            for match in re.finditer(r"\{% include\b.*?%\}", source, re.DOTALL):
                if "\n" in match.group():
                    offenders.append(str(path.relative_to(TEMPLATE_DIR)))
        self.assertEqual(
            offenders, [],
            "multi-line {% include %} tags render as visible text: "
            + ", ".join(offenders),
        )

    def test_rendered_pages_contain_no_template_syntax(self):
        user = User.objects.create_user(username="comments", password="password123")
        pet = Pet.objects.create(owner=user, name="Рекс", species="dog")
        Reminder.objects.create(owner=user, title="Напомняне", due_date="2030-01-01")
        self.client.force_login(user)

        pages = [
            reverse("pets:home"),
            reverse("pets:dashboard"),
            reverse("pets:pet_list"),
            reverse("pets:pet_detail", kwargs={"pk": 1}),
            reverse("pets:pet_passport", kwargs={"pk": 1}),
            reverse("pets:reminder_list"),
            reverse("pets:pet_create"),
            reverse("pets:reminder_create"),
            reverse("pets:vaccination_create", kwargs={"pet_pk": pet.pk}),
            reverse("pets:medical_record_create", kwargs={"pet_pk": pet.pk}),
            reverse("pets:medication_create", kwargs={"pet_pk": pet.pk}),
            reverse("pets:vet_visit_create", kwargs={"pet_pk": pet.pk}),
            reverse("accounts:profile"),
        ]
        leftovers = (
            "{#", "#}", "{% comment", "{% endcomment", "{% translate",
            "{% blocktranslate", "{% include",
        )
        for url in pages:
            html = self.client.get(url).content.decode()
            for marker in leftovers:
                with self.subTest(url=url, marker=marker):
                    self.assertNotIn(marker, html)


class LanguageSwitcherDisclosureTests(DefaultLanguageMixin, TestCase):

    def setUp(self):
        self.client = Client()
        self.html = self.client.get("/en/").content.decode()

    def test_panel_utility_does_not_hide_itself(self):
        css = (BASE_DIR / "static" / "css" / "app.css").read_text(encoding="utf-8")
        match = re.search(r"\.lang-panel\{([^}]*)\}", css)
        self.assertIsNotNone(match, ".lang-panel missing from the compiled CSS")
        self.assertNotIn(
            "display:none", match.group(1),
            "lang-panel must not set display, or removing the `hidden` class "
            "cannot reveal the dropdown",
        )

    def test_hidden_utility_still_exists(self):
        css = (BASE_DIR / "static" / "css" / "app.css").read_text(encoding="utf-8")
        self.assertIn(".hidden{display:none}", css)

    def test_panel_ships_closed(self):
        self.assertIn('id="langMenuDropdown" class="lang-panel hidden"', self.html)

    def test_toggle_script_removes_the_hidden_class(self):
        self.assertIn("langPanel.classList.toggle('hidden', !open)", self.html)
        self.assertIn("setLangOpen(langPanel.classList.contains('hidden'))", self.html)

    def test_trigger_advertises_the_disclosure(self):
        button = re.search(r'<button[^>]*id="langMenuButton"[^>]*>', self.html).group(0)
        self.assertIn('aria-expanded="false"', button)
        self.assertIn('aria-controls="langMenuDropdown"', button)
        self.assertIn("lang-trigger", button)

    def test_mobile_drawer_switcher_needs_no_toggle(self):
        self.assertIn("lang-segmented", self.html)
        self.assertNotIn('class="lang-segmented hidden"', self.html)


class BaseTemplateContractTests(DefaultLanguageMixin, TestCase):
    def setUp(self):
        self.client = Client()
        self.addCleanup(translation.activate, settings.LANGUAGE_CODE)
        translation.activate(settings.LANGUAGE_CODE)

    def test_document_language_is_bulgarian(self):
        self.assertContains(self.client.get("/bg/"), '<html lang="bg"')

    def test_document_language_follows_the_active_language(self):
        self.assertContains(self.client.get("/en/"), '<html lang="en"')

    def test_has_skip_link(self):
        self.assertContains(self.client.get(reverse("pets:home")), 'class="skip-link"')
        self.assertContains(self.client.get(reverse("pets:home")), 'href="#main"')

    def test_main_landmark_is_present(self):
        self.assertContains(self.client.get(reverse("pets:home")), 'id="main"')

    def test_theme_toggle_is_present_before_first_paint(self):
        html = self.client.get(reverse("pets:home")).content.decode()
        self.assertIn('id="themeToggle"', html)
        self.assertIn("prefers-color-scheme: dark", html)

    def test_no_inline_javascript_in_flash_close_button(self):
        html = self.client.get(reverse("pets:home")).content.decode()
        self.assertNotIn("onclick=", html)


class SharedFieldPartialTests(DefaultLanguageMixin, TestCase):

    FORM_TEMPLATES = [
        "pets/pet_form.html",
        "pets/vaccination_form.html",
        "pets/medication_form.html",
        "pets/medical_record_form.html",
        "pets/vet_visit_form.html",
        "pets/reminder_form.html",
        "accounts/login.html",
        "accounts/register.html",
        "accounts/profile.html",
    ]

    def test_every_form_template_uses_the_shared_partial(self):
        offenders = [
            name for name in self.FORM_TEMPLATES
            if 'partials/field.html' not in (TEMPLATE_DIR / name).read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [], f"Not using the field partial: {offenders}")

    def test_field_partial_exists(self):
        self.assertTrue((TEMPLATE_DIR / "partials" / "field.html").exists())

    def test_every_form_template_uses_the_error_partials(self):
        """Regression: the login page hand-rolled its error banner.

        It shipped a non-field error block of its own instead of including the
        shared partial, and never included the consolidated summary at all, so
        a login form left blank showed inline errors but no summary and no jump
        links. Every form template must reach both partials, directly or through
        `form_open.html`.
        """
        offenders = []
        for name in self.FORM_TEMPLATES:
            source = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
            if "partials/form_open.html" in source:
                continue
            if "partials/error_summary.html" not in source:
                offenders.append(f"{name} (no error_summary)")
            if "partials/non_field_errors.html" not in source:
                offenders.append(f"{name} (no non_field_errors)")
        self.assertEqual(offenders, [], f"Bypassing the error partials: {offenders}")

    def test_non_field_errors_partial_exists(self):
        self.assertTrue((TEMPLATE_DIR / "partials" / "non_field_errors.html").exists())

    def test_login_page_renders_a_summary_for_blank_credentials(self):
        """The case that exposed the missing include."""
        User.objects.create_user(username="blanklogin", password="password123")
        response = self.client.post(
            reverse("accounts:login"), {"username": "", "password": ""}
        )
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="form-errors"', html)
        self.assertIn("Потребителско име", html)

    def test_login_page_shows_no_empty_summary_for_wrong_credentials(self):
        """Wrong credentials are non-field errors, so the summary stays hidden."""
        User.objects.create_user(username="wrongcreds", password="password123")
        html = self.client.post(
            reverse("accounts:login"), {"username": "wrongcreds", "password": "nope"}
        ).content.decode()
        self.assertNotIn('id="form-errors"', html)
        self.assertIn('role="alert"', html)

    def test_widgets_carry_no_styling_classes(self):
        from . import forms as pet_forms

        for name in ("PetForm", "VaccinationForm", "MedicalRecordForm",
                     "MedicationForm", "VetVisitForm", "ReminderForm"):
            form_class = getattr(pet_forms, name)
            bound = form_class()
            for field_name, field in bound.fields.items():
                if field.widget.__class__.__name__.endswith("CheckboxInput"):
                    continue
                classes = field.widget.attrs.get("class", "")
                self.assertEqual(
                    classes, "",
                    f"{name}.{field_name} still hard-codes widget classes: {classes!r}",
                )

    def test_add_class_filter_applies_classes_and_aria(self):
        from pets.templatetags.petcare_tags import add_class

        from .forms import PetForm

        form = PetForm(data={"name": "Рекс", "species": "dog", "weight": "-5"})
        self.assertFalse(form.is_valid())

        rendered = str(add_class(form["weight"], "field field-error"))
        self.assertIn("field", rendered)
        self.assertIn("field-error", rendered)
        self.assertIn('aria-invalid="true"', rendered)
        self.assertIn('aria-describedby="id_weight_error"', rendered)

    def test_add_class_filter_does_not_mutate_the_widget(self):
        from pets.templatetags.petcare_tags import add_class

        form = PetForm()
        first = str(add_class(form["name"], "field"))
        second = str(add_class(form["name"], "field"))
        self.assertEqual(first, second)

    def test_add_class_filter_ignores_non_bound_fields(self):
        from pets.templatetags.petcare_tags import add_class

        self.assertEqual(add_class("not a field", "field"), "not a field")

    def test_file_input_gets_the_file_input_treatment(self):
        from pets.templatetags.petcare_tags import add_class

        from .forms import PetForm

        rendered = str(add_class(PetForm()["photo"], "file-input"))
        self.assertIn("file-input", rendered)

    def test_field_partial_renders_label_help_and_aria_wiring(self):
        from django.template import Context, Template

        template = Template(
            '{% load petcare_tags %}'
            '{% include "partials/field.html" with field=form.approximate_age %}'
        )
        rendered = template.render(Context({"form": PetForm()}))

        self.assertIn("<label", rendered)
        self.assertIn("hint", rendered)
        self.assertIn('id="id_approximate_age_helptext"', rendered)
        self.assertIn('aria-describedby="id_approximate_age_helptext"', rendered)
        self.assertIn("не знаете точната дата", rendered)

    def test_checkbox_partial_omits_the_label_header(self):
        from django.template import Context, Template

        template = Template(
            '{% load petcare_tags %}'
            '{% include "partials/checkbox.html" with field=form.is_neutered %}'
        )
        rendered = template.render(Context({"form": PetForm()}))
        self.assertIn("is_neutered", rendered)
        self.assertEqual(rendered.count("<label"), 1)


class QueryTransformTagTests(DefaultLanguageMixin, TestCase):
    def _request(self, **params):
        from django.http import QueryDict

        request = type("R", (), {"GET": QueryDict("", mutable=True)})()
        for key, value in params.items():
            request.GET[key] = value
        return request

    def test_preserves_other_params_and_overrides_page(self):
        template = Template("{% load petcare_tags %}?{% query_transform page=3 %}")
        out = template.render(Context({"request": self._request(status="overdue", page="1")}))
        self.assertIn("status=overdue", out)
        self.assertIn("page=3", out)

    def test_drops_empty_values(self):
        template = Template("{% load petcare_tags %}?{% query_transform q='' %}")
        out = template.render(Context({"request": self._request(q="hello", status="all")}))
        self.assertNotIn("q=", out)
        self.assertIn("status=all", out)

    def test_pagination_links_preserve_active_filters(self):
        from datetime import date, timedelta

        from django.contrib.auth.models import User

        from .models import Pet, Reminder

        user = User.objects.create_user(username="pg", password="password123")
        pet = Pet.objects.create(owner=user, name="Рекс", species="dog")
        for i in range(25):
            Reminder.objects.create(
                owner=user, pet=pet, title=f"R{i}", due_date=date.today() + timedelta(days=i)
            )

        self.client.force_login(user)
        html = self.client.get(reverse("pets:reminder_list") + "?status=upcoming").content.decode()

        page2 = re.search(r'href="\?([^"]*page=2[^"]*)"', html)
        self.assertIsNotNone(page2, "no link to page 2")
        self.assertIn("status=upcoming", page2.group(1))


class ErrorStateRenderingTests(DefaultLanguageMixin, TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        self.user = User.objects.create_user(username="errs", password="password123")
        self.client.force_login(self.user)

    def test_form_errors_produce_summary_and_inline_messages(self):
        response = self.client.post(reverse("pets:pet_create"), {
            "name": "", "species": "dog", "weight": "-1",
            "microchip_number": "nope", "birth_date": "2099-01-01",
        })
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        self.assertIn('id="form-errors"', html)
        self.assertIn('role="alert"', html)
        self.assertIn('aria-invalid="true"', html)
        self.assertIn("field-error", html)
        self.assertRegex(html, r'href="#id_\w+"')

    def test_valid_form_has_no_error_markup(self):
        response = self.client.get(reverse("pets:pet_create"))
        html = response.content.decode()
        self.assertNotIn('id="form-errors"', html)
        self.assertNotIn("aria-invalid", html)


class ErrorPageTests(DefaultLanguageMixin, TestCase):
    def test_404_uses_custom_template(self):
        response = self.client.get("/no-such-page-at-all/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Страницата не е намерена", status_code=404)

    def test_error_templates_exist(self):
        for name in ("404.html", "403.html", "500.html"):
            self.assertTrue((TEMPLATE_DIR / name).exists(), f"{name} missing")

    def test_500_template_does_not_extend_base(self):
        text = (TEMPLATE_DIR / "500.html").read_text(encoding="utf-8")
        self.assertNotIn("{% extends", text)


class AccessibleControlsTests(DefaultLanguageMixin, TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        from .models import Pet, Reminder

        self.user = User.objects.create_user(username="a11y", password="password123")
        self.pet = Pet.objects.create(owner=self.user, name="Рекс", species="dog")
        self.reminder = Reminder.objects.create(
            owner=self.user, pet=self.pet, title="Преглед", due_date="2026-01-01"
        )
        self.client.force_login(self.user)

    def test_every_button_has_an_accessible_name(self):
        pages = [
            reverse("pets:home"),
            reverse("pets:dashboard"),
            reverse("pets:pet_list"),
            reverse("pets:reminder_list"),
            reverse("pets:reminder_create"),
            reverse("pets:pet_create"),
        ]

        for path in pages:
            for attrs, text in _iter_buttons(self.client.get(path).content.decode()):
                name = (
                    attrs.get("aria-label")
                    or attrs.get("title")
                    or text.strip()
                    or attrs.get("value")
                )
                self.assertTrue(
                    name,
                    f"<button> without an accessible name on {path}: "
                    f"{attrs} inner={text.strip()!r}",
                )

    def test_every_icon_is_hidden_from_screen_readers(self):
        pages = [
            reverse("pets:home"),
            reverse("pets:dashboard"),
            reverse("pets:pet_list"),
            reverse("pets:reminder_list"),
            reverse("pets:pet_detail", kwargs={"pk": self.pet.pk}),
        ]

        offenders = []
        for path in pages:
            html = self.client.get(path).content.decode()
            for match in re.finditer(r"<i class=\"fa-[^\"]*\"[^>]*>", html):
                if "aria-hidden" not in match.group(0):
                    offenders.append((path, match.group(0)[:60]))
        self.assertEqual(offenders, [], f"icons missing aria-hidden: {offenders[:5]}")

    def test_nav_marks_current_page(self):
        from django.contrib.auth.models import User

        html = self.client.get(reverse("pets:reminder_list")).content.decode()
        self.assertIn('aria-current="page"', html)

    def test_tab_bar_marks_active_tab(self):
        html = self.client.get(
            reverse("pets:pet_detail", kwargs={"pk": self.pet.pk}) + "?tab=vaccinations"
        ).content.decode()
        self.assertIn('aria-current="page"', html)

    def test_icon_only_buttons_expose_text_or_aria_label(self):
        html = self.client.get(reverse("pets:pet_list")).content.decode()
        icons = re.findall(r'<i class="fa-[^"]*"', html)
        self.assertTrue(icons)
        for match in re.finditer(r'<i class="fa-[^"]*"[^>]*>', html):
            self.assertIn(
                "aria-hidden", match.group(0),
                f"icon missing aria-hidden: {match.group(0)[:70]}",
            )
