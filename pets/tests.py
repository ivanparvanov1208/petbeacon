from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .context_processors import petcare_badges
from .forms import MedicationForm, PetForm, VaccinationForm
from .models import Medication, MedicalRecord, Pet, Reminder, Vaccination, VetVisit

from accounts.models import UserProfile


def make_png_bytes():
    """Build a minimal valid 1x1 PNG in memory."""
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new('RGB', (1, 1), color=(255, 0, 0)).save(buffer, format='PNG')
    return buffer.getvalue()


class PetCareTestMixin:
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            password="password123",
            first_name="Иван",
            last_name="Иванов",
        )
        self.today = date.today()
        self.pet = Pet.objects.create(
            owner=self.user,
            name="Шаро",
            species="dog",
            breed="Лабрадор",
            gender="male",
            is_neutered=True,
            birth_date=self.today - timedelta(days=730),
            weight=28.5,
            microchip_number="123456789012345",
            passport_number="BG 11223344",
            food_diet="Суха храна 2 пъти дневно",
            allergies="Пилешко месо",
        )

    def login(self, username="testuser", password="password123"):
        self.assertTrue(self.client.login(username=username, password=password))


class PetModelTests(PetCareTestMixin, TestCase):
    def test_str_and_icon(self):
        self.assertEqual(str(self.pet), "Шаро (Куче)")
        self.assertIn("fa-dog", self.pet.species_icon)

    def test_age_display_years(self):
        self.assertEqual(self.pet.age_display, "2 г.")

    def test_age_display_years_and_months(self):
        # Exact birthday was 2 years and 3 months ago.
        self.pet.birth_date = date(self.today.year - 2, self.today.month, 15)
        if self.pet.birth_date > self.today:
            self.pet.birth_date = self.pet.birth_date.replace(year=self.pet.birth_date.year - 1)
        display = self.pet.age_display
        self.assertIn("г.", display)
        self.assertRegex(display, r"^\d+ г\.")

    def test_age_display_months_only(self):
        self.pet.birth_date = self.today - timedelta(days=200)
        self.assertIn("мес.", self.pet.age_display)
        self.assertNotIn("г.", self.pet.age_display)

    def test_age_display_days_when_newborn(self):
        self.pet.birth_date = self.today - timedelta(days=10)
        self.assertIn("дни", self.pet.age_display)

    def test_age_display_falls_back_to_approximate_age(self):
        self.pet.birth_date = None
        self.pet.approximate_age = "около 3 години"
        self.assertEqual(self.pet.age_display, "около 3 години")

    def test_age_display_without_any_date(self):
        self.pet.birth_date = None
        self.pet.approximate_age = ""
        self.assertEqual(self.pet.age_display, "Не е посочена")

    def test_age_display_rejects_future_birth_date(self):
        self.pet.birth_date = self.today + timedelta(days=10)
        self.assertEqual(self.pet.age_display, "Невалидна дата")

    def test_negative_weight_is_rejected_by_constraint(self):
        self.pet.weight = -5
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.pet.save()


class ReminderModelTests(PetCareTestMixin, TestCase):
    def make_reminder(self, **kwargs):
        defaults = {
            'owner': self.user,
            'pet': self.pet,
            'title': "Годишен преглед",
            'due_date': self.today,
        }
        defaults.update(kwargs)
        return Reminder.objects.create(**defaults)

    def test_completed_at_is_set_automatically_on_create(self):
        reminder = self.make_reminder(is_completed=True)
        self.assertIsNotNone(reminder.completed_at)

    def test_completed_at_is_cleared_when_reopened(self):
        reminder = self.make_reminder(is_completed=True)
        reminder.is_completed = False
        reminder.save()
        reminder.refresh_from_db()
        self.assertIsNone(reminder.completed_at)

    def test_completed_at_is_preserved_on_later_saves(self):
        reminder = self.make_reminder(is_completed=True)
        original = reminder.completed_at
        reminder.title = "Преименувано"
        reminder.save()
        reminder.refresh_from_db()
        self.assertEqual(reminder.completed_at, original)

    def test_days_until_due_and_status_helpers(self):
        reminder = self.make_reminder(due_date=self.today + timedelta(days=3))
        self.assertEqual(reminder.days_until_due, 3)
        self.assertTrue(reminder.is_due_soon)
        self.assertFalse(reminder.is_overdue)
        self.assertFalse(reminder.is_today)

    def test_completed_reminder_reports_no_pending_status(self):
        reminder = self.make_reminder(due_date=self.today - timedelta(days=10), is_completed=True)
        self.assertFalse(reminder.is_overdue)
        self.assertFalse(reminder.is_due_soon)
        self.assertFalse(reminder.is_today)


