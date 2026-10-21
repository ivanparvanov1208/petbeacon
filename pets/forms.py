from datetime import date

from django import forms
from django.conf import settings
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from PIL import Image, UnidentifiedImageError

from .models import Pet, Vaccination, MedicalRecord, Medication, VetVisit, Reminder


CHECKBOX_CLASSES = "h-5 w-5 shrink-0 cursor-pointer rounded border-ink-300 text-brand-600 focus:ring-2 focus:ring-brand-500 dark:border-ink-600"


_photo_placeholder = gettext_lazy("Напр. Рекс, Бела, Макс")
_breed_placeholder = gettext_lazy("Напр. Немска овчарка, Сиамска...")
_age_placeholder = gettext_lazy("Напр. 2 г. и 4 мес. (ако рождената дата е неизвестна)")
_weight_placeholder = gettext_lazy("Напр. 14.5")
_microchip_placeholder = gettext_lazy("15-цифрен код на микрочип")
_passport_placeholder = gettext_lazy("Номер на ветеринарен паспорт")
_diet_placeholder = gettext_lazy("Марка суха храна, консерви, брой хранения дневно, грамаж...")
_allergies_placeholder = gettext_lazy("Алергия към пилешко, към препарати, към медикаменти...")
_notes_placeholder = gettext_lazy("Характер, навици, контакт с други животни, любими играчки...")


class DefaultCheckedCheckboxInput(forms.CheckboxInput):

    def get_value(self, data, files, name):
        if not self.is_bound and name not in data:
            return True
        return super().get_value(data, files, name)


def _validate_upload_size(uploaded_file, label):
    max_bytes = getattr(settings, 'MAX_UPLOAD_SIZE_BYTES', 5 * 1024 * 1024)
    if uploaded_file.size > max_bytes:
        raise forms.ValidationError(
            _("%(label)s е твърде голям (%(size)d KB). Максималният размер е %(max)d MB.")
            % {
                "label": label,
                "size": uploaded_file.size // 1024,
                "max": max_bytes // (1024 * 1024),
            }
        )


def _extension_of(uploaded_file):
    return uploaded_file.name.rsplit('.', 1)[-1].lower() if '.' in uploaded_file.name else ''


def _validate_non_negative_money(value, label):
    if value is not None and value < 0:
        raise forms.ValidationError(
            _("%(label)s не може да е отрицателна.") % {"label": label}
        )
    return value


def _validate_image(image):
    if not image:
        return image

    _validate_upload_size(image, _("Снимката"))

    ext = _extension_of(image)
    allowed = getattr(settings, 'ALLOWED_IMAGE_EXTENSIONS', ['jpg', 'jpeg', 'png', 'gif', 'webp'])
    if ext not in allowed:
        raise forms.ValidationError(
            _("Неразрешен формат на снимката (%(ext)s). Позволени: %(allowed)s.")
            % {"ext": f".{ext or '?'}", "allowed": ", ".join('.' + e for e in allowed)}
        )

    try:
        image.seek(0)
        with Image.open(image) as opened:
            opened.verify()
    except UnidentifiedImageError:
        image.seek(0)
        raise forms.ValidationError(
            _("Съдържанието на файла не е валидно изображение. Уверете се, че качвате снимка, а не преименуван документ.")
        )
    except OSError:
        image.seek(0)
        raise forms.ValidationError(_("Снимката е повредена и не може да бъде прочетена."))
    finally:
        image.seek(0)

    return image


def _validate_document(doc):
    if not doc:
        return doc

    _validate_upload_size(doc, _("Документът"))

    ext = _extension_of(doc)
    allowed = getattr(
        settings,
        'ALLOWED_DOCUMENT_EXTENSIONS',
        ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'doc', 'docx', 'txt'],
    )
    if ext not in allowed:
        raise forms.ValidationError(
            _("Неразрешен формат на документа (%(ext)s). Позволени: %(allowed)s.")
            % {"ext": f".{ext or '?'}", "allowed": ", ".join('.' + e for e in allowed)}
        )

    return doc


