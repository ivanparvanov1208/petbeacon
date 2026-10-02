from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date


class Pet(models.Model):
    SPECIES_CHOICES = [
        ('dog', 'Куче'),
        ('cat', 'Котка'),
        ('bird', 'Птица'),
        ('rodent', 'Гризач'),
        ('rabbit', 'Заек'),
        ('fish', 'Рибки / Аквариум'),
        ('reptile', 'Влечуго'),
        ('other', 'Друго'),
    ]

    GENDER_CHOICES = [
        ('male', 'Мъжки'),
        ('female', 'Женски'),
        ('unknown', 'Неизвестен'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pets', verbose_name="Собственик")
    name = models.CharField(max_length=100, verbose_name="Име на любимеца")
    species = models.CharField(max_length=20, choices=SPECIES_CHOICES, default='dog', verbose_name="Вид животно")
    breed = models.CharField(max_length=100, blank=True, verbose_name="Порода")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='unknown', verbose_name="Пол")
    is_neutered = models.BooleanField(default=False, verbose_name="Кастриран / Кастрирана")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Дата на раждане")
    approximate_age = models.CharField(max_length=50, blank=True, verbose_name="Приблизителна възраст", help_text="Ако не знаете точната дата на раждане (напр. '2 години')")
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Тегло (кг)")
    microchip_number = models.CharField(max_length=50, blank=True, verbose_name="Номер на микрочип")
    passport_number = models.CharField(max_length=50, blank=True, verbose_name="Номер на европейски паспорт")
    photo = models.ImageField(upload_to='pets/', blank=True, null=True, verbose_name="Снимка")
    food_diet = models.TextField(blank=True, verbose_name="Хранене и диета", help_text="Любима храна, дневна дажба, график на хранене, забранени лакомства")
    allergies = models.TextField(blank=True, verbose_name="Алергии и непоносимости", help_text="Хранителни или медикаментозни алергии")
    special_notes = models.TextField(blank=True, verbose_name="Специални бележки и характер", help_text="Особености в поведението, навици, страх от гръмотевици и т.н.")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Създаден на")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновен на")

    class Meta:
        verbose_name = "Домашен любимец"
        verbose_name_plural = "Домашни любимци"
        ordering = ['name']
        indexes = [
            models.Index(fields=['microchip_number'], name='pet_microchip_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weight__isnull=True) | models.Q(weight__gte=0),
                name='pet_weight_non_negative',
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_species_display()})"

    @property
    def age_display(self):
        if not self.birth_date:
            return self.approximate_age or "Не е посочена"

        today = date.today()
        if self.birth_date > today:
            return "Невалидна дата"

        months = (today.year - self.birth_date.year) * 12 + today.month - self.birth_date.month
        if today.day < self.birth_date.day:
            months -= 1
        months = max(months, 0)

        years, rem_months = divmod(months, 12)
        if years:
            return f"{years} г. и {rem_months} мес." if rem_months else f"{years} г."
        if months:
            return f"{months} мес."
        return f"{(today - self.birth_date).days} дни"

    @property
    def species_icon(self):
        icons = {
            'dog': 'fa-solid fa-dog text-amber-600',
            'cat': 'fa-solid fa-cat text-indigo-600',
            'bird': 'fa-solid fa-dove text-sky-500',
            'rodent': 'fa-solid fa-otter text-amber-700',
            'rabbit': 'fa-solid fa-carrot text-orange-500',
            'fish': 'fa-solid fa-fish text-cyan-500',
            'reptile': 'fa-solid fa-dragon text-emerald-600',
            'other': 'fa-solid fa-paw text-teal-600',
        }
        return icons.get(self.species, 'fa-solid fa-paw text-teal-600')

    @property
    def photo_url(self):
        if self.photo and hasattr(self.photo, 'url'):
            return self.photo.url
        return None


