# Generated for PetBeacon reminder delivery preferences and veterinarian reviews.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('pets', '0003_consultation_consultationmessage_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='reminder',
            name='email_notification_enabled',
            field=models.BooleanField(default=True, verbose_name='Изпрати напомняне по имейл'),
        ),
        migrations.AddField(
            model_name='reminder',
            name='email_notification_sent_at',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='reminder',
            name='language',
            field=models.CharField(
                choices=[('bg', 'Български'), ('en', 'English')],
                default='bg',
                max_length=2,
                verbose_name='Език на известието',
            ),
        ),
        migrations.CreateModel(
            name='VetReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')], verbose_name='Оценка')),
                ('comment', models.TextField(blank=True, max_length=2000, verbose_name='Коментар')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('consultation', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='review', to='pets.consultation')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vet_reviews_written', to=settings.AUTH_USER_MODEL)),
                ('veterinarian', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vet_reviews_received', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Отзив за ветеринар',
                'verbose_name_plural': 'Отзиви за ветеринари',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='vetreview',
            constraint=models.CheckConstraint(
                condition=models.Q(('rating__gte', 1), ('rating__lte', 5)),
                name='vet_review_rating_1_to_5',
            ),
        ),
    ]
