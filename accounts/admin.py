from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = gettext_lazy("Допълнителна информация")
    verbose_name_plural = gettext_lazy("Допълнителна информация")


class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]

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

    list_display = ('user', 'role', 'phone', 'city', 'created_at')
    list_filter = ('role',)
    list_select_related = ('user',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email')


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
