from datetime import date

from django import forms
from django.conf import settings
from PIL import Image, UnidentifiedImageError

from .models import Pet, Vaccination, MedicalRecord, Medication, VetVisit, Reminder


COMMON_INPUT_CLASSES = "w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none transition text-slate-800 bg-white placeholder:text-slate-400"
COMMON_TEXTAREA_CLASSES = "w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none transition text-slate-800 bg-white placeholder:text-slate-400 resize-y"
COMMON_SELECT_CLASSES = "w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none transition bg-white text-slate-800"
FILE_INPUT_CLASSES = "w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100 cursor-pointer"
CHECKBOX_CLASSES = "w-5 h-5 text-brand-600 rounded border-slate-300 focus:ring-brand-500"
ERROR_CLASSES = "mt-1.5 text-xs font-medium text-rose-600"
LABEL_CLASSES = "block text-xs sm:text-sm font-semibold text-slate-700 mb-1.5"


class DefaultCheckedCheckboxInput(forms.CheckboxInput):
    """Checkbox input that renders ``checked`` for unbound forms.

    Django's ``CheckboxInput.get_value()`` returns ``False`` whenever the field
    name is absent from the submitted data, so ``initial=True`` is never
    reflected in the rendered HTML. This restores the intended default while
    still reflecting the real POST data when the form is re-rendered after a
    validation error.
    """

    def get_value(self, data, files, name):
        if not self.is_bound and name not in data:
            return True
        return super().get_value(data, files, name)


def _validate_upload_size(uploaded_file, label="Файлът"):
    max_bytes = getattr(settings, 'MAX_UPLOAD_SIZE_BYTES', 5 * 1024 * 1024)
    if uploaded_file.size > max_bytes:
        raise forms.ValidationError(
            f"{label} е твърде голям ({uploaded_file.size // 1024} KB). "
            f"Максималният размер е {max_bytes // (1024 * 1024)} MB."
        )


def _extension_of(uploaded_file):
    return uploaded_file.name.rsplit('.', 1)[-1].lower() if '.' in uploaded_file.name else ''


def _validate_non_negative_money(value, label):
    if value is not None and value < 0:
        raise forms.ValidationError(f"{label} не може да е отрицателна.")
    return value


def _validate_image(image):
    """Validate an uploaded image by size, extension *and* real content.

    The extension check alone is trivially bypassable (any file renamed to
    ``.jpg``), so the file is also opened with Pillow to confirm it really is
    a decodable image.
    """
    if not image:
        return image

    _validate_upload_size(image, "Снимката")

    ext = _extension_of(image)
    allowed = getattr(settings, 'ALLOWED_IMAGE_EXTENSIONS', ['jpg', 'jpeg', 'png', 'gif', 'webp'])
    if ext not in allowed:
        raise forms.ValidationError(
            f"Неразрешен формат на снимката (.{ext or '?'}). "
            f"Позволени: {', '.join('.' + e for e in allowed)}."
        )

    try:
        image.seek(0)
        with Image.open(image) as opened:
            opened.verify()
    except UnidentifiedImageError:
        image.seek(0)
        raise forms.ValidationError(
            "Съдържанието на файла не е валидно изображение. "
            "Уверете се, че качвате снимка, а не преименуван документ."
        )
    except OSError:
        image.seek(0)
        raise forms.ValidationError("Снимката е повредена и не може да бъде прочетена.")
    finally:
        image.seek(0)

    return image


