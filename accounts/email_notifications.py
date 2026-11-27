import logging
from urllib.parse import urlencode, urljoin

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.signing import TimestampSigner
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import format as date_format
from django.utils.translation import gettext as _, override


logger = logging.getLogger(__name__)
_VERIFICATION_SALT = 'petbeacon.accounts.email-verification'


def _language(language):
    return language if language in {'bg', 'en'} else settings.LANGUAGE_CODE


def _send_branded_email(recipient, subject, template_name, context, language='bg'):
    if not recipient:
        return False

    context = {**context, 'site_url': settings.APP_BASE_URL}
    try:
        with override(_language(language)):
            text_body = render_to_string(f'emails/{template_name}.txt', context)
            html_body = render_to_string(f'emails/{template_name}.html', context)
            message = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
            )
            message.attach_alternative(html_body, 'text/html')
            message.send(fail_silently=False)
        return True
    except Exception as error:
        logger.warning(
            'PetBeacon email notification failed (%s).', type(error).__name__
        )
        return False


def send_email_verification(user, language='bg'):
    signer = TimestampSigner(salt=_VERIFICATION_SALT)
    token = signer.sign_object({'user_id': user.pk, 'email': user.email})
    path = reverse('accounts:verify_email')
    query = urlencode({'token': token})
    verify_url = urljoin(f'{settings.APP_BASE_URL}/', f'{path.lstrip("/")}?{query}')
    with override(_language(language)):
        subject = _('Verify your PetBeacon email address')
    return _send_branded_email(
        user.email,
        subject,
        'email_verification',
        {'user': user, 'verify_url': verify_url},
        language,
    )


def verify_email_token(token):
    signer = TimestampSigner(salt=_VERIFICATION_SALT)
    payload = signer.unsign_object(
        token, max_age=getattr(settings, 'EMAIL_VERIFICATION_MAX_AGE', 86400)
    )
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.get(pk=payload['user_id'], email=payload['email'])


def send_login_notification(user, language='bg'):
    with override(_language(language)):
        subject = _('New sign-in to your PetBeacon account')
        login_time = date_format(timezone.localtime(), 'DATETIME_FORMAT')
    return _send_branded_email(
        user.email,
        subject,
        'account_login_notification',
        {'user': user, 'login_time': login_time},
        language,
    )


def send_account_change_notification(user, recipient=None, language='bg'):
    with override(_language(language)):
        subject = _('PetBeacon account information was updated')
        changed_at = date_format(timezone.localtime(), 'DATETIME_FORMAT')
    return _send_branded_email(
        recipient if recipient is not None else user.email,
        subject,
        'account_change_notification',
        {'user': user, 'changed_at': changed_at},
        language,
    )


