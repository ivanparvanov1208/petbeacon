from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.translation import get_language, gettext_lazy
from .email_notifications import send_account_change_notification, send_email_verification
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = gettext_lazy("Допълнителна информация")
    verbose_name_plural = gettext_lazy("Допълнителна информация")


class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]

    def save_model(self, request, obj, form, change):
        obj._previous_admin_email = None
        obj._admin_user_changed = False
        if change:
            previous = User.objects.get(pk=obj.pk)
            obj._previous_admin_email = previous.email
            obj._admin_user_changed = bool(form.changed_data)
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        obj = form.instance
        profile_before = None
        if change:
            profile_before = UserProfile.objects.filter(user=obj).values(
                'role', 'phone', 'city'
            ).first()

        super().save_related(request, form, formsets, change)
        if not change:
            return

        profile, _created = UserProfile.objects.get_or_create(user=obj)
        profile_after = {
            'role': profile.role,
            'phone': profile.phone,
            'city': profile.city,
        }
        profile_changed = profile_before is not None and any(
            profile_before[field] != profile_after[field] for field in profile_after
        )
        previous_email = getattr(obj, '_previous_admin_email', None) or ''
        email_changed = previous_email.casefold() != (obj.email or '').casefold()

        if email_changed:
            profile.email_verified = False
            profile.save(update_fields=['email_verified'])
            if previous_email:
                send_account_change_notification(
                    obj, recipient=previous_email, language=get_language() or 'bg'
                )
            if obj.email:
                send_email_verification(obj, get_language() or 'bg')
            return

        if getattr(obj, '_admin_user_changed', False) or profile_changed:
            send_account_change_notification(obj, language=get_language() or 'bg')

    def get_inline_instances(self, request, obj=None):
        # The post_save signal creates the profile when a new user is saved.
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)


class UserProfileAdmin(admin.ModelAdmin):
    """The only place a role can be changed.

    ``role`` is intentionally absent from every user-facing form, so this
    admin is what grants it.
    """

    list_display = ('user', 'role', 'email_verified', 'phone', 'city', 'created_at')
    list_filter = ('role',)
    list_select_related = ('user',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email')

    def save_model(self, request, obj, form, change):
        previous = None
        if change:
            previous = UserProfile.objects.get(pk=obj.pk)
        super().save_model(request, obj, form, change)
        if change and previous and any(
            getattr(previous, field) != getattr(obj, field)
            for field in ('role', 'phone', 'city')
        ):
            send_account_change_notification(obj.user, language=get_language() or 'bg')


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