def _validate_document(doc):
    """Validate an uploaded medical document by size and extension."""
    if not doc:
        return doc

    _validate_upload_size(doc, "Документът")

    ext = _extension_of(doc)
    allowed = getattr(
        settings,
        'ALLOWED_DOCUMENT_EXTENSIONS',
        ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'doc', 'docx', 'txt'],
    )
    if ext not in allowed:
        raise forms.ValidationError(
            f"Неразрешен формат на документа (.{ext or '?'}). "
            f"Позволени: {', '.join('.' + e for e in allowed)}."
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
            'name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Напр. Рекс, Бела, Макс'}),
            'species': forms.Select(attrs={'class': COMMON_SELECT_CLASSES}),
            'breed': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Напр. Немска овчарка, Сиамска...'}),
            'gender': forms.Select(attrs={'class': COMMON_SELECT_CLASSES}),
            'is_neutered': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
            'birth_date': forms.DateInput(attrs={'class': COMMON_INPUT_CLASSES, 'type': 'date'}),
            'approximate_age': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Напр. 2 г. и 4 мес. (ако рождената дата е неизвестна)'}),
            'weight': forms.NumberInput(attrs={'class': COMMON_INPUT_CLASSES, 'step': '0.1', 'min': '0', 'placeholder': 'Напр. 14.5'}),
            'microchip_number': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': '15-цифрен код на микрочип'}),
            'passport_number': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Номер на ветеринарен паспорт'}),
            'photo': forms.FileInput(attrs={'class': FILE_INPUT_CLASSES, 'accept': 'image/*'}),
            'food_diet': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 3, 'placeholder': 'Марка суха храна, консерви, брой хранения дневно, грамаж...'}),
            'allergies': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 2, 'placeholder': 'Алергия към пилешко, към препарати, към медикаменти...'}),
            'special_notes': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 3, 'placeholder': 'Характер, навици, контакт с други животни, любими играчки...'}),
        }

    def clean_photo(self):
        return _validate_image(self.cleaned_data.get('photo'))

    def clean_birth_date(self):
        birth_date = self.cleaned_data.get('birth_date')
        if birth_date and birth_date > date.today():
            raise forms.ValidationError("Датата на раждане не може да е в бъдещето.")
        return birth_date

    def clean_weight(self):
        weight = self.cleaned_data.get('weight')
        if weight is not None and weight <= 0:
            raise forms.ValidationError("Теглото трябва да е положително число.")
        return weight

    def clean_microchip_number(self):
        chip = (self.cleaned_data.get('microchip_number') or '').strip()
        if chip and not chip.isdigit():
            raise forms.ValidationError(
                "Номерът на микрочипа трябва да се състои само от цифри (обикновено 15)."
            )
        if chip and len(chip) != 15:
            raise forms.ValidationError(
                f"Стандартният микрочип има 15 цифри, въведени са {len(chip)}."
            )
        return chip



class VaccinationForm(forms.ModelForm):
    create_reminder = forms.BooleanField(
        required=False,
        initial=True,
        label="Създай автоматично напомняне за следващата доза",
        widget=DefaultCheckedCheckboxInput(attrs={'class': CHECKBOX_CLASSES})
    )

    class Meta:
        model = Vaccination
        fields = ['name', 'date_administered', 'next_due_date', 'batch_number', 'clinic_or_vet', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Напр. Бяс (Rabisin), DHPPi, Tricat...'}),
            'date_administered': forms.DateInput(attrs={'class': COMMON_INPUT_CLASSES, 'type': 'date'}),
            'next_due_date': forms.DateInput(attrs={'class': COMMON_INPUT_CLASSES, 'type': 'date'}),
            'batch_number': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Партиден номер от стикера'}),
            'clinic_or_vet': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Име на лекар или клиника'}),
            'notes': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 2, 'placeholder': 'Наблюдавани реакции или бележки...'}),
        }

    def clean_date_administered(self):
        date_administered = self.cleaned_data.get('date_administered')
        if date_administered and date_administered > date.today():
            raise forms.ValidationError("Датата на поставяне не може да е в бъдещето.")
        return date_administered

    def clean(self):
        cleaned_data = super().clean()
        administered = cleaned_data.get('date_administered')
        next_due = cleaned_data.get('next_due_date')
        if administered and next_due and next_due < administered:
            self.add_error(
                'next_due_date',
                "Следващата ваксинация не може да е преди датата на поставяне на сегашната.",
            )
        return cleaned_data


