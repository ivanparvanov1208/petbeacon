from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.utils.http import url_has_allowed_host_and_scheme
from django.conf import settings
from django.views.decorators.http import require_POST

from .forms import UserRegistrationForm, UserLoginForm, UserProfileUpdateForm
from .models import UserProfile


# ---------------------------------------------------------------------------
# Login Rate Limiting
#
# Tracked in the cache (keyed by client IP *and* submitted username) instead of
# the session, because a session-scoped counter is reset simply by clearing
# cookies — which is exactly what a credential-stuffing script would do.
# ---------------------------------------------------------------------------
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
    """Return ``(locked, remaining_seconds)`` for the given client/username."""
    ip_attempts_key, user_attempts_key, ip_lock_key, user_lock_key = _throttle_keys(request, username)

    # Lock the narrowest scope first so legitimate users are not affected by
    # someone else hammering a different account from the same NAT address.
    for lock_key in (user_lock_key, ip_lock_key):
        remaining = cache.get(lock_key)
        if remaining:
            return True, int(remaining)

    # ``max`` (not sum) so a single client/username pair is not counted twice.
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
    """Increment the failure counters and lock once the threshold is reached."""
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


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def register_view(request):
    if request.user.is_authenticated:
        return redirect('pets:dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()

            # UserProfile is created by the post_save signal in accounts.models
            profile = UserProfile.objects.get_or_create(user=user)[0]
            profile.phone = form.cleaned_data.get('phone', '')
            profile.city = form.cleaned_data.get('city', '')
            profile.save()

            login(request, user)
            messages.success(
                request,
                f"Добре дошли в PetCare, {user.first_name or user.username}! "
                "Вашият профил бе създаден успешно."
            )
            return redirect('pets:dashboard')
        else:
            messages.error(request, "Моля, проверете въведените данни в полетата по-долу.")
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('pets:dashboard')

    username = request.POST.get('username', '')

    # Check rate limiting
    locked, remaining = _is_locked_out(request, username)
    if locked:
        minutes = remaining // 60
        seconds = remaining % 60
        messages.error(
            request,
            f"Твърде много неуспешни опити за вход. "
            f"Моля, изчакайте {minutes}м {seconds}с и опитайте отново."
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
            _clear_login_attempts(request, username)
            login(request, user)
            messages.success(request, f"Здравейте отново, {user.first_name or user.username}!")

            # Safe redirect — prevent open redirect attacks
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
                    f"Профилът е временно заключен за {_LOCKOUT_SECONDS // 60} минути "
                    "поради твърде много неуспешни опити."
                )
            else:
                remaining_attempts = max(0, _MAX_ATTEMPTS - cache.get(
                    f"{_ATTEMPTS_PREFIX}{_client_ip(request)}", 0
                ))
                messages.error(
                    request,
                    f"Грешно потребителско име или парола. "
                    f"Остават ви {remaining_attempts} опит(а)."
                )
    else:
        form = UserLoginForm(request)

    return render(request, 'accounts/login.html', {'form': form})


@require_POST
def logout_view(request):
    """Logout MUST be POST to prevent CSRF-based logout attacks."""
    logout(request)
    messages.info(request, "Успешно излязохте от профила си. Очакваме ви отново!")
    return redirect('pets:home')


@login_required
def profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            profile.phone = form.cleaned_data.get('phone', '')
            profile.city = form.cleaned_data.get('city', '')
            profile.save()
            messages.success(request, "Данните на вашия профил бяха обновени успешно!")
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
