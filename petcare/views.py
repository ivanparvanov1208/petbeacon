from django.conf import settings
from django.http import HttpResponseServerError
from django.middleware.csrf import get_token
from django.template.loader import get_template
from django.urls import reverse
from django.utils import translation


def server_error(request):
    context = {
        'csrf_token': get_token(request),
        'home_url': reverse('pets:home'),
        'LANGUAGES': settings.LANGUAGES,
        'CURRENT_LANGUAGE': translation.get_language(),
    }
    return HttpResponseServerError(get_template('500.html').render(context))
