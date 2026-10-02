from django import forms
from django.contrib import admin
from .models import Pet, Vaccination, MedicalRecord, Medication, VetVisit, Reminder


class VaccinationInline(admin.TabularInline):
    model = Vaccination
    extra = 0


class MedicalRecordInline(admin.TabularInline):
    model = MedicalRecord
    extra = 0


class MedicationInline(admin.TabularInline):
    model = Medication
    extra = 0


class VetVisitInline(admin.TabularInline):
    model = VetVisit
    extra = 0


class ReminderInlineForm(forms.ModelForm):
    """Inline form that leaves ``owner`` out.

    ``Reminder.owner`` is a non-nullable FK to ``User``. Exposing it inside the
    Pet inline would be meaningless (the owner is whoever the pet belongs to),
    but omitting it without filling it in makes every inline save attempt
    ``owner = NULL``. The value is assigned in ``PetAdmin.save_formset``.
    """

    class Meta:
        model = Reminder
        exclude = ('owner',)


class ReminderInline(admin.TabularInline):
    model = Reminder
    form = ReminderInlineForm
    extra = 0
    autocomplete_fields = ('pet',)


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ('name', 'species', 'breed', 'gender', 'owner', 'birth_date', 'weight', 'is_neutered')
    list_filter = ('species', 'gender', 'is_neutered')
    search_fields = ('name', 'breed', 'microchip_number', 'passport_number', 'owner__username')
    list_select_related = ('owner',)
    inlines = [VaccinationInline, MedicalRecordInline, MedicationInline, VetVisitInline, ReminderInline]

    def save_formset(self, request, form, formset, change):
        """Assign the reminder owner before the formset writes the rows.

        Note this must live on the ``ModelAdmin``: Django calls
        ``ModelAdmin.save_formset`` for *every* inline formset, so a
        ``save_formset`` defined on the inline itself is never invoked.
        """
        if formset.model is Reminder:
            for reminder_form in formset.forms:
                instance = reminder_form.instance
                if instance.owner_id is None:
                    instance.owner_id = request.user.pk
        super().save_formset(request, form, formset, change)


@admin.register(Vaccination)
class VaccinationAdmin(admin.ModelAdmin):
    list_display = ('name', 'pet', 'date_administered', 'next_due_date', 'clinic_or_vet', 'batch_number')
    list_filter = ('date_administered', 'next_due_date')
    search_fields = ('name', 'pet__name', 'clinic_or_vet', 'batch_number')
    list_select_related = ('pet',)
    autocomplete_fields = ('pet',)


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('title', 'pet', 'date', 'veterinarian', 'clinic', 'cost')
    list_filter = ('date', 'clinic')
    search_fields = ('title', 'diagnosis', 'treatment', 'pet__name', 'veterinarian')
    list_select_related = ('pet',)
    autocomplete_fields = ('pet',)


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'pet', 'dosage', 'frequency', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'start_date')
    search_fields = ('name', 'pet__name', 'instructions')
    list_select_related = ('pet',)
    autocomplete_fields = ('pet',)


@admin.register(VetVisit)
class VetVisitAdmin(admin.ModelAdmin):
    list_display = ('pet', 'visit_date', 'clinic_name', 'vet_name', 'reason', 'total_cost')
    list_filter = ('visit_date', 'clinic_name')
    search_fields = ('pet__name', 'clinic_name', 'vet_name', 'reason')
    list_select_related = ('pet',)
    autocomplete_fields = ('pet',)


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'pet', 'reminder_type', 'due_date', 'due_time', 'priority', 'is_completed')
    list_filter = ('is_completed', 'reminder_type', 'priority', 'due_date')
    search_fields = ('title', 'pet__name', 'owner__username', 'notes')
    list_select_related = ('owner', 'pet')
    autocomplete_fields = ('owner', 'pet')
    readonly_fields = ('completed_at',)
