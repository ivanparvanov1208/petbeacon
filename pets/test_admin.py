from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Pet, Reminder


class PetAdminInlineTests(TestCase):
    """Regression: saving a Pet with an inline Reminder raised ValidationError.

    ``Reminder.owner`` is a non-nullable FK to ``User`` and had no field in the
    inline form, so every inline save attempted to write ``owner = NULL``.
    """

    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin', password='password123', email='admin@example.com'
        )
        self.client.login(username='admin', password='password123')

    def test_pet_change_page_loads(self):
        pet = Pet.objects.create(owner=self.admin_user, name='Шаро', species='dog')
        response = self.client.get(
            reverse('admin:pets_pet_change', kwargs={'object_id': pet.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_creating_pet_with_inline_reminder_assigns_owner(self):
        response = self.client.post(reverse('admin:pets_pet_add'), {
            'name': 'Бела',
            'species': 'cat',
            'gender': 'unknown',
            'owner': self.admin_user.pk,
            'food_diet': '',
            'allergies': '',
            'special_notes': '',
            'birth_date_0': '',
            'birth_date_1': '',
            # Inline prefixes: vaccinations / medical records / medications /
            # vet visits / reminders.
            'vaccinations-TOTAL_FORMS': '0',
            'vaccinations-INITIAL_FORMS': '0',
            'vaccinations-MIN_NUM_FORMS': '0',
            'vaccinations-MAX_NUM_FORMS': '1000',
            'medical_records-TOTAL_FORMS': '0',
            'medical_records-INITIAL_FORMS': '0',
            'medical_records-MIN_NUM_FORMS': '0',
            'medical_records-MAX_NUM_FORMS': '1000',
            'medications-TOTAL_FORMS': '0',
            'medications-INITIAL_FORMS': '0',
            'medications-MIN_NUM_FORMS': '0',
            'medications-MAX_NUM_FORMS': '1000',
            'vet_visits-TOTAL_FORMS': '0',
            'vet_visits-INITIAL_FORMS': '0',
            'vet_visits-MIN_NUM_FORMS': '0',
            'vet_visits-MAX_NUM_FORMS': '1000',
            'reminders-TOTAL_FORMS': '1',
            'reminders-INITIAL_FORMS': '0',
            'reminders-MIN_NUM_FORMS': '0',
            'reminders-MAX_NUM_FORMS': '1000',
            'reminders-0-reminder_type': 'vaccination',
            'reminders-0-title': 'Ваксинация',
            'reminders-0-due_date': '2030-01-01',
            'reminders-0-due_time': '09:00',
            'reminders-0-priority': 'normal',
            'reminders-0-notes': '',
            'reminders-0-pet': '',
            '_save': 'Запази',
        })

        self.assertEqual(response.status_code, 302, response.context['errors'] if response.status_code == 200 else '')
        pet = Pet.objects.get(name='Бела')
        reminder = Reminder.objects.get(title='Ваксинация')
        self.assertEqual(reminder.pet, pet)
        self.assertEqual(reminder.owner, self.admin_user)
