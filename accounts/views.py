from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from django.conf import settings
from django.utils import timezone
from django.views.decorators.http import require_POST
import datetime

from .forms import UserRegistrationForm, UserLoginForm, UserProfileUpdateForm
from .models import UserProfile


# ---------------------------------------------------------------------------
# Login Rate Limiting Helpers (session-based, no extra package required)
# ---------------------------------------------------------------------------
_MAX_ATTEMPTS = getattr(settings, 'LOGIN_MAX_ATTEMPTS', 5)
_LOCKOUT_SECONDS = getattr(settings, 'LOGIN_LOCKOUT_SECONDS', 300)


def _is_locked_out(request):
    """Return True and remaining seconds if the session is in lockout period."""
    attempts = request.session.get('login_attempts', 0)
    lockout_until = request.session.get('login_lockout_until')

    if lockout_until:
        lockout_until_dt = datetime.datetime.fromisoformat(lockout_until)
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        if now < lockout_until_dt:
            remaining = int((lockout_until_dt - now).total_seconds())
            return True, remaining

    return False, 0


def _record_failed_attempt(request):
    """Increment failed attempts and set lockout if threshold reached."""
    attempts = request.session.get('login_attempts', 0) + 1
    request.session['login_attempts'] = attempts

    if attempts >= _MAX_ATTEMPTS:
        lockout_until = (
            datetime.datetime.now(tz=datetime.timezone.utc)
            + datetime.timedelta(seconds=_LOCKOUT_SECONDS)
        )
        request.session['login_lockout_until'] = lockout_until.isoformat()


def _clear_login_attempts(request):
    request.session.pop('login_attempts', None)
    request.session.pop('login_lockout_until', None)


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

            profile, _ = UserProfile.objects.get_or_create(user=user)
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

    # Check rate limiting
    locked, remaining = _is_locked_out(request)
    if locked:
        minutes = remaining // 60
        seconds = remaining % 60
        messages.error(
            request,
            f"Твърде много неуспешни опити за вход. "
            f"Моля, изчакайте {minutes}м {seconds}с и опитайте отново."
        )
        return render(request, 'accounts/login.html', {
            'form': UserLoginForm(),
            'locked_out': True,
            'remaining_seconds': remaining,
        })

    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            _clear_login_attempts(request)
            login(request, user)
            messages.success(request, f"Здравейте отново, {user.first_name or user.username}!")

            # Safe redirect — prevent open redirect attacks
            next_url = request.GET.get('next', '')
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect('pets:dashboard')
        else:
            _record_failed_attempt(request)
            attempts = request.session.get('login_attempts', 0)
            remaining_attempts = max(0, _MAX_ATTEMPTS - attempts)
            if remaining_attempts > 0:
                messages.error(
                    request,
                    f"Грешно потребителско име или парола. "
                    f"Остават ви {remaining_attempts} опит(а)."
                )
            else:
                messages.error(
                    request,
                    f"Профилът е временно заключен за {_LOCKOUT_SECONDS // 60} минути "
                    "поради твърде много неуспешни опити."
                )
    else:
        form = UserLoginForm()

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
