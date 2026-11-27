import hashlib

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _, get_language
from django.utils.translation import ngettext
from django.conf import settings
from django.views.decorators.http import require_POST

from .email_notifications import (
    send_email_verification,
    send_login_notification,
    verify_email_token,
)
from .forms import (
    EmailVerificationResendForm,
    UserRegistrationForm,
    UserLoginForm,
    UserProfileUpdateForm,
)
from .models import UserProfile


# Cache-based counters persist across browser sessions and cleared cookies.
_MAX_ATTEMPTS = getattr(settings, 'LOGIN_MAX_ATTEMPTS', 5)
_LOCKOUT_SECONDS = getattr(settings, 'LOGIN_LOCKOUT_SECONDS', 300)
_ATTEMPTS_PREFIX = 'login-fail:'
_LOCKOUT_PREFIX = 'login-lockout:'


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _throttle_keys(request, username):
    ip = _client_ip(request)
    username = (username or '').strip().lower()
    base = f"{_ATTEMPTS_PREFIX}{ip}"
    return base, f"{base}:{username}", f"{_LOCKOUT_PREFIX}{ip}", f"{_LOCKOUT_PREFIX}{ip}:{username}"


def _is_locked_out(request, username=''):
    ip_attempts_key, user_attempts_key, ip_lock_key, user_lock_key = _throttle_keys(request, username)

    for lock_key in (user_lock_key, ip_lock_key):
        remaining = cache.get(lock_key)
        if remaining:
            return True, int(remaining)

    attempts = max(
        cache.get(ip_attempts_key, 0),
        cache.get(user_attempts_key, 0),
    )
    if attempts >= _MAX_ATTEMPTS:
        cache.set(ip_lock_key, _LOCKOUT_SECONDS, _LOCKOUT_SECONDS)
        cache.set(user_lock_key, _LOCKOUT_SECONDS, _LOCKOUT_SECONDS)
        return True, _LOCKOUT_SECONDS

    return False, 0


def _record_failed_attempt(request, username=''):
    ip_attempts_key, user_attempts_key, ip_lock_key, user_lock_key = _throttle_keys(request, username)
    cache.set(ip_attempts_key, cache.get(ip_attempts_key, 0) + 1, _LOCKOUT_SECONDS)
    cache.set(user_attempts_key, cache.get(user_attempts_key, 0) + 1, _LOCKOUT_SECONDS)

    if max(cache.get(ip_attempts_key, 0), cache.get(user_attempts_key, 0)) >= _MAX_ATTEMPTS:
        cache.set(ip_lock_key, _LOCKOUT_SECONDS, _LOCKOUT_SECONDS)
        cache.set(user_lock_key, _LOCKOUT_SECONDS, _LOCKOUT_SECONDS)


def _clear_login_attempts(request, username=''):
    ip_attempts, user_attempts, ip_lock, user_lock = _throttle_keys(request, username)
    for key in (ip_attempts, user_attempts, ip_lock, user_lock):
        cache.delete(key)