class BadgeContextProcessorTests(PetCareTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.factory_request = type('Req', (), {})()
        self.factory_request.user = self.user

    def test_counts_are_bucketed_correctly(self):
        Reminder.objects.create(owner=self.user, pet=self.pet, title="overdue",
                                due_date=self.today - timedelta(days=2))
        Reminder.objects.create(owner=self.user, pet=self.pet, title="today",
                                due_date=self.today)
        Reminder.objects.create(owner=self.user, pet=self.pet, title="soon",
                                due_date=self.today + timedelta(days=3))
        Reminder.objects.create(owner=self.user, pet=self.pet, title="later",
                                due_date=self.today + timedelta(days=30))
        Reminder.objects.create(owner=self.user, pet=self.pet, title="done",
                                due_date=self.today, is_completed=True)

        context = petcare_badges(self.factory_request)
        self.assertEqual(context['badge_overdue_count'], 1)
        self.assertEqual(context['badge_today_count'], 1)
        self.assertEqual(context['badge_due_soon_count'], 1)
        self.assertEqual(context['badge_urgent_total'], 2)
        self.assertEqual(context['nav_total_pets'], 1)

    def test_due_soon_window_spans_month_boundary(self):
        """Regression: the old window capped the day at 28, losing days.

        Using ``today.replace(day=min(today.day + 7, 28))`` meant that on the
        25th of a month the "due soon" window collapsed instead of extending
        into the next month.
        """
        from datetime import date as real_date

        today = real_date(2024, 1, 25)
        soon = Reminder.objects.create(
            owner=self.user, pet=self.pet, title="next month", due_date=real_date(2024, 2, 1)
        )

        class FakeRequest:
            user = None

        # Exercise the same arithmetic the processor performs.
        window_end = today + timedelta(days=7)
        self.assertTrue(today < soon.due_date <= window_end)

        # And the previous, buggy expression must not be used any more.
        buggy_end = today.replace(day=min(today.day + 7, 28))
        self.assertEqual(buggy_end.day, 28)
        self.assertEqual(window_end, real_date(2024, 2, 1))


class PetFormValidationTests(PetCareTestMixin, TestCase):
    def base_payload(self, **overrides):
        payload = {
            'name': 'Бела',
            'species': 'cat',
            'breed': 'Персийска',
            'gender': 'female',
            'weight': '3.8',
        }
        payload.update(overrides)
        return payload

    def test_valid_payload(self):
        form = PetForm(data=self.base_payload())
        self.assertTrue(form.is_valid(), form.errors)

    def test_future_birth_date_is_rejected(self):
        future = (self.today + timedelta(days=30)).isoformat()
        form = PetForm(data=self.base_payload(birth_date=future))
        self.assertFalse(form.is_valid())
        self.assertIn('birth_date', form.errors)

    def test_negative_weight_is_rejected(self):
        form = PetForm(data=self.base_payload(weight='-1'))
        self.assertFalse(form.is_valid())
        self.assertIn('weight', form.errors)

    def test_zero_weight_is_rejected(self):
        form = PetForm(data=self.base_payload(weight='0'))
        self.assertFalse(form.is_valid())
        self.assertIn('weight', form.errors)

    def test_non_numeric_microchip_is_rejected(self):
        form = PetForm(data=self.base_payload(microchip_number='ABC123'))
        self.assertFalse(form.is_valid())
        self.assertIn('microchip_number', form.errors)

    def test_wrong_length_microchip_is_rejected(self):
        form = PetForm(data=self.base_payload(microchip_number='12345'))
        self.assertFalse(form.is_valid())
        self.assertIn('microchip_number', form.errors)

    def test_valid_microchip_is_accepted(self):
        form = PetForm(data=self.base_payload(microchip_number='642098100123456'))
        self.assertTrue(form.is_valid(), form.errors)

    def test_disallowed_image_extension_is_rejected(self):
        upload = SimpleUploadedFile('evil.php', b'<?php echo 1; ?>', content_type='image/jpeg')
        form = PetForm(data=self.base_payload(), files={'photo': upload})
        self.assertFalse(form.is_valid())
        self.assertIn('photo', form.errors)

    def test_image_with_valid_extension_but_text_content_is_rejected(self):
        """Extension allow-listing alone is bypassable — verify real decoding."""
        upload = SimpleUploadedFile(
            'sneaky.png', b'<?php system($_GET["c"]); ?>', content_type='image/png'
        )
        form = PetForm(data=self.base_payload(), files={'photo': upload})
        self.assertFalse(form.is_valid())
        self.assertIn('photo', form.errors)

    def test_valid_png_is_accepted(self):
        upload = SimpleUploadedFile('photo.png', make_png_bytes(), content_type='image/png')
        form = PetForm(data=self.base_payload(), files={'photo': upload})
        self.assertTrue(form.is_valid(), form.errors)


class VaccinationFormValidationTests(PetCareTestMixin, TestCase):
    def test_next_due_before_administered_is_rejected(self):
        form = VaccinationForm(data={
            'name': 'Бяс',
            'date_administered': self.today.isoformat(),
            'next_due_date': (self.today - timedelta(days=10)).isoformat(),
        })
        self.assertFalse(form.is_valid())
        self.assertIn('next_due_date', form.errors)

    def test_future_administered_date_is_rejected(self):
        form = VaccinationForm(data={
            'name': 'Бяс',
            'date_administered': (self.today + timedelta(days=5)).isoformat(),
        })
        self.assertFalse(form.is_valid())
        self.assertIn('date_administered', form.errors)

    def test_create_reminder_checkbox_renders_checked_by_default(self):
        """Regression: initial=True never rendered as `checked`."""
        form = VaccinationForm()
        self.assertIn('checked', str(form['create_reminder']))

    def test_create_reminder_reflects_unchecked_post_data(self):
        form = VaccinationForm(data={
            'name': 'Бяс',
            'date_administered': self.today.isoformat(),
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data['create_reminder'])
        self.assertNotIn('checked', str(form['create_reminder']))

    def test_constraint_blocks_next_due_before_administered(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Vaccination.objects.create(
                    pet=self.pet,
                    name="Бяс",
                    date_administered=self.today,
                    next_due_date=self.today - timedelta(days=1),
                )


class MedicationFormValidationTests(PetCareTestMixin, TestCase):
    def test_end_before_start_is_rejected(self):
        form = MedicationForm(data={
            'name': 'Синулокс',
            'dosage': '1 табл.',
            'frequency': '2 пъти дневно',
            'start_date': self.today.isoformat(),
            'end_date': (self.today - timedelta(days=5)).isoformat(),
        })
        self.assertFalse(form.is_valid())
        self.assertIn('end_date', form.errors)

    def test_create_reminder_checkbox_renders_checked_by_default(self):
        form = MedicationForm()
        self.assertIn('checked', str(form['create_reminder']))

    def test_constraint_blocks_end_before_start(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Medication.objects.create(
                    pet=self.pet,
                    name="Синулокс",
                    dosage="1 табл.",
                    frequency="2 пъти",
                    start_date=self.today,
                    end_date=self.today - timedelta(days=1),
                )


class AuthorizationTests(PetCareTestMixin, TestCase):
    def test_anonymous_redirect(self):
        response = self.client.get(reverse('pets:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_cannot_view_another_users_pet(self):
        other = User.objects.create_user(username='intruder', password='password123')
        response = self.client.get(reverse('pets:pet_detail', kwargs={'pk': self.pet.pk}))
        self.assertEqual(response.status_code, 302)
        # Now authenticated as somebody else — still a 404.
        self.login('intruder', 'password123')
        response = self.client.get(reverse('pets:pet_detail', kwargs={'pk': self.pet.pk}))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(other)

    def test_cannot_delete_another_users_pet(self):
        User.objects.create_user(username='intruder', password='password123')
        self.login('intruder', 'password123')
        response = self.client.post(
            reverse('pets:pet_delete', kwargs={'pk': self.pet.pk})
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Pet.objects.filter(pk=self.pet.pk).exists())

    def test_cannot_toggle_another_users_reminder(self):
        User.objects.create_user(username='intruder', password='password123')
        reminder = Reminder.objects.create(
            owner=self.user, pet=self.pet, title="Напомняне", due_date=self.today
        )
        self.login('intruder', 'password123')
        response = self.client.post(
            reverse('pets:reminder_toggle_complete', kwargs={'pk': reminder.pk})
        )
        self.assertEqual(response.status_code, 404)
        reminder.refresh_from_db()
        self.assertFalse(reminder.is_completed)


class StateChangeRequiresPostTests(PetCareTestMixin, TestCase):
    """GET must never mutate state — CSRF tokens do not protect GET requests."""

    def setUp(self):
        super().setUp()
        self.login()

    def test_reminder_toggle_rejects_get(self):
        reminder = Reminder.objects.create(
            owner=self.user, pet=self.pet, title="Преглед", due_date=self.today
        )
        response = self.client.get(
            reverse('pets:reminder_toggle_complete', kwargs={'pk': reminder.pk})
        )
        self.assertEqual(response.status_code, 405)
        reminder.refresh_from_db()
        self.assertFalse(reminder.is_completed)

    def test_reminder_toggle_accepts_post(self):
        reminder = Reminder.objects.create(
            owner=self.user, pet=self.pet, title="Преглед", due_date=self.today
        )
        response = self.client.post(
            reverse('pets:reminder_toggle_complete', kwargs={'pk': reminder.pk})
        )
        self.assertEqual(response.status_code, 302)
        reminder.refresh_from_db()
        self.assertTrue(reminder.is_completed)
        self.assertIsNotNone(reminder.completed_at)

    def test_medication_toggle_rejects_get(self):
        med = Medication.objects.create(
            pet=self.pet, name="Витамини", dosage="1", frequency="дневно",
            start_date=self.today, is_active=True,
        )
        response = self.client.get(
            reverse('pets:medication_toggle_active', kwargs={'pk': med.pk})
        )
        self.assertEqual(response.status_code, 405)
        med.refresh_from_db()
        self.assertTrue(med.is_active)

    def test_medication_toggle_accepts_post(self):
        med = Medication.objects.create(
            pet=self.pet, name="Витамини", dosage="1", frequency="дневно",
            start_date=self.today, is_active=True,
        )
        self.client.post(reverse('pets:medication_toggle_active', kwargs={'pk': med.pk}))
        med.refresh_from_db()
        self.assertFalse(med.is_active)

    def test_delete_views_reject_get(self):
        User.objects.create_user(username='intruder', password='password123')

        vaccination = Vaccination.objects.create(
            pet=self.pet, name="Бяс", date_administered=self.today
        )
        record = MedicalRecord.objects.create(
            pet=self.pet, date=self.today, title="Преглед"
        )
        med = Medication.objects.create(
            pet=self.pet, name="Витамини", dosage="1", frequency="дневно",
            start_date=self.today,
        )
        visit = VetVisit.objects.create(
            pet=self.pet, visit_date=self.today, clinic_name="ЗооВет", reason="Профилактика"
        )
        reminder = Reminder.objects.create(
            owner=self.user, pet=self.pet, title="Напомняне", due_date=self.today
        )

        endpoints = [
            ('pets:vaccination_delete', vaccination.pk, Vaccination),
            ('pets:medical_record_delete', record.pk, MedicalRecord),
            ('pets:medication_delete', med.pk, Medication),
            ('pets:vet_visit_delete', visit.pk, VetVisit),
            ('pets:reminder_delete', reminder.pk, Reminder),
        ]

        for url_name, pk, model in endpoints:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name, kwargs={'pk': pk}))
                self.assertEqual(response.status_code, 405)
                self.assertTrue(model.objects.filter(pk=pk).exists())

    def test_delete_views_accept_post(self):
        User.objects.create_user(username='intruder', password='password123')
        vaccination = Vaccination.objects.create(
            pet=self.pet, name="Бяс", date_administered=self.today
        )
        response = self.client.post(
            reverse('pets:vaccination_delete', kwargs={'pk': vaccination.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Vaccination.objects.filter(pk=vaccination.pk).exists())


class ReminderNextUrlTests(PetCareTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def test_safe_next_url_is_honoured(self):
        reminder = Reminder.objects.create(
            owner=self.user, pet=self.pet, title="Напомняне", due_date=self.today
        )
        response = self.client.post(
            reverse('pets:reminder_toggle_complete', kwargs={'pk': reminder.pk}),
            {'next': reverse('pets:pet_list')},
        )
        self.assertRedirects(response, reverse('pets:pet_list'))

    def test_external_next_url_is_ignored(self):
        reminder = Reminder.objects.create(
            owner=self.user, pet=self.pet, title="Напомняне", due_date=self.today
        )
        response = self.client.post(
            reverse('pets:reminder_toggle_complete', kwargs={'pk': reminder.pk}),
            {'next': 'https://evil.example.com/'},
        )
        self.assertRedirects(response, reverse('pets:reminder_list'))


class ViewAndListTests(PetCareTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def test_dashboard(self):
        response = self.client.get(reverse('pets:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Шаро")
        self.assertContains(response, "Лабрадор")

    def test_pet_list_search(self):
        self.assertContains(self.client.get(reverse('pets:pet_list')), "Шаро")
        self.assertContains(
            self.client.get(reverse('pets:pet_list') + '?q=Шаро'), "Шаро"
        )
        self.assertNotContains(
            self.client.get(reverse('pets:pet_list') + '?q=НямаТаковаЖивотно'), "Лабрадор"
        )

    def test_pet_list_pagination(self):
        for i in range(15):
            Pet.objects.create(owner=self.user, name=f"Любимец {i:02d}", species='dog')

        first_page = self.client.get(reverse('pets:pet_list'))
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.context['pets']), 12)
        self.assertTrue(first_page.context['page_obj'].has_next())

        second_page = self.client.get(reverse('pets:pet_list') + '?page=2')
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(len(second_page.context['pets']), 4)
        self.assertFalse(second_page.context['page_obj'].has_next())

    def test_pet_list_pagination_preserves_filters(self):
        for i in range(15):
            Pet.objects.create(owner=self.user, name=f"Котка {i:02d}", species='cat')

        response = self.client.get(reverse('pets:pet_list') + '?species=cat')
        self.assertEqual(response.context['page_obj'].paginator.count, 15)
        query_string = response.context['filter_qs'].urlencode()
        self.assertIn('species=cat', query_string)

    def test_reminder_list_invalid_pet_filter_is_ignored(self):
        Reminder.objects.create(owner=self.user, pet=self.pet, title="X", due_date=self.today)
        response = self.client.get(reverse('pets:reminder_list') + '?pet=not-a-number')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['pet_filter'], '')
        self.assertEqual(response.context['page_obj'].paginator.count, 1)

    def test_reminder_list_status_filters(self):
        Reminder.objects.create(owner=self.user, pet=self.pet, title="overdue",
                                due_date=self.today - timedelta(days=3))
        Reminder.objects.create(owner=self.user, pet=self.pet, title="today",
                                due_date=self.today)
        Reminder.objects.create(owner=self.user, pet=self.pet, title="future",
                                due_date=self.today + timedelta(days=3))
        Reminder.objects.create(owner=self.user, pet=self.pet, title="done",
                                due_date=self.today, is_completed=True)

        counts = {}
        for status in ('overdue', 'today', 'upcoming', 'completed', 'all'):
            response = self.client.get(reverse('pets:reminder_list') + f'?status={status}')
            self.assertEqual(response.status_code, 200)
            counts[status] = response.context['page_obj'].paginator.count

        self.assertEqual(counts, {
            'overdue': 1, 'today': 1, 'upcoming': 1, 'completed': 1, 'all': 4,
        })

    def test_pet_detail_rejects_unknown_tab(self):
        response = self.client.get(
            reverse('pets:pet_detail', kwargs={'pk': self.pet.pk}) + '?tab=evil'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_tab'], 'overview')

    def test_pet_detail_accepts_known_tab(self):
        response = self.client.get(
            reverse('pets:pet_detail', kwargs={'pk': self.pet.pk}) + '?tab=vaccinations'
        )
        self.assertEqual(response.context['active_tab'], 'vaccinations')

    def test_pet_create(self):
        response = self.client.post(reverse('pets:pet_create'), {
            'name': 'Бела',
            'species': 'cat',
            'breed': 'Персийска',
            'gender': 'female',
            'is_neutered': True,
            'weight': 3.8,
            'birth_date': '2023-05-15',
            'food_diet': 'Пауч за котки',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Pet.objects.filter(name='Бела', owner=self.user).exists())

    def test_vaccination_create_with_auto_reminder(self):
        due_date = self.today + timedelta(days=365)
        response = self.client.post(
            reverse('pets:vaccination_create', kwargs={'pet_pk': self.pet.pk}), {
                'name': 'Ваксина Бяс',
                'date_administered': self.today.isoformat(),
                'next_due_date': due_date.isoformat(),
                'batch_number': 'VAC-1234',
                'clinic_or_vet': 'Клиника ЗооВет',
                'create_reminder': True,
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Vaccination.objects.filter(pet=self.pet, name='Ваксина Бяс').exists())
        self.assertTrue(Reminder.objects.filter(pet=self.pet, title__icontains='Ваксина Бяс').exists())

    def test_vaccination_create_redirects_via_reverse(self):
        response = self.client.post(
            reverse('pets:vaccination_create', kwargs={'pet_pk': self.pet.pk}), {
                'name': 'Ваксина Бяс',
                'date_administered': self.today.isoformat(),
            }
        )
        self.assertRedirects(
            response,
            f"{reverse('pets:pet_detail', kwargs={'pk': self.pet.pk})}?tab=vaccinations",
        )

    def test_pet_passport_printable_view(self):
        response = self.client.get(reverse('pets:pet_passport', kwargs={'pk': self.pet.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ЗДРАВЕН ПАСПОРТ")
        self.assertContains(response, "Шаро")
        self.assertContains(response, "123456789012345")


class ListQueryCountTests(PetCareTestMixin, TestCase):
    """Guard against N+1 regressions in the list views.

    Asserts the query count is independent of the number of rows rather than
    pinning an exact number, so unrelated changes elsewhere in a view do not
    cause false failures while a real N+1 still does.
    """

    def setUp(self):
        super().setUp()
        self.login()

    def _count_queries_for_reminder_list(self, rows):
        for i in range(rows):
            pet = Pet.objects.create(owner=self.user, name=f"Любимец {i:02d}", species='dog')
            Reminder.objects.create(
                owner=self.user, pet=pet, title=f"Напомняне {i}", due_date=self.today
            )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('pets:reminder_list'))
            # Touch the pet relation the way the template does.
            for reminder in response.context['reminders']:
                self.assertIsNotNone(reminder.pet.name)
        return len(queries)

    def test_reminder_list_query_count_is_independent_of_row_count(self):
        self.assertEqual(self._count_queries_for_reminder_list(4), self._count_queries_for_reminder_list(12))

    def test_pet_list_query_count_is_independent_of_row_count(self):
        def measure(rows):
            for i in range(rows):
                Pet.objects.create(
                    owner=self.user, name=f"Допълнителен {i:02d}", species='dog',
                    breed=f"Порода {i}",
                )
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(reverse('pets:pet_list'))
                list(response.context['pets'])
            return len(queries)

        self.assertEqual(measure(4), measure(12))

    def test_dashboard_query_count_is_independent_of_reminder_count(self):
        def measure(rows):
            for i in range(rows):
                pet = Pet.objects.create(owner=self.user, name=f"Любимец {i:02d}", species='dog')
                Reminder.objects.create(
                    owner=self.user, pet=pet, title=f"Напомняне {i}", due_date=self.today
                )
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(reverse('pets:dashboard'))
                for reminder in response.context['today_reminders']:
                    self.assertIsNotNone(reminder.pet.name)
            return len(queries)

        self.assertEqual(measure(4), measure(12))


class UserProfileSignalTests(TestCase):
    def test_profile_created_for_new_user(self):
        user = User.objects.create_user(username='siguser', password='password123')
        self.assertTrue(hasattr(user, 'profile'))

    def test_existing_profile_is_not_duplicated(self):
        user = User.objects.create_user(username='siguser2', password='password123')
        user.first_name = 'Променено'
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Променено')
        self.assertEqual(user.profile.phone, '')

    def test_profile_created_for_pre_existing_user(self):
        user = User.objects.create(username='nosignal', password='password123')
        # Re-saving must not raise and must leave exactly one profile row.
        user.save()
        self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)
