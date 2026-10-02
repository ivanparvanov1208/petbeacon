from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from .forms import UserProfileUpdateForm, UserRegistrationForm
from .models import UserProfile


def registration_payload(**overrides):
    payload = {
        'username': 'newuser',
        'first_name': 'Иван',
        'last_name': 'Иванов',
        'email': 'ivan@example.com',
        'password': 'Str0ng-Passphrase!42',
        'password_confirm': 'Str0ng-Passphrase!42',
    }
    payload.update(overrides)
    return payload


class UserProfileModelTests(TestCase):
    def test_profile_created_automatically(self):
        user = User.objects.create_user(username='auto', password='password123')
        self.assertIsInstance(user.profile, UserProfile)

    def test_saving_user_again_does_not_duplicate_profile(self):
        user = User.objects.create_user(username='auto2', password='password123')
        user.last_login = None
        user.save()
        self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)


class RegistrationFormTests(TestCase):
    def test_valid_registration(self):
        form = UserRegistrationForm(data=registration_payload())
        self.assertTrue(form.is_valid(), form.errors)

    def test_mismatched_passwords(self):
        form = UserRegistrationForm(data=registration_payload(password_confirm='Other-Pass-1'))
        self.assertFalse(form.is_valid())
        self.assertIn('password_confirm', form.errors)

    def test_weak_password_is_rejected(self):
        """Regression: AUTH_PASSWORD_VALIDATORS were never applied."""
        form = UserRegistrationForm(data=registration_payload(
            password='password',
            password_confirm='password',
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_numeric_only_password_is_rejected(self):
        form = UserRegistrationForm(data=registration_payload(
            password='9182736450',
            password_confirm='9182736450',
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_password_similar_to_username_is_rejected(self):
        form = UserRegistrationForm(data=registration_payload(
            username='petlover123',
            password='petlover123!',
            password_confirm='petlover123!',
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_duplicate_email_is_rejected_case_insensitively(self):
        User.objects.create_user(
            username='existing', password='password123', email='Ivan@Example.com'
        )
        form = UserRegistrationForm(data=registration_payload(email='ivan@example.com'))
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_duplicate_username_is_rejected_case_insensitively(self):
        User.objects.create_user(username='newuser', password='password123')
        form = UserRegistrationForm(data=registration_payload(username='NEWUSER'))
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)


class ProfileUpdateFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='me', password='password123', email='me@example.com'
        )

    def test_email_may_stay_the_same(self):
        form = UserProfileUpdateForm(
            data={'first_name': 'Иван', 'last_name': 'Иванов', 'email': 'me@example.com'},
            instance=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_email_cannot_be_taken_by_another_user(self):
        User.objects.create_user(username='other', password='password123', email='other@example.com')
        form = UserProfileUpdateForm(
            data={'first_name': 'Иван', 'last_name': 'Иванов', 'email': 'other@example.com'},
            instance=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


class RegistrationViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_registration_creates_user_and_logs_in(self):
        response = self.client.post(reverse('accounts:register'), registration_payload())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())
        self.assertTrue(self.client.session.get('_auth_user_id'))

    def test_weak_password_is_rejected_end_to_end(self):
        response = self.client.post(reverse('accounts:register'), registration_payload(
            password='12345', password_confirm='12345',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='newuser').exists())

    def test_profile_fields_are_saved(self):
        self.client.post(reverse('accounts:register'), registration_payload(
            phone='+359 88 123 4567', city='София',
        ))
        profile = UserProfile.objects.get(user__username='newuser')
        self.assertEqual(profile.phone, '+359 88 123 4567')
        self.assertEqual(profile.city, 'София')


class LoginRateLimitTests(TestCase):
    """The counter must live in the cache, not the session.

    A session-scoped counter is reset simply by dropping cookies, which is what
    a credential-stuffing client would do on every request.
    """

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(username='victim', password='password123')
        self.url = reverse('accounts:login')
        self.max_attempts = 5

    def attempt(self, username='victim', password='wrong'):
        return self.client.post(self.url, {'username': username, 'password': password})

    def test_lockout_after_threshold(self):
        for _ in range(self.max_attempts - 1):
            self.attempt()
        self.assertEqual(self.attempt().status_code, 200)

        # Threshold reached — the next attempt is refused before authentication.
        response = self.attempt()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['locked_out'])

    def test_lockout_survives_losing_the_session_cookie(self):
        for _ in range(self.max_attempts):
            self.attempt()

        # Simulate an attacker dropping cookies to reset a session counter.
        self.client.cookies.clear()

        response = self.attempt()
        self.assertTrue(response.context['locked_out'])
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_correct_password_still_works_before_threshold(self):
        self.attempt()
        self.attempt()
        response = self.client.post(self.url, {
            'username': 'victim', 'password': 'password123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_successful_login_clears_counters(self):
        for _ in range(self.max_attempts - 1):
            self.attempt()
        self.client.post(self.url, {'username': 'victim', 'password': 'password123'})
        self.assertNotIn('login_attempts', str(cache._cache))

        # A later wrong attempt must not be treated as attempt #5.
        self.attempt()
        response = self.client.post(self.url, {
            'username': 'victim', 'password': 'password123',
        })
        self.assertEqual(response.status_code, 302)

    def test_open_redirect_is_blocked(self):
        response = self.client.post(
            self.url + '?next=https://evil.example.com/',
            {'username': 'victim', 'password': 'password123'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('pets:dashboard'))

    def test_safe_next_url_is_honoured(self):
        response = self.client.post(
            self.url + f'?next={reverse("pets:pet_list")}',
            {'username': 'victim', 'password': 'password123'},
        )
        self.assertRedirects(response, reverse('pets:pet_list'))


class LogoutTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='outuser', password='password123')
        self.client = Client()

    def test_logout_requires_post(self):
        self.client.login(username='outuser', password='password123')
        response = self.client.get(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)

    def test_logout_via_post(self):
        self.client.login(username='outuser', password='password123')
        response = self.client.post(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)
