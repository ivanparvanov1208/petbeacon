"""
URL configuration for VetLink project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.utils.translation import gettext_lazy as _

# Customize Django Admin site header
admin.site.site_header = _("VetLink Администрация")
admin.site.site_title = _("VetLink Портал")
admin.site.index_title = _("Управление на база данни за домашни любимци")

urlpatterns = [
    # The language switcher posts here, so it must stay outside i18n_patterns.
    path('i18n/', include('django.conf.urls.i18n')),
    # Admin is deliberately unprefixed: it is its own translation domain and
    # follows whatever language the session is already in.
    path('admin/', admin.site.urls),
]

# The rest of the site is mounted under i18n_patterns so every URL carries its
# language prefix (/bg/..., /en/...). That keeps a shared link unambiguous and
# makes the current language visible in the address bar. It also lets Django's
# `set_language` view map the current page onto its equivalent in the new
# language when it redirects back.
urlpatterns += i18n_patterns(
    path('auth/', include('accounts.urls')),
    path('', include('pets.urls')),
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Serve from the project's static/ directory, not STATIC_ROOT — the latter
    # only exists after `collectstatic` and is empty during development.
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')