def register_view(request):
    if request.user.is_authenticated:
        return redirect('pets:dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()

            # The post_save signal creates the profile; only an admin assigns vet access.
            profile = UserProfile.objects.get_or_create(user=user)[0]
            profile.phone = form.cleaned_data.get('phone', '')
            profile.city = form.cleaned_data.get('city', '')
            profile.email_verified = False
            profile.save(update_fields=['phone', 'city', 'email_verified'])

            email_sent = send_email_verification(user, get_language() or 'bg')
            return render(request, 'accounts/email_verification_pending.html', {
                'email': user.email,
                'email_sent': email_sent,
            })
        else:
            messages.error(request, _("Моля, проверете въведените данни в полетата по-долу."))
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('pets:dashboard')

    username = request.POST.get('username', '')

    locked, remaining = _is_locked_out(request, username)
    if locked:
        minutes = remaining // 60
        seconds = remaining % 60
        messages.error(
            request,
            _("Твърде много неуспешни опити за вход. Моля, изчакайте %(minutes)dм %(seconds)dс и опитайте отново.")
            % {"minutes": minutes, "seconds": seconds},
        )
        return render(request, 'accounts/login.html', {
            'form': UserLoginForm(request, data=request.POST or None),
            'locked_out': True,
            'remaining_seconds': remaining,
        })

    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            profile, _created = UserProfile.objects.get_or_create(user=user)
            if not profile.email_verified:
                messages.error(
                    request,
                    _("Потвърдете имейл адреса си, преди да влезете в профила."),
                )
                return redirect('accounts:resend_email_verification')
            _clear_login_attempts(request, username)
            login(request, user)
            send_login_notification(user, get_language() or 'bg')
            messages.success(
                request,
                _("Здравейте отново, %(name)s!") % {"name": user.first_name or user.username},
            )

            next_url = request.POST.get('next') or request.GET.get('next', '')
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect('pets:dashboard')
        else:
            _record_failed_attempt(request, username)
            still_locked, lockout_seconds = _is_locked_out(request, username)
            if still_locked:
                messages.error(
                    request,
                    _("Профилът е временно заключен за %(minutes)d минути поради твърде много неуспешни опити.")
                    % {"minutes": _LOCKOUT_SECONDS // 60},
                )
            else:
                remaining_attempts = max(0, _MAX_ATTEMPTS - cache.get(
                    f"{_ATTEMPTS_PREFIX}{_client_ip(request)}", 0
                ))
                messages.error(
                    request,
                    ngettext(
                        "Грешно потребителско име или парола. Остава ви %(count)d опит.",
                        "Грешно потребителско име или парола. Остават ви %(count)d опита.",
                        remaining_attempts,
                    ) % {"count": remaining_attempts},
                )
    else:
        form = UserLoginForm(request)

    return render(request, 'accounts/login.html', {'form': form})


def verify_email_view(request):
    token = request.GET.get('token', '')
    try:
        user = verify_email_token(token)
    except (BadSignature, SignatureExpired, User.DoesNotExist, KeyError, TypeError, ValueError):
        messages.error(request, _("Връзката за потвърждение е невалидна или е изтекла."))
        return redirect('accounts:resend_email_verification')

    profile, _created = UserProfile.objects.get_or_create(user=user)
    if not profile.email_verified:
        profile.email_verified = True
        profile.save(update_fields=['email_verified'])
        messages.success(request, _("Имейл адресът ви е потвърден. Вече можете да влезете."))
    else:
        messages.info(request, _("Имейл адресът ви вече е потвърден."))
    return redirect('accounts:login')


def resend_email_verification_view(request):
    if request.method == 'POST':
        form = EmailVerificationResendForm(request.POST)
        if form.is_valid():
            user = User.objects.filter(
                email__iexact=form.cleaned_data['email'], is_active=True
            ).first()
            if user:
                profile, _created = UserProfile.objects.get_or_create(user=user)
                normalized_email = form.cleaned_data['email'].strip().casefold()
                email_key = hashlib.sha256(normalized_email.encode('utf-8')).hexdigest()
                may_send = cache.add(
                    f'email-verification-resend:{email_key}', True, 60
                )
                if not profile.email_verified and may_send:
                    send_email_verification(user, get_language() or 'bg')
            # Keep the response the same whether the account exists or not.
            messages.success(
                request,
                _("Ако има непотвърден профил с този адрес, ще получите имейл с инструкции."),
            )
            return redirect('accounts:login')
    else:
        form = EmailVerificationResendForm(initial={
            'email': request.GET.get('email', ''),
        })
    return render(request, 'accounts/resend_email_verification.html', {'form': form})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, _("Успешно излязохте от профила си. Очакваме ви отново!"))
    return redirect('pets:home')


@login_required
def profile_view(request):
    # Keep this variable name distinct from the gettext alias `_` used below.
    profile, _profile_created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            profile.phone = form.cleaned_data.get('phone', '')
            profile.city = form.cleaned_data.get('city', '')
            profile.save()
            messages.success(request, _("Данните на вашия профил бяха обновени успешно!"))
            return redirect('accounts:profile')
    else:
        form = UserProfileUpdateForm(instance=request.user, initial={
            'phone': profile.phone,
            'city': profile.city,
        })

    return render(request, 'accounts/profile.html', {
        'form': form,
        'profile': profile,
    })