class PetForm(forms.ModelForm):
    class Meta:
        model = Pet
        fields = [
            'name', 'species', 'breed', 'gender', 'is_neutered',
            'birth_date', 'approximate_age', 'weight',
            'microchip_number', 'passport_number', 'photo',
            'food_diet', 'allergies', 'special_notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': '', 'placeholder': _photo_placeholder}),
            'species': forms.Select(attrs={'class': ''}),
            'breed': forms.TextInput(attrs={'class': '', 'placeholder': _breed_placeholder}),
            'gender': forms.Select(attrs={'class': ''}),
            'is_neutered': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
            'birth_date': forms.DateInput(attrs={'class': '', 'type': 'date'}),
            'approximate_age': forms.TextInput(attrs={'class': '', 'placeholder': _age_placeholder}),
            'weight': forms.NumberInput(attrs={'class': '', 'step': '0.1', 'min': '0', 'placeholder': _weight_placeholder}),
            'microchip_number': forms.TextInput(attrs={'class': '', 'placeholder': _microchip_placeholder}),
            'passport_number': forms.TextInput(attrs={'class': '', 'placeholder': _passport_placeholder}),
            'photo': forms.FileInput(attrs={'class': '', 'accept': 'image/*'}),
            'food_diet': forms.Textarea(attrs={'class': '', 'rows': 3, 'placeholder': _diet_placeholder}),
            'allergies': forms.Textarea(attrs={'class': '', 'rows': 2, 'placeholder': _allergies_placeholder}),
            'special_notes': forms.Textarea(attrs={'class': '', 'rows': 3, 'placeholder': _notes_placeholder}),
        }

    def clean_photo(self):
        return _validate_image(self.cleaned_data.get('photo'))

    def clean_birth_date(self):
        birth_date = self.cleaned_data.get('birth_date')
        if birth_date and birth_date > date.today():
            raise forms.ValidationError(_("Датата на раждане не може да е в бъдещето."))
        return birth_date

    def clean_weight(self):
        weight = self.cleaned_data.get('weight')
        if weight is not None and weight <= 0:
            raise forms.ValidationError(_("Теглото трябва да е положително число."))
        return weight

    def clean_microchip_number(self):
        chip = (self.cleaned_data.get('microchip_number') or '').strip()
        if chip and not chip.isdigit():
            raise forms.ValidationError(
                _("Номерът на микрочипа трябва да се състои само от цифри (обикновено 15).")
            )
        if chip and len(chip) != 15:
            raise forms.ValidationError(
                _("Стандартният микрочип има 15 цифри, въведени са %(count)d.")
                % {"count": len(chip)}
            )
        return chip


class VaccinationForm(forms.ModelForm):
    create_reminder = forms.BooleanField(
        required=False,
        initial=True,
        label=gettext_lazy("Създай автоматично напомняне за следващата доза"),
        widget=DefaultCheckedCheckboxInput(attrs={'class': CHECKBOX_CLASSES})
    )

    class Meta:
        model = Vaccination
        fields = ['name', 'date_administered', 'next_due_date', 'batch_number', 'clinic_or_vet', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': '', 'placeholder': gettext_lazy("Напр. Бяс (Rabisin), DHPPi, Tricat...")}),
            'date_administered': forms.DateInput(attrs={'class': '', 'type': 'date'}),
            'next_due_date': forms.DateInput(attrs={'class': '', 'type': 'date'}),
            'batch_number': forms.TextInput(attrs={'class': '', 'placeholder': gettext_lazy("Партиден номер от стикера")}),
            'clinic_or_vet': forms.TextInput(attrs={'class': '', 'placeholder': gettext_lazy("Име на лекар или клиника")}),
            'notes': forms.Textarea(attrs={'class': '', 'rows': 2, 'placeholder': gettext_lazy("Наблюдавани реакции или бележки...")}),
        }

    def clean_date_administered(self):
        date_administered = self.cleaned_data.get('date_administered')
        if date_administered and date_administered > date.today():
            raise forms.ValidationError(_("Датата на поставяне не може да е в бъдещето."))
        return date_administered

    def clean(self):
        cleaned_data = super().clean()
        administered = cleaned_data.get('date_administered')
        next_due = cleaned_data.get('next_due_date')
        if administered and next_due and next_due < administered:
            self.add_error(
                'next_due_date',
                _("Следващата ваксинация не може да е преди датата на поставяне на сегашната."),
            )
        return cleaned_data