class Vaccination(models.Model):
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='vaccinations', verbose_name="Любимец")
    name = models.CharField(max_length=150, verbose_name="Име на ваксината", help_text="Напр. Бяс, DHPPi, Tricat, Годишна поливалентна")
    date_administered = models.DateField(verbose_name="Дата на поставяне")
    next_due_date = models.DateField(null=True, blank=True, verbose_name="Следваща ваксинация (краен срок)")
    batch_number = models.CharField(max_length=100, blank=True, verbose_name="Сериен / партиден номер")
    clinic_or_vet = models.CharField(max_length=150, blank=True, verbose_name="Клиника / Лекар")
    notes = models.TextField(blank=True, verbose_name="Бележки / странични реакции")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ваксинация"
        verbose_name_plural = "Ваксинации"
        ordering = ['-date_administered']
        indexes = [
            models.Index(fields=['next_due_date'], name='vacc_next_due_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(next_due_date__isnull=True)
                    | models.Q(next_due_date__gte=models.F('date_administered'))
                ),
                name='vacc_next_due_after_administered',
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.pet.name} ({self.date_administered})"

    @property
    def is_overdue(self):
        if not self.next_due_date:
            return False
        return self.next_due_date < date.today()

    @property
    def is_due_soon(self):
        if not self.next_due_date:
            return False
        days = (self.next_due_date - date.today()).days
        return 0 <= days <= 30

    @property
    def status(self):
        if not self.next_due_date:
            return 'completed'
        if self.is_overdue:
            return 'overdue'
        if self.is_due_soon:
            return 'due_soon'
        return 'valid'


class MedicalRecord(models.Model):
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='medical_records', verbose_name="Любимец")
    date = models.DateField(default=date.today, verbose_name="Дата на процедурата / прегледа")
    title = models.CharField(max_length=200, verbose_name="Причина / Диагноза / Процедура", help_text="Напр. Годишен преглед, почистване на зъбен камък, гастрит")
    diagnosis = models.TextField(blank=True, verbose_name="Констатации и диагноза")
    treatment = models.TextField(blank=True, verbose_name="Назначено лечение и процедури")
    veterinarian = models.CharField(max_length=150, blank=True, verbose_name="Ветеринарен лекар")
    clinic = models.CharField(max_length=150, blank=True, verbose_name="Ветеринарна клиника")
    cost = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Стойност (лв.)")
    notes = models.TextField(blank=True, verbose_name="Допълнителни бележки")
    document = models.FileField(upload_to='medical_docs/', blank=True, null=True, verbose_name="Прикачен файл / резултати")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Медицински запис"
        verbose_name_plural = "Медицинска история"
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.title} - {self.pet.name} ({self.date})"


class Medication(models.Model):
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='medications', verbose_name="Любимец")
    name = models.CharField(max_length=150, verbose_name="Име на медикамента", help_text="Напр. Антибиотик, Витамини, Капки за очи")
    dosage = models.CharField(max_length=100, verbose_name="Дозировка", help_text="Напр. 1 таблетка, 2.5 мл")
    frequency = models.CharField(max_length=100, verbose_name="Честота на прием", help_text="Напр. 2 пъти дневно, сутрин и вечер, на всеки 8 часа")
    start_date = models.DateField(default=date.today, verbose_name="Начална дата")
    end_date = models.DateField(null=True, blank=True, verbose_name="Крайна дата (по избор)")
    instructions = models.TextField(blank=True, verbose_name="Специфични указания", help_text="По време на хранене, разтворено във вода и др.")
    is_active = models.BooleanField(default=True, verbose_name="Активен прием в момента")
    notes = models.TextField(blank=True, verbose_name="Бележки")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Прием на лекарство"
        verbose_name_plural = "Прием на лекарства"
        ordering = ['-is_active', '-start_date']
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(end_date__isnull=True)
                    | models.Q(end_date__gte=models.F('start_date'))
                ),
                name='med_end_after_start',
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.dosage}) - {self.pet.name}"


