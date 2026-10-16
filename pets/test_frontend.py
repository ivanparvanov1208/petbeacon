"""Tests for the front-end contract: design tokens, partials and ARIA wiring.

These guard the redesign against silent regressions — e.g. re-introducing the
Tailwind CDN, breaking the shared field partial, or losing the ARIA wiring that
ties inputs to their error messages.
"""

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
    """Start the module from the default language.

    LocaleMiddleware activates a language per request and never deactivates it,
    so a test that fetches /en/ leaves English active for whatever runs next in
    the same thread. Several tests here render templates directly — with no
    request, and therefore no middleware — and assert on Bulgarian text, so the
    active language has to be pinned rather than inherited.
    """
    translation.activate(settings.LANGUAGE_CODE)


def tearDownModule():
    translation.activate(settings.LANGUAGE_CODE)


class _ButtonParser(HTMLParser):
    """Collects every <button> as (attrs, inner_text)."""

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
    """Pin the active language to the default for the duration of a test class.

    ``LocaleMiddleware`` activates a language per request and never deactivates
    it, and Django keeps the active language in thread-local state. A test that
    fetches ``/en/`` therefore leaves English active for every test that runs
    after it in the same thread, which breaks assertions on Bulgarian text.
    Any test that touches an explicitly-prefixed URL must mix this in.
    """

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
    """Template comments must never reach the rendered page.

    Django's ``{# ... #}`` comment syntax is single-line only: the lexer pattern
    is not DOTALL, so an opening ``{#`` whose ``#}`` sits on a later line is
    emitted verbatim as page text. It renders as broken markup in the middle of
    the body and is invisible in the template's visual structure, which makes it
    an easy mistake to reintroduce.
    """

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

    def test_rendered_pages_contain_no_template_syntax(self):
        user = User.objects.create_user(username="comments", password="password123")
        Pet.objects.create(owner=user, name="Рекс", species="dog")
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
        ]
        leftovers = ("{#", "#}", "{% comment", "{% endcomment", "{% translate", "{% blocktranslate")
        for url in pages:
            html = self.client.get(url).content.decode()
            for marker in leftovers:
                with self.subTest(url=url, marker=marker):
                    self.assertNotIn(marker, html)


class LanguageSwitcherDisclosureTests(DefaultLanguageMixin, TestCase):
    """The dropdown must actually open.

    The panel's visibility is owned entirely by the `hidden` utility, which the
    toggle script adds and removes. If `display: none` is baked into the
    `lang-panel` utility instead, removing the class changes nothing and the
    dropdown silently never opens — a failure with no visible cause in the
    template, so it is pinned here.
    """

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
        """The drawer variant is a segmented control, always visible."""
        self.assertIn("lang-segmented", self.html)
        self.assertNotIn('class="lang-segmented hidden"', self.html)


class BaseTemplateContractTests(DefaultLanguageMixin, TestCase):
    def setUp(self):
        self.client = Client()
        # `<html lang>` now reflects the active language, and LocaleMiddleware
        # activates it per request without a matching deactivate — so a test that
        # visited /en/ would otherwise leak into every test that follows it in the
        # same thread. Pin the default language for this class.
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
    """The field partial is used by all nine form templates."""

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

    def test_widgets_carry_no_styling_classes(self):
        """Regression: hard-coded widget classes fight the design system.

        `.field` is applied at render time by the partial; if forms.py also
        pinned e.g. `rounded-xl border-slate-200`, which one wins would depend
        on Tailwind's output order.
        """
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
        # Django sets aria-invalid for bound fields that have errors.
        self.assertIn('aria-invalid="true"', rendered)
        self.assertIn('aria-describedby="id_weight_error"', rendered)

    def test_add_class_filter_does_not_mutate_the_widget(self):
        """Rendering twice must not accumulate classes on the shared widget."""
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
        self.assertIn("не знаете точната дата", rendered)  # the actual help_text

    def test_checkbox_partial_omits_the_label_header(self):
        from django.template import Context, Template

        template = Template(
            '{% load petcare_tags %}'
            '{% include "partials/checkbox.html" with field=form.is_neutered %}'
        )
        rendered = template.render(Context({"form": PetForm()}))
        self.assertIn("is_neutered", rendered)
        # A checkbox is wrapped in its own <label>; it must not get a second one.
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
        # Summary entries deep-link to the offending input.
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
        """Extending base.html inside the 500 handler risks a nested failure."""
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
        """A button needs aria-label, title, or visible text to be reachable.

        Icon-only buttons are easy to leave unlabelled during a redesign, and
        the failure mode is a screen reader announcing nothing at all. Uses the
        standard library parser so the project gains no test dependency.
        """
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
        # Every <i class="fa-..."> must be aria-hidden, otherwise screen readers
        # announce the raw icon name ("fa-solid fa-print") as content.
        icons = re.findall(r'<i class="fa-[^"]*"', html)
        self.assertTrue(icons)
        for match in re.finditer(r'<i class="fa-[^"]*"[^>]*>', html):
            self.assertIn(
                "aria-hidden", match.group(0),
                f"icon missing aria-hidden: {match.group(0)[:70]}",
            )
