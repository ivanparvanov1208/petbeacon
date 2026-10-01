from django.contrib import admin
from .models import Pet, Vaccination, MedicalRecord, Medication, VetVisit, Reminder


class VaccinationInline(admin.TabularInline):
    model = Vaccination
    extra = 1


class MedicalRecordInline(admin.TabularInline):
    model = MedicalRecord
    extra = 1


class MedicationInline(admin.TabularInline):
    model = Medication
    extra = 1


class VetVisitInline(admin.TabularInline):
    model = VetVisit
    extra = 1


class ReminderInline(admin.TabularInline):
    model = Reminder
    extra = 1


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ('name', 'species', 'breed', 'gender', 'owner', 'birth_date', 'weight', 'is_neutered')
    list_filter = ('species', 'gender', 'is_neutered')
    search_fields = ('name', 'breed', 'microchip_number', 'passport_number', 'owner__username')
    inlines = [VaccinationInline, MedicalRecordInline, MedicationInline, VetVisitInline, ReminderInline]


@admin.register(Vaccination)
class VaccinationAdmin(admin.ModelAdmin):
    list_display = ('name', 'pet', 'date_administered', 'next_due_date', 'clinic_or_vet', 'batch_number')
    list_filter = ('date_administered', 'next_due_date')
    search_fields = ('name', 'pet__name', 'clinic_or_vet', 'batch_number')


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('title', 'pet', 'date', 'veterinarian', 'clinic', 'cost')
    list_filter = ('date', 'clinic')
    search_fields = ('title', 'diagnosis', 'treatment', 'pet__name', 'veterinarian')


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'pet', 'dosage', 'frequency', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'start_date')
    search_fields = ('name', 'pet__name', 'instructions')


@admin.register(VetVisit)
class VetVisitAdmin(admin.ModelAdmin):
    list_display = ('pet', 'visit_date', 'clinic_name', 'vet_name', 'reason', 'total_cost')
    list_filter = ('visit_date', 'clinic_name')
    search_fields = ('pet__name', 'clinic_name', 'vet_name', 'reason')


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'pet', 'reminder_type', 'due_date', 'due_time', 'priority', 'is_completed')
    list_filter = ('is_completed', 'reminder_type', 'priority', 'due_date')
    search_fields = ('title', 'pet__name', 'owner__username', 'notes')
