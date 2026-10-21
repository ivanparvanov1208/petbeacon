"""
URL configuration for PetBeacon project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.utils.translation import gettext_lazy as _


admin.site.site_header = _("PetBeacon Администрация")
admin.site.site_title = _("PetBeacon Портал")
admin.site.index_title = _("Управление на база данни за домашни любимци")

urlpatterns = [

    path('i18n/', include('django.conf.urls.i18n')),


    path('admin/', admin.site.urls),
]


urlpatterns += i18n_patterns(
    path('auth/', include('accounts.urls')),
    path('', include('pets.urls')),
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')
