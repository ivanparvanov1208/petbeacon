from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from pets.models import Consultation, Pet, VetReview


class VetReviewViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='review-owner', password='test-password-123'
        )
        self.veterinarian = User.objects.create_user(
            username='review-vet', password='test-password-123'
        )
        self.veterinarian.profile.role = UserProfile.ROLE_VET
        self.veterinarian.profile.save(update_fields=['role'])
        self.pet = Pet.objects.create(owner=self.owner, name='Luna', species='cat')
        self.consultation = Consultation.objects.create(
            owner=self.owner,
            veterinarian=self.veterinarian,
            pet=self.pet,
            subject='Follow-up',
            initial_message='A question about recovery.',
            status=Consultation.STATUS_CLOSED,
        )
        self.review_url = reverse(
            'pets:consultation_review', kwargs={'pk': self.consultation.pk}
        )
        self.client.force_login(self.owner)

    def test_owner_can_review_veterinarian_after_consultation_closes(self):
        response = self.client.post(
            self.review_url, {'rating': '5', 'comment': 'Very helpful.'}
        )

        self.assertRedirects(
            response,
            reverse('pets:consultation_detail', kwargs={'pk': self.consultation.pk}),
            fetch_redirect_response=False,
        )
        review = VetReview.objects.get(consultation=self.consultation)
        self.assertEqual(review.owner, self.owner)
        self.assertEqual(review.veterinarian, self.veterinarian)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, 'Very helpful.')

    def test_owner_can_edit_existing_review_without_creating_another(self):
        review = VetReview.objects.create(
            consultation=self.consultation,
            owner=self.owner,
            veterinarian=self.veterinarian,
            rating=3,
            comment='It was okay.',
        )

        self.client.post(self.review_url, {'rating': '4', 'comment': 'Better now.'})

        self.assertEqual(VetReview.objects.count(), 1)
        review.refresh_from_db()
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.comment, 'Better now.')

    def test_review_is_rejected_until_consultation_is_closed(self):
        self.consultation.status = Consultation.STATUS_OPEN
        self.consultation.save(update_fields=['status'])

        response = self.client.post(self.review_url, {'rating': '5', 'comment': 'Good.'})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(VetReview.objects.exists())

    def test_invalid_rating_is_not_saved(self):
        response = self.client.post(
            self.review_url, {'rating': '6', 'comment': 'Invalid rating.'}
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(VetReview.objects.exists())

    def test_only_consultation_owner_can_submit_review(self):
        self.client.force_login(self.veterinarian)
        response = self.client.post(self.review_url, {'rating': '5', 'comment': ''})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(VetReview.objects.exists())

        outsider = User.objects.create_user(
            username='review-outsider', password='test-password-123'
        )
        self.client.force_login(outsider)
        response = self.client.post(self.review_url, {'rating': '5', 'comment': ''})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(VetReview.objects.exists())

    def test_review_endpoint_rejects_get(self):
        response = self.client.get(self.review_url)
        self.assertEqual(response.status_code, 405)

    def test_veterinarian_reviews_page_shows_received_rating_average(self):
        VetReview.objects.create(
            consultation=self.consultation,
            owner=self.owner,
            veterinarian=self.veterinarian,
            rating=4,
            comment='Helpful advice.',
        )

        response = self.client.get(
            reverse('pets:vet_reviews', kwargs={'vet_pk': self.veterinarian.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['veterinarian'].review_count, 1)
        self.assertEqual(float(response.context['veterinarian'].review_average), 4.0)
        self.assertEqual(list(response.context['reviews']), [VetReview.objects.get()])


