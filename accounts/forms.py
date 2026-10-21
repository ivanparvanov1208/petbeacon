from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

_I = (
    "w-full rounded-lg border border-ink-200 bg-white px-3.5 py-2.5 text-sm text-ink-800 "
    "shadow-xs transition placeholder:text-ink-400 "
    "focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15 focus:outline-none "
    "disabled:cursor-not-allowed disabled:bg-ink-50"
)


class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        label=gettext_lazy("Парола"),
        widget=forms.PasswordInput(attrs={'class': _I, 'placeholder': gettext_lazy("Минимум 8 символа")}),
        min_length=8
    )
    password_confirm = forms.CharField(
        label=gettext_lazy("Потвърди паролата"),
        widget=forms.PasswordInput(attrs={'class': _I, 'placeholder': gettext_lazy("Повторете паролата")}),
        min_length=8
    )
    phone = forms.CharField(
        label=gettext_lazy("Телефон за връзка (по избор)"),
        required=False,
        widget=forms.TextInput(attrs={'class': _I, 'placeholder': '+359 88 123 4567'})
    )
    city = forms.CharField(
        label=gettext_lazy("Град (по избор)"),
        required=False,
        widget=forms.TextInput(attrs={'class': _I, 'placeholder': gettext_lazy("София, Пловдив, Варна...")})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        labels = {
            'username': gettext_lazy("Потребителско име"),
            'first_name': gettext_lazy("Име"),
            'last_name': gettext_lazy("Фамилия"),
            'email': gettext_lazy("Имейл адрес"),
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': _I, 'placeholder': 'pet_lover123'}),
            'first_name': forms.TextInput(attrs={'class': _I, 'placeholder': gettext_lazy("Иван")}),
            'last_name': forms.TextInput(attrs={'class': _I, 'placeholder': gettext_lazy("Иванов")}),
            'email': forms.EmailInput(attrs={'class': _I, 'placeholder': 'ivan@example.com'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Този имейл адрес вече се използва от друг профил."))
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(_("Това потребителско име вече е заето."))
        return username

    def _password_candidate(self):
        return User(
            username=self.data.get('username', ''),
            first_name=self.data.get('first_name', ''),
            last_name=self.data.get('last_name', ''),
            email=self.data.get('email', ''),
        )

    def _validate_password_strength(self, password, user=None):
        if not password:
            return
        try:
            validate_password(password, user)
        except forms.ValidationError as exc:
            raise forms.ValidationError(exc.messages, code='password_too_weak')

    def clean_password(self):
        password = self.cleaned_data.get('password')
        self._validate_password_strength(password, self._password_candidate())
        return password

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', _("Паролите не съвпадат!"))
        return cleaned_data


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        label=gettext_lazy("Потребителско име"),
        widget=forms.TextInput(attrs={
            'class': _I,
            'placeholder': gettext_lazy("Въведете потребителско име"),
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label=gettext_lazy("Парола"),
        widget=forms.PasswordInput(attrs={'class': _I, 'placeholder': '••••••••'})
    )


class UserProfileUpdateForm(forms.ModelForm):
    phone = forms.CharField(
        label=gettext_lazy("Телефон"),
        required=False,
        widget=forms.TextInput(attrs={'class': _I, 'placeholder': '+359 88 123 4567'})
    )
    city = forms.CharField(
        label=gettext_lazy("Град"),
        required=False,
        widget=forms.TextInput(attrs={'class': _I, 'placeholder': gettext_lazy("София, Пловдив...")})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        labels = {
            'first_name': gettext_lazy("Име"),
            'last_name': gettext_lazy("Фамилия"),
            'email': gettext_lazy("Имейл адрес"),
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': _I}),
            'last_name': forms.TextInput(attrs={'class': _I}),
            'email': forms.EmailInput(attrs={'class': _I}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Този имейл адрес вече се използва от друг профил."))
        return email
