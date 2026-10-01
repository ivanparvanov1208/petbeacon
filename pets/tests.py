from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import date, timedelta
from .models import Pet, Vaccination, MedicalRecord, Medication, VetVisit, Reminder


class PetCareTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            password="password123",
            first_name="Иван",
            last_name="Иванов"
        )
        self.today = date.today()

        # Create a test pet
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
            allergies="Пилешко месо"
        )

    def test_pet_model_properties(self):
        self.assertEqual(str(self.pet), "Шаро (Куче)")
        self.assertIn("г.", self.pet.age_display)
        self.assertIn("fa-dog", self.pet.species_icon)

    def test_anonymous_redirect(self):
        response = self.client.get(reverse('pets:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_login_and_dashboard(self):
        self.client.login(username="testuser", password="password123")
        response = self.client.get(reverse('pets:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Шаро")
        self.assertContains(response, "Лабрадор")

    def test_pet_list_and_search(self):
        self.client.login(username="testuser", password="password123")
        
        # Test full list
        response = self.client.get(reverse('pets:pet_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Шаро")

        # Test search match
        response = self.client.get(reverse('pets:pet_list') + '?q=Шаро')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Шаро")

        # Test search no match
        response = self.client.get(reverse('pets:pet_list') + '?q=НямаТаковаЖивотно')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Лабрадор")

    def test_pet_create(self):
        self.client.login(username="testuser", password="password123")
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
        self.client.login(username="testuser", password="password123")
        due_date = self.today + timedelta(days=365)
        response = self.client.post(reverse('pets:vaccination_create', kwargs={'pet_pk': self.pet.pk}), {
            'name': 'Ваксина Бяс',
            'date_administered': self.today.strftime('%Y-%m-%d'),
            'next_due_date': due_date.strftime('%Y-%m-%d'),
            'batch_number': 'VAC-1234',
            'clinic_or_vet': 'Клиника ЗооВет',
            'create_reminder': True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Vaccination.objects.filter(pet=self.pet, name='Ваксина Бяс').exists())
        self.assertTrue(Reminder.objects.filter(pet=self.pet, title__icontains='Ваксина Бяс').exists())

    def test_reminder_toggle_complete(self):
        reminder = Reminder.objects.create(
            owner=self.user,
            pet=self.pet,
            title="Годишен преглед",
            due_date=self.today,
            is_completed=False
        )
        self.client.login(username="testuser", password="password123")
        response = self.client.get(reverse('pets:reminder_toggle_complete', kwargs={'pk': reminder.pk}))
        self.assertEqual(response.status_code, 302)
        reminder.refresh_from_db()
        self.assertTrue(reminder.is_completed)
        self.assertIsNotNone(reminder.completed_at)

    def test_pet_passport_printable_view(self):
        self.client.login(username="testuser", password="password123")
        response = self.client.get(reverse('pets:pet_passport', kwargs={'pk': self.pet.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ЗДРАВЕН ПАСПОРТ")
        self.assertContains(response, "Шаро")
        self.assertContains(response, "123456789012345")
