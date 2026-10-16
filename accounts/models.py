from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy


class UserProfile(models.Model):
    # Role labels are lazy so they resolve per request language. The stored value
    # is always the code on the left, never the label, so switching language
    # never touches existing rows.
    ROLE_OWNER = 'owner'
    ROLE_VET = 'vet'

    ROLE_CHOICES = [
        (ROLE_OWNER, gettext_lazy("Стопанин")),
        (ROLE_VET, gettext_lazy("Ветеринар")),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default=ROLE_OWNER,
        verbose_name=gettext_lazy("Роля"),
        help_text=gettext_lazy("Стопанин управлява любимците си, Ветеринар работи с медицинските им записи."),
    )
    phone = models.CharField(max_length=30, blank=True, verbose_name=gettext_lazy("Телефон за връзка"))
    city = models.CharField(max_length=100, blank=True, verbose_name=gettext_lazy("Град / Населено място"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=gettext_lazy("Дата на регистрация"))

    class Meta:
        verbose_name = gettext_lazy("Потребителски профил")
        verbose_name_plural = gettext_lazy("Потребителски профили")

    def __str__(self):
        return _("Профил на %(name)s") % {"name": self.user.get_full_name() or self.user.username}

    @property
    def is_vet(self):
        return self.role == self.ROLE_VET

    @property
    def is_owner(self):
        return self.role == self.ROLE_OWNER


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Guarantee a profile row exists for every user.

    Uses ``get_or_create`` and never touches existing rows: ``User.save()`` runs
    on every login (``update_last_login``), and an unconditional write here
    turned each sign-in into an extra UPDATE against the profile table.
    """
    UserProfile.objects.get_or_create(user=instance)