class VetVisit(models.Model):
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='vet_visits', verbose_name="Любимец")
    visit_date = models.DateField(default=date.today, verbose_name="Дата на посещението")
    clinic_name = models.CharField(max_length=150, verbose_name="Име на клиниката")
    vet_name = models.CharField(max_length=150, blank=True, verbose_name="Име на лекаря")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Телефон за връзка с клиниката")
    reason = models.CharField(max_length=250, verbose_name="Причина за посещението", help_text="Профилактика, спешен преглед, контролен преглед...")
    examination_summary = models.TextField(blank=True, verbose_name="Резултати от прегледа")
    recommendations = models.TextField(blank=True, verbose_name="Препоръки и следващи стъпки")
    total_cost = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Стойност (лв.)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ветеринарно посещение"
        verbose_name_plural = "Ветеринарни посещения"
        ordering = ['-visit_date', '-created_at']

    def __str__(self):
        return f"{self.pet.name} при {self.clinic_name} на {self.visit_date}"


class Reminder(models.Model):
    TYPE_CHOICES = [
        ('vaccination', 'Ваксинация'),
        ('vet_visit', 'Ветеринарен преглед'),
        ('medication', 'Прием на лекарство'),
        ('deworming', 'Обезпаразитяване'),
        ('grooming', 'Груминг / Къпане'),
        ('food_refill', 'Покупка на храна'),
        ('other', 'Друго напомняне'),
    ]

    PRIORITY_CHOICES = [
        ('high', 'Висок приоритет'),
        ('normal', 'Нормален приоритет'),
        ('low', 'Нисък приоритет'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reminders', verbose_name="Потребител")
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='reminders', null=True, blank=True, verbose_name="Любимец")
    reminder_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='vaccination', verbose_name="Тип напомняне")
    title = models.CharField(max_length=200, verbose_name="Заглавие на напомнянето")
    due_date = models.DateField(verbose_name="Крайна дата")
    due_time = models.TimeField(null=True, blank=True, verbose_name="Час (по избор)")
    priority = models.CharField(max_length=15, choices=PRIORITY_CHOICES, default='normal', verbose_name="Приоритет")
    is_completed = models.BooleanField(default=False, verbose_name="Изпълнено")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата на изпълнение")
    notes = models.TextField(blank=True, verbose_name="Бележки / детайли")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Напомняне"
        verbose_name_plural = "Напомняния"
        ordering = ['is_completed', 'due_date', 'due_time']
        indexes = [
            models.Index(
                fields=['owner', 'is_completed', 'due_date'],
                name='reminder_owner_status_due_idx',
            ),
        ]

    def __str__(self):
        pet_str = f" за {self.pet.name}" if self.pet else ""
        return f"{self.title}{pet_str} ({self.due_date})"

    def save(self, *args, **kwargs):
        """Keep ``completed_at`` in sync with ``is_completed``.

        ``is_completed`` is the source of truth; the timestamp is derived so no
        caller can leave the two fields inconsistent.
        """
        if self.is_completed:
            if self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None
        super().save(*args, **kwargs)

    @property
    def days_until_due(self):
        return (self.due_date - date.today()).days

    @property
    def is_overdue(self):
        if self.is_completed:
            return False
        return self.days_until_due < 0

    @property
    def is_today(self):
        if self.is_completed:
            return False
        return self.days_until_due == 0

    @property
    def is_due_soon(self):
        if self.is_completed:
            return False
        return 0 <= self.days_until_due <= 7

    @property
    def type_icon(self):
        icons = {
            'vaccination': 'fa-solid fa-syringe text-emerald-600',
            'vet_visit': 'fa-solid fa-stethoscope text-blue-600',
            'medication': 'fa-solid fa-pills text-purple-600',
            'deworming': 'fa-solid fa-shield-virus text-amber-600',
            'grooming': 'fa-solid fa-shower text-teal-600',
            'food_refill': 'fa-solid fa-bowl-food text-orange-600',
            'other': 'fa-solid fa-bell text-gray-600',
        }
        return icons.get(self.reminder_type, 'fa-solid fa-bell text-gray-600')
