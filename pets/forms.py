from django import forms
from django.conf import settings
from .models import Pet, Vaccination, MedicalRecord, Medication, VetVisit, Reminder


COMMON_INPUT_CLASSES = "w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none transition text-slate-800 bg-white placeholder:text-slate-400"
COMMON_TEXTAREA_CLASSES = "w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none transition text-slate-800 bg-white placeholder:text-slate-400 resize-y"
COMMON_SELECT_CLASSES = "w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none transition bg-white text-slate-800"
FILE_INPUT_CLASSES = "w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100 cursor-pointer"
CHECKBOX_CLASSES = "w-5 h-5 text-brand-600 rounded border-slate-300 focus:ring-brand-500"


def _validate_image(image):
    """Shared validator for uploaded images."""
    if not image:
        return image
    max_bytes = getattr(settings, 'MAX_UPLOAD_SIZE_BYTES', 5 * 1024 * 1024)
    if image.size > max_bytes:
        raise forms.ValidationError(
            f"Файлът е твърде голям ({image.size // 1024} KB). Максималният размер е {max_bytes // (1024*1024)} MB."
        )
    ext = image.name.rsplit('.', 1)[-1].lower()
    allowed = getattr(settings, 'ALLOWED_IMAGE_EXTENSIONS', ['jpg', 'jpeg', 'png', 'gif', 'webp'])
    if ext not in allowed:
        raise forms.ValidationError(
            f"Неразрешен формат на файла (.{ext}). Позволени: {', '.join('.' + e for e in allowed)}."
        )
    return image


def _validate_document(doc):
    """Shared validator for uploaded documents."""
    if not doc:
        return doc
    max_bytes = getattr(settings, 'MAX_UPLOAD_SIZE_BYTES', 5 * 1024 * 1024)
    if doc.size > max_bytes:
        raise forms.ValidationError(
            f"Файлът е твърде голям ({doc.size // 1024} KB). Максималният размер е {max_bytes // (1024*1024)} MB."
        )
    ext = doc.name.rsplit('.', 1)[-1].lower()
    allowed = getattr(settings, 'ALLOWED_DOCUMENT_EXTENSIONS', ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'txt'])
    if ext not in allowed:
        raise forms.ValidationError(
            f"Неразрешен формат (.{ext}). Позволени: {', '.join('.' + e for e in allowed)}."
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
            'weight': forms.NumberInput(attrs={'class': COMMON_INPUT_CLASSES, 'step': '0.1', 'placeholder': 'Напр. 14.5'}),
            'microchip_number': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': '15-цифрен код на микрочип'}),
            'passport_number': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES, 'placeholder': 'Номер на ветеринарен паспорт'}),
            'photo': forms.FileInput(attrs={'class': FILE_INPUT_CLASSES, 'accept': 'image/*'}),
            'food_diet': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 3, 'placeholder': 'Марка суха храна, консерви, брой хранения дневно, грамаж...'}),
            'allergies': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 2, 'placeholder': 'Алергия към пилешко, към препарати, към медикаменти...'}),
            'special_notes': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 3, 'placeholder': 'Характер, навици, контакт с други животни, любими играчки...'}),
        }

    def clean_photo(self):
        return _validate_image(self.cleaned_data.get('photo'))


class VaccinationForm(forms.ModelForm):
    create_reminder = forms.BooleanField(
        required=False,
        initial=True,
        label="Създай автоматично напомняне за следващата доза",
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES})
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
            'cost': forms.NumberInput(attrs={'class': COMMON_INPUT_CLASSES, 'step': '0.01', 'placeholder': '0.00'}),
            'notes': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASSES, 'rows': 2, 'placeholder': 'Допълнителни указания...'}),
            'document': forms.FileInput(attrs={'class': FILE_INPUT_CLASSES}),
        }

    def clean_document(self):
        return _validate_document(self.cleaned_data.get('document'))


class MedicationForm(forms.ModelForm):
    create_reminder = forms.BooleanField(
        required=False,
        initial=True,
        label="Добави в списъка с напомняния",
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES})
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
            'total_cost': forms.NumberInput(attrs={'class': COMMON_INPUT_CLASSES, 'step': '0.01', 'placeholder': '0.00'}),
        }


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
