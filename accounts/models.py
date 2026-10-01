from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=30, blank=True, verbose_name="Телефон за връзка")
    city = models.CharField(max_length=100, blank=True, verbose_name="Град / Населено място")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата на регистрация")

    class Meta:
        verbose_name = "Потребителски профил"
        verbose_name_plural = "Потребителски профили"

    def __str__(self):
        return f"Профил на {self.user.get_full_name() or self.user.username}"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()
        else:
            UserProfile.objects.create(user=instance)