class MedicalRecordForm(forms.ModelForm):
    class Meta:
        model = MedicalRecord
        fields = ['date', 'title', 'diagnosis', 'treatment', 'veterinarian', 'clinic', 'cost', 'notes', 'document']
        widgets = {
            'date': forms.DateInput(attrs={'class': '', 'type': 'date'}),
            'title': forms.TextInput(attrs={'class': '', 'placeholder': gettext_lazy("Напр. Почистване на зъбен камък, Отит...")}),
            'diagnosis': forms.Textarea(attrs={'class': '', 'rows': 2, 'placeholder': gettext_lazy("Констатирано състояние / диагноза...")}),
            'treatment': forms.Textarea(attrs={'class': '', 'rows': 3, 'placeholder': gettext_lazy("Приложена терапия, манипулации, инжекции...")}),
            'veterinarian': forms.TextInput(attrs={'class': '', 'placeholder': gettext_lazy("Д-р Петров")}),
            'clinic': forms.TextInput(attrs={'class': '', 'placeholder': gettext_lazy('Ветеринарна клиника "ЗооВет"')}),
            'cost': forms.NumberInput(attrs={'class': '', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'notes': forms.Textarea(attrs={'class': '', 'rows': 2, 'placeholder': gettext_lazy("Допълнителни указания...")}),
            'document': forms.FileInput(attrs={'class': ''}),
        }

    def clean_document(self):
        return _validate_document(self.cleaned_data.get('document'))

    def clean_cost(self):
        return _validate_non_negative_money(self.cleaned_data.get('cost'), _("Стойността"))


class MedicationForm(forms.ModelForm):
    create_reminder = forms.BooleanField(
        required=False,
        initial=True,
        label=gettext_lazy("Добави в списъка с напомняния"),
        widget=DefaultCheckedCheckboxInput(attrs={'class': CHECKBOX_CLASSES})
    )

    class Meta:
        model = Medication
        fields = ['name', 'dosage', 'frequency', 'start_date', 'end_date', 'instructions', 'is_active', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': '', 'placeholder': gettext_lazy("Напр. Синулокс, Апоквел, Омега-3...")}),
            'dosage': forms.TextInput(attrs={'class': '', 'placeholder': gettext_lazy("Напр. 1 табл., 2.5 мл, 3 капки")}),
            'frequency': forms.TextInput(attrs={'class': '', 'placeholder': gettext_lazy("Напр. 2 пъти на ден (сутрин и вечер)")}),
            'start_date': forms.DateInput(attrs={'class': '', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': '', 'type': 'date'}),
            'instructions': forms.Textarea(attrs={'class': '', 'rows': 2, 'placeholder': gettext_lazy("Да се дава с храната; да не се дели таблетката...")}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
            'notes': forms.Textarea(attrs={'class': '', 'rows': 2, 'placeholder': gettext_lazy("Бележки или поносимост")}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', _("Крайната дата не може да е преди началната дата."))
        return cleaned_data


class VetVisitForm(forms.ModelForm):
    class Meta:
        model = VetVisit
        fields = ['visit_date', 'clinic_name', 'vet_name', 'phone', 'reason', 'examination_summary', 'recommendations', 'total_cost']
        widgets = {
            'visit_date': forms.DateInput(attrs={'class': '', 'type': 'date'}),
            'clinic_name': forms.TextInput(attrs={'class': '', 'placeholder': gettext_lazy("Ветеринарна клиника...")}),
            'vet_name': forms.TextInput(attrs={'class': '', 'placeholder': gettext_lazy("Д-р Георгиев")}),
            'phone': forms.TextInput(attrs={'class': '', 'placeholder': '+359 888 123 456'}),
            'reason': forms.TextInput(attrs={'class': '', 'placeholder': gettext_lazy("Годишен профилактичен преглед, проблем с лапата...")}),
            'examination_summary': forms.Textarea(attrs={'class': '', 'rows': 3, 'placeholder': gettext_lazy("Температура, състояние на козината, зъби, лимфни възли...")}),
            'recommendations': forms.Textarea(attrs={'class': '', 'rows': 3, 'placeholder': gettext_lazy("Препоръки за храна, контролен преглед след 10 дни...")}),
            'total_cost': forms.NumberInput(attrs={'class': '', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
        }

    def clean_total_cost(self):
        return _validate_non_negative_money(self.cleaned_data.get('total_cost'), _("Стойността"))


class ReminderForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['pet'].queryset = Pet.objects.filter(owner=user)
            self.fields['pet'].empty_label = _("Общо напомняне (без конкретен любимец)")

    class Meta:
        model = Reminder
        fields = ['pet', 'reminder_type', 'title', 'due_date', 'due_time', 'priority', 'notes', 'is_completed']
        widgets = {
            'pet': forms.Select(attrs={'class': ''}),
            'reminder_type': forms.Select(attrs={'class': ''}),
            'title': forms.TextInput(attrs={'class': '', 'placeholder': gettext_lazy("Напр. Ваксинация срещу бяс, Контролен преглед...")}),
            'due_date': forms.DateInput(attrs={'class': '', 'type': 'date'}),
            'due_time': forms.TimeInput(attrs={'class': '', 'type': 'time'}),
            'priority': forms.Select(attrs={'class': ''}),
            'is_completed': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
            'notes': forms.Textarea(attrs={'class': '', 'rows': 2, 'placeholder': gettext_lazy("Допълнителни детайли, час за запазване...")}),
        }
