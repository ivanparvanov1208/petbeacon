from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

_I = "w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none transition text-slate-800 bg-white placeholder:text-slate-400"


class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        label="Парола",
        widget=forms.PasswordInput(attrs={'class': _I, 'placeholder': 'Минимум 8 символа'}),
        min_length=8
    )
    password_confirm = forms.CharField(
        label="Потвърди паролата",
        widget=forms.PasswordInput(attrs={'class': _I, 'placeholder': 'Повторете паролата'}),
        min_length=8
    )
    phone = forms.CharField(
        label="Телефон за връзка (по избор)",
        required=False,
        widget=forms.TextInput(attrs={'class': _I, 'placeholder': '+359 88 123 4567'})
    )
    city = forms.CharField(
        label="Град (по избор)",
        required=False,
        widget=forms.TextInput(attrs={'class': _I, 'placeholder': 'София, Пловдив, Варна...'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        labels = {
            'username': 'Потребителско име',
            'first_name': 'Име',
            'last_name': 'Фамилия',
            'email': 'Имейл адрес',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': _I, 'placeholder': 'pet_lover123'}),
            'first_name': forms.TextInput(attrs={'class': _I, 'placeholder': 'Иван'}),
            'last_name': forms.TextInput(attrs={'class': _I, 'placeholder': 'Иванов'}),
            'email': forms.EmailInput(attrs={'class': _I, 'placeholder': 'ivan@example.com'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Този имейл адрес вече се използва от друг профил.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Това потребителско име вече е заето.")
        return username

    def _password_candidate(self):
        """Build an unsaved User so the similarity validator has real context.

        ``self.instance`` is not populated until ``_post_clean()``, which runs
        after the per-field cleaners, so it cannot be used here.
        """
        return User(
            username=self.data.get('username', ''),
            first_name=self.data.get('first_name', ''),
            last_name=self.data.get('last_name', ''),
            email=self.data.get('email', ''),
        )

    def _validate_password_strength(self, password, user=None):
        """Run the project's AUTH_PASSWORD_VALIDATORS against the candidate."""
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
            self.add_error('password_confirm', "Паролите не съвпадат!")
        return cleaned_data


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Потребителско име",
        widget=forms.TextInput(attrs={
            'class': _I,
            'placeholder': 'Въведете потребителско име',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label="Парола",
        widget=forms.PasswordInput(attrs={'class': _I, 'placeholder': '••••••••'})
    )


class UserProfileUpdateForm(forms.ModelForm):
    phone = forms.CharField(
        label="Телефон",
        required=False,
        widget=forms.TextInput(attrs={'class': _I, 'placeholder': '+359 88 123 4567'})
    )
    city = forms.CharField(
        label="Град",
        required=False,
        widget=forms.TextInput(attrs={'class': _I, 'placeholder': 'София, Пловдив...'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        labels = {
            'first_name': 'Име',
            'last_name': 'Фамилия',
            'email': 'Имейл адрес',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': _I}),
            'last_name': forms.TextInput(attrs={'class': _I}),
            'email': forms.EmailInput(attrs={'class': _I}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Този имейл адрес вече се използва от друг профил.")
        return email