class MedicalRecordForm(forms.ModelForm):
    class Meta:
        model = MedicalRecord
        fields = ['date', 'title', 'diagnosis', 'treatment', 'veterinarian', 'clinic', 'cost', 'notes', 'document']
        widgets = {
            'date': forms.DateInput(attrs={'class': COMMON_INPUT_CLASSES, 'type': 'date'}),
            'title': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Напр. Почистване на зъбен камък, Отит...'}),
            'diagnosis': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 2, 'placeholder': 'Констатирано състояние / диагноза...'}),
            'treatment': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 3, 'placeholder': 'Приложена терапия, манипулации, инжекции...'}),
            'veterinarian': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Д-р Петров'}),
            'clinic': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Ветеринарна клиника "ЗооВет"'}),
            'cost': forms.NumberInput(attrs={'class': COMMON_INPUT_CLASSES, 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'notes': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 2, 'placeholder': 'Допълнителни указания...'}),
            'document': forms.FileInput(attrs={'class': FILE_INPUT_CLASSES}),
        }

    def clean_document(self):
        return _validate_document(self.cleaned_data.get('document'))

    def clean_cost(self):
        return _validate_non_negative_money(self.cleaned_data.get('cost'), 'Стойността')


class MedicationForm(forms.ModelForm):
    create_reminder = forms.BooleanField(
        required=False,
        initial=True,
        label="Добави в списъка с напомняния",
        widget=DefaultCheckedCheckboxInput(attrs={'class': CHECKBOX_CLASSES})
    )

    class Meta:
        model = Medication
        fields = ['name', 'dosage', 'frequency', 'start_date', 'end_date', 'instructions', 'is_active', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Напр. Синулокс, Апоквел, Омега-3...'}),
            'dosage': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Напр. 1 табл., 2.5 мл, 3 капки'}),
            'frequency': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Напр. 2 пъти на ден (сутрин и вечер)'}),
            'start_date': forms.DateInput(attrs={'class': COMMON_INPUT_CLASSES, 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': COMMON_INPUT_CLASSES, 'type': 'date'}),
            'instructions': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 2, 'placeholder': 'Да се дава с храната; да не се дели таблетката...'}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
            'notes': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 2, 'placeholder': 'Бележки или поносимост'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', "Крайната дата не може да е преди началната дата.")
        return cleaned_data


class VetVisitForm(forms.ModelForm):
    class Meta:
        model = VetVisit
        fields = ['visit_date', 'clinic_name', 'vet_name', 'phone', 'reason', 'examination_summary', 'recommendations', 'total_cost']
        widgets = {
            'visit_date': forms.DateInput(attrs={'class': COMMON_INPUT_CLASSES, 'type': 'date'}),
            'clinic_name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Ветеринарна клиника...'}),
            'vet_name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Д-р Георгиев'}),
            'phone': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': '+359 888 123 456'}),
            'reason': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Годишен профилактичен преглед, проблем с лапата...'}),
            'examination_summary': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 3, 'placeholder': 'Температура, състояние на козината, зъби, лимфни възли...'}),
            'recommendations': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 3, 'placeholder': 'Препоръки за храна, контролен преглед след 10 дни...'}),
            'total_cost': forms.NumberInput(attrs={'class': COMMON_INPUT_CLASSES, 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
        }

    def clean_total_cost(self):
        return _validate_non_negative_money(self.cleaned_data.get('total_cost'), 'Стойността')


class ReminderForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['pet'].queryset = Pet.objects.filter(owner=user)
            self.fields['pet'].empty_label = "Общо напомняне (без конкретен любимец)"

    class Meta:
        model = Reminder
        fields = ['pet', 'reminder_type', 'title', 'due_date', 'due_time', 'priority', 'notes', 'is_completed']
        widgets = {
            'pet': forms.Select(attrs={'class': COMMON_SELECT_CLASSES}),
            'reminder_type': forms.Select(attrs={'class': COMMON_SELECT_CLASSES}),
            'title': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Напр. Ваксинация срещу бяс, Контролен преглед...'}),
            'due_date': forms.DateInput(attrs={'class': COMMON_INPUT_CLASSES, 'type': 'date'}),
            'due_time': forms.TimeInput(attrs={'class': COMMON_INPUT_CLASSES, 'type': 'time'}),
            'priority': forms.Select(attrs={'class': COMMON_SELECT_CLASSES}),
            'is_completed': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
            'notes': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 2, 'placeholder': 'Допълнителни детайли, час за запазване...'}),
        }
