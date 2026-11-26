from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from pets.models import Pet, Reminder


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    EMAIL_HOST='smtp.test.invalid',
    EMAIL_PORT=587,
    EMAIL_USE_TLS=True,
    EMAIL_USE_SSL=False,
    EMAIL_HOST_USER='petbeacon@test.invalid',
    EMAIL_HOST_PASSWORD='test-only-password',
    DEFAULT_FROM_EMAIL='PetBeacon <petbeacon@test.invalid>',
    REMINDER_EMAIL_LEAD_HOURS=24,
    APP_BASE_URL='https://petbeacon.test',
)
class ReminderNotificationCommandTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='reminder-owner',
            password='test-password-123',
            email='owner@example.test',
        )
        self.pet = Pet.objects.create(owner=self.owner, name='Milo', species='dog')
        self.today = timezone.localtime().date()
        self.now = timezone.make_aware(
            datetime.combine(self.today, time(8, 0)), timezone.get_current_timezone()
        )

    def make_reminder(self, **overrides):
        values = {
            'owner': self.owner,
            'pet': self.pet,
            'title': 'Annual check-up',
            'reminder_type': 'vet_visit',
            'due_date': self.today + timedelta(days=1),
            'due_time': time(8, 0),
            'language': 'en',
        }
        values.update(overrides)
        return Reminder.objects.create(**values)

    def run_command_at_fixed_time(self):
        with patch(
            'pets.management.commands.send_reminder_notifications.timezone.localtime',
            return_value=self.now,
        ):
            call_command('send_reminder_notifications', verbosity=0)

    def test_sends_html_and_plain_email_once_for_reminder_in_window(self):
        reminder = self.make_reminder()

        self.run_command_at_fixed_time()

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['owner@example.test'])
        self.assertEqual(message.from_email, 'PetBeacon <petbeacon@test.invalid>')
        self.assertIn('Annual check-up', message.subject)
        self.assertEqual(len(message.alternatives), 1)
        self.assertEqual(message.alternatives[0][1], 'text/html')
        self.assertIn('Milo', message.body)
        self.assertIn('Milo', message.alternatives[0][0])
        self.assertIn('https://petbeacon.test/', message.alternatives[0][0])

        reminder.refresh_from_db()
        self.assertIsNotNone(reminder.email_notification_sent_at)

        self.run_command_at_fixed_time()
        self.assertEqual(len(mail.outbox), 1)

    def test_uses_nine_am_when_reminder_has_no_time(self):
        reminder = self.make_reminder(due_date=self.today, due_time=None)

        self.run_command_at_fixed_time()

        self.assertEqual(len(mail.outbox), 1)
        reminder.refresh_from_db()
        self.assertIsNotNone(reminder.email_notification_sent_at)

    def test_skips_disabled_completed_and_out_of_window_reminders(self):
        disabled = self.make_reminder(title='Disabled', email_notification_enabled=False)
        completed = self.make_reminder(title='Completed', is_completed=True)
        outside_window = self.make_reminder(
            title='Outside window', due_time=time(9, 0)
        )
        no_email_owner = User.objects.create_user(username='no-email-owner')
        no_email_pet = Pet.objects.create(owner=no_email_owner, name='No mail')
        no_email = self.make_reminder(
            owner=no_email_owner,
            pet=no_email_pet,
            title='No email address',
        )

        self.run_command_at_fixed_time()

        self.assertEqual(mail.outbox, [])
        for reminder in (disabled, completed, outside_window, no_email):
            reminder.refresh_from_db()
            self.assertIsNone(reminder.email_notification_sent_at)

    def test_skips_due_time_that_has_already_passed_today(self):
        reminder = self.make_reminder(due_date=self.today, due_time=time(7, 59))

        self.run_command_at_fixed_time()

        self.assertEqual(mail.outbox, [])
        reminder.refresh_from_db()
        self.assertIsNone(reminder.email_notification_sent_at)

    @override_settings(EMAIL_HOST='', EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD='')
    def test_fails_clearly_when_smtp_settings_are_missing(self):
        with self.assertRaisesMessage(CommandError, 'Configure EMAIL_HOST'):
            call_command('send_reminder_notifications', verbosity=0)
        self.assertEqual(mail.outbox, [])

    @override_settings(EMAIL_USE_TLS=True, EMAIL_USE_SSL=True)
    def test_rejects_enabling_starttls_and_ssl_together(self):
        with self.assertRaisesMessage(CommandError, 'not both'):
            call_command('send_reminder_notifications', verbosity=0)
        self.assertEqual(mail.outbox, [])


class MobileReminderFeedTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='mobile-owner')
        self.other_owner = User.objects.create_user(username='mobile-other-owner')
        self.pet = Pet.objects.create(owner=self.owner, name='Milo', species='dog')
        self.feed_url = reverse('pets:mobile_reminders_feed')
        self.now = timezone.localtime()

    def test_feed_contains_only_the_signed_in_owners_future_pending_reminders(self):
        due_date = self.now.date() + timedelta(days=1)
        own_reminder = Reminder.objects.create(
            owner=self.owner,
            pet=self.pet,
            title='Upcoming check-up',
            due_date=due_date,
            due_time=time(9, 30),
        )
        Reminder.objects.create(
            owner=self.owner,
            title='Completed',
            due_date=due_date,
            due_time=time(10, 0),
            is_completed=True,
        )
        Reminder.objects.create(
            owner=self.owner,
            title='Past',
            due_date=self.now.date() - timedelta(days=1),
        )
        Reminder.objects.create(
            owner=self.other_owner,
            title='Another account',
            due_date=due_date,
            due_time=time(9, 30),
        )
        self.client.force_login(self.owner)

        response = self.client.get(self.feed_url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['accountId'], self.owner.pk)
        self.assertEqual([item['id'] for item in payload['reminders']], [own_reminder.pk])
        item = payload['reminders'][0]
        self.assertEqual(item['title'], own_reminder.title)
        expected_due_at = timezone.make_aware(
            datetime.combine(own_reminder.due_date, own_reminder.due_time),
            timezone.get_current_timezone(),
        )
        self.assertEqual(item['dueAt'], int(expected_due_at.timestamp() * 1000))
        self.assertTrue(item['body'])
        self.assertTrue(item['url'].endswith(reverse('pets:reminder_list')))

    def test_feed_requires_an_authenticated_user(self):
        response = self.client.get(self.feed_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)
