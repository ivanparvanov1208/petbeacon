from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from datetime import date, timedelta
from .models import Pet, Vaccination, MedicalRecord, Medication, VetVisit, Reminder
from .forms import (
    PetForm, VaccinationForm, MedicalRecordForm,
    MedicationForm, VetVisitForm, ReminderForm
)


def home_view(request):
    """Landing page for visitors."""
    if request.user.is_authenticated:
        return redirect('pets:dashboard')
    return render(request, 'pets/home.html')


@login_required
def dashboard_view(request):
    """Main dashboard for pet owners."""
    today = date.today()
    user_pets = Pet.objects.filter(owner=request.user)
    
    # Reminders
    user_reminders = Reminder.objects.filter(owner=request.user)
    overdue_reminders = user_reminders.filter(is_completed=False, due_date__lt=today).order_by('due_date')
    today_reminders = user_reminders.filter(is_completed=False, due_date=today).order_by('due_time')
    upcoming_reminders = user_reminders.filter(
        is_completed=False,
        due_date__gt=today,
        due_date__lte=today + timedelta(days=14)
    ).order_by('due_date', 'due_time')

    # Vaccinations alerts
    vaccinations_overdue = Vaccination.objects.filter(
        pet__owner=request.user,
        next_due_date__lt=today
    ).select_related('pet').order_by('next_due_date')

    vaccinations_due_soon = Vaccination.objects.filter(
        pet__owner=request.user,
        next_due_date__gte=today,
        next_due_date__lte=today + timedelta(days=30)
    ).select_related('pet').order_by('next_due_date')

    # Active medications
    active_meds = Medication.objects.filter(
        pet__owner=request.user,
        is_active=True
    ).select_related('pet').order_by('end_date')

    # Recent vet visits
    recent_visits = VetVisit.objects.filter(
        pet__owner=request.user
    ).select_related('pet').order_by('-visit_date')[:5]

    context = {
        'total_pets': user_pets.count(),
        'pets': user_pets[:6],
        'overdue_reminders': overdue_reminders,
        'today_reminders': today_reminders,
        'upcoming_reminders': upcoming_reminders,
        'vaccinations_overdue': vaccinations_overdue,
        'vaccinations_due_soon': vaccinations_due_soon,
        'active_meds': active_meds,
        'recent_visits': recent_visits,
        'today': today,
    }
    return render(request, 'pets/dashboard.html', context)


# --- PET CRUD ---

@login_required
def pet_list_view(request):
    pets = Pet.objects.filter(owner=request.user)
    
    query = request.GET.get('q', '').strip()
    species = request.GET.get('species', '').strip()

    if query:
        pets = pets.filter(
            Q(name__icontains=query) |
            Q(breed__icontains=query) |
            Q(microchip_number__icontains=query) |
            Q(passport_number__icontains=query)
        )

    if species and species != 'all':
        pets = pets.filter(species=species)

    context = {
        'pets': pets,
        'query': query,
        'selected_species': species,
        'species_choices': Pet.SPECIES_CHOICES,
    }
    return render(request, 'pets/pet_list.html', context)


@login_required
def pet_detail_view(request, pk):
    pet = get_object_or_404(Pet, pk=pk, owner=request.user)
    active_tab = request.GET.get('tab', 'overview')

    vaccinations = pet.vaccinations.all()
    medical_records = pet.medical_records.all()
    medications = pet.medications.all()
    vet_visits = pet.vet_visits.all()
    reminders = pet.reminders.all().order_by('is_completed', 'due_date')

    context = {
        'pet': pet,
        'active_tab': active_tab,
        'vaccinations': vaccinations,
        'medical_records': medical_records,
        'medications': medications,
        'vet_visits': vet_visits,
        'reminders': reminders,
    }
    return render(request, 'pets/pet_detail.html', context)


@login_required
def pet_create_view(request):
    if request.method == 'POST':
        form = PetForm(request.POST, request.FILES)
        if form.is_valid():
            pet = form.save(commit=False)
            pet.owner = request.user
            pet.save()
            messages.success(request, f"Успешно добавихте профил на {pet.name}!")
            return redirect('pets:pet_detail', pk=pet.pk)
    else:
        form = PetForm()

    return render(request, 'pets/pet_form.html', {
        'form': form,
        'title': 'Добавяне на нов домашен любимец',
        'button_text': 'Запази любимеца',
    })


@login_required
def pet_update_view(request, pk):
    pet = get_object_or_404(Pet, pk=pk, owner=request.user)

    if request.method == 'POST':
        form = PetForm(request.POST, request.FILES, instance=pet)
        if form.is_valid():
            form.save()
            messages.success(request, f"Данните за {pet.name} бяха обновени успешно!")
            return redirect('pets:pet_detail', pk=pet.pk)
    else:
        form = PetForm(instance=pet)

    return render(request, 'pets/pet_form.html', {
        'form': form,
        'pet': pet,
        'title': f'Редакция на профила на {pet.name}',
        'button_text': 'Запази промените',
    })


@login_required
def pet_delete_view(request, pk):
    pet = get_object_or_404(Pet, pk=pk, owner=request.user)

    if request.method == 'POST':
        name = pet.name
        pet.delete()
        messages.success(request, f"Профилът на {name} бе изтрит успешно.")
        return redirect('pets:pet_list')

    return render(request, 'pets/pet_confirm_delete.html', {'pet': pet})


@login_required
def pet_passport_view(request, pk):
    """Printable health passport / summary card for vet visits."""
    pet = get_object_or_404(Pet, pk=pk, owner=request.user)
    return render(request, 'pets/pet_passport_print.html', {
        'pet': pet,
        'vaccinations': pet.vaccinations.all(),
        'medications': pet.medications.all(),
        'medical_records': pet.medical_records.all(),
        'vet_visits': pet.vet_visits.all(),
        'today': date.today(),
    })


# --- VACCINATION CRUD ---

@login_required
def vaccination_create_view(request, pet_pk):
    pet = get_object_or_404(Pet, pk=pet_pk, owner=request.user)

    if request.method == 'POST':
        form = VaccinationForm(request.POST)
        if form.is_valid():
            vac = form.save(commit=False)
            vac.pet = pet
            vac.save()

            if form.cleaned_data.get('create_reminder') and vac.next_due_date:
                Reminder.objects.create(
                    owner=request.user,
                    pet=pet,
                    reminder_type='vaccination',
                    title=f"Ваксинация: {vac.name}",
                    due_date=vac.next_due_date,
                    priority='high',
                    notes=f"Следваща доза за {vac.name}. Предишна поставена на {vac.date_administered}."
                )

            messages.success(request, f"Ваксинацията '{vac.name}' бе добавена успешно за {pet.name}!")
            return redirect(f"/pets/{pet.pk}/?tab=vaccinations")
    else:
        form = VaccinationForm(initial={'date_administered': date.today()})

    return render(request, 'pets/vaccination_form.html', {
        'form': form,
        'pet': pet,
        'title': f'Добавяне на ваксинация за {pet.name}',
    })


@login_required
def vaccination_update_view(request, pk):
    vac = get_object_or_404(Vaccination, pk=pk, pet__owner=request.user)
    pet = vac.pet

    if request.method == 'POST':
        form = VaccinationForm(request.POST, instance=vac)
        if form.is_valid():
            form.save()
            messages.success(request, f"Ваксинацията '{vac.name}' бе обновена успешно!")
            return redirect(f"/pets/{pet.pk}/?tab=vaccinations")
    else:
        form = VaccinationForm(instance=vac)

    return render(request, 'pets/vaccination_form.html', {
        'form': form,
        'pet': pet,
        'vac': vac,
        'title': f'Редакция на ваксинация: {vac.name}',
    })


@login_required
def vaccination_delete_view(request, pk):
    vac = get_object_or_404(Vaccination, pk=pk, pet__owner=request.user)
    pet_pk = vac.pet.pk
    vac_name = vac.name
    vac.delete()
    messages.success(request, f"Ваксинацията '{vac_name}' бе изтрита.")
    return redirect(f"/pets/{pet_pk}/?tab=vaccinations")


# --- MEDICAL RECORD CRUD ---

@login_required
def medical_record_create_view(request, pet_pk):
    pet = get_object_or_404(Pet, pk=pet_pk, owner=request.user)

    if request.method == 'POST':
        form = MedicalRecordForm(request.POST, request.FILES)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.pet = pet
            rec.save()
            messages.success(request, f"Медицинският запис '{rec.title}' бе добавен успешно!")
            return redirect(f"/pets/{pet.pk}/?tab=records")
    else:
        form = MedicalRecordForm(initial={'date': date.today()})

    return render(request, 'pets/medical_record_form.html', {
        'form': form,
        'pet': pet,
        'title': f'Добавяне на медицински запис за {pet.name}',
    })


@login_required
def medical_record_update_view(request, pk):
    rec = get_object_or_404(MedicalRecord, pk=pk, pet__owner=request.user)
    pet = rec.pet

    if request.method == 'POST':
        form = MedicalRecordForm(request.POST, request.FILES, instance=rec)
        if form.is_valid():
            form.save()
            messages.success(request, f"Записът '{rec.title}' бе обновен успешно!")
            return redirect(f"/pets/{pet.pk}/?tab=records")
    else:
        form = MedicalRecordForm(instance=rec)

    return render(request, 'pets/medical_record_form.html', {
        'form': form,
        'pet': pet,
        'rec': rec,
        'title': f'Редакция на медицински запис: {rec.title}',
    })


@login_required
def medical_record_delete_view(request, pk):
    rec = get_object_or_404(MedicalRecord, pk=pk, pet__owner=request.user)
    pet_pk = rec.pet.pk
    rec_title = rec.title
    rec.delete()
    messages.success(request, f"Медицинският запис '{rec_title}' бе изтрит.")
    return redirect(f"/pets/{pet_pk}/?tab=records")


# --- MEDICATION CRUD ---

@login_required
def medication_create_view(request, pet_pk):
    pet = get_object_or_404(Pet, pk=pet_pk, owner=request.user)

    if request.method == 'POST':
        form = MedicationForm(request.POST)
        if form.is_valid():
            med = form.save(commit=False)
            med.pet = pet
            med.save()

            if form.cleaned_data.get('create_reminder'):
                Reminder.objects.create(
                    owner=request.user,
                    pet=pet,
                    reminder_type='medication',
                    title=f"Прием на лекарство: {med.name} ({med.dosage})",
                    due_date=med.start_date,
                    priority='high',
                    notes=f"Честота: {med.frequency}. {med.instructions}"
                )

            messages.success(request, f"Медикаментът '{med.name}' бе добавен успешно!")
            return redirect(f"/pets/{pet.pk}/?tab=meds")
    else:
        form = MedicationForm(initial={'start_date': date.today()})

    return render(request, 'pets/medication_form.html', {
        'form': form,
        'pet': pet,
        'title': f'Предписване на медикамент за {pet.name}',
    })


@login_required
def medication_update_view(request, pk):
    med = get_object_or_404(Medication, pk=pk, pet__owner=request.user)
    pet = med.pet

    if request.method == 'POST':
        form = MedicationForm(request.POST, instance=med)
        if form.is_valid():
            form.save()
            messages.success(request, f"Медикаментът '{med.name}' бе обновен успешно!")
            return redirect(f"/pets/{pet.pk}/?tab=meds")
    else:
        form = MedicationForm(instance=med)

    return render(request, 'pets/medication_form.html', {
        'form': form,
        'pet': pet,
        'med': med,
        'title': f'Редакция на медикамент: {med.name}',
    })


@login_required
def medication_toggle_active_view(request, pk):
    med = get_object_or_404(Medication, pk=pk, pet__owner=request.user)
    med.is_active = not med.is_active
    med.save()
    status_text = "активно" if med.is_active else "приключило"
    messages.success(request, f"Лекарството '{med.name}' е отбелязано като {status_text}.")
    return redirect(f"/pets/{med.pet.pk}/?tab=meds")


@login_required
def medication_delete_view(request, pk):
    med = get_object_or_404(Medication, pk=pk, pet__owner=request.user)
    pet_pk = med.pet.pk
    med_name = med.name
    med.delete()
    messages.success(request, f"Лекарството '{med_name}' бе изтрито.")
    return redirect(f"/pets/{pet_pk}/?tab=meds")


# --- VET VISIT CRUD ---

@login_required
def vet_visit_create_view(request, pet_pk):
    pet = get_object_or_404(Pet, pk=pet_pk, owner=request.user)

    if request.method == 'POST':
        form = VetVisitForm(request.POST)
        if form.is_valid():
            visit = form.save(commit=False)
            visit.pet = pet
            visit.save()
            messages.success(request, f"Ветеринарното посещение на {pet.name} бе записано успешно!")
            return redirect(f"/pets/{pet.pk}/?tab=visits")
    else:
        form = VetVisitForm(initial={'visit_date': date.today()})

    return render(request, 'pets/vet_visit_form.html', {
        'form': form,
        'pet': pet,
        'title': f'Записване на ветеринарно посещение за {pet.name}',
    })


@login_required
def vet_visit_update_view(request, pk):
    visit = get_object_or_404(VetVisit, pk=pk, pet__owner=request.user)
    pet = visit.pet

    if request.method == 'POST':
        form = VetVisitForm(request.POST, instance=visit)
        if form.is_valid():
            form.save()
            messages.success(request, "Ветеринарното посещение бе обновено успешно!")
            return redirect(f"/pets/{pet.pk}/?tab=visits")
    else:
        form = VetVisitForm(instance=visit)

    return render(request, 'pets/vet_visit_form.html', {
        'form': form,
        'pet': pet,
        'visit': visit,
        'title': f'Редакция на посещение от {visit.visit_date}',
    })


@login_required
def vet_visit_delete_view(request, pk):
    visit = get_object_or_404(VetVisit, pk=pk, pet__owner=request.user)
    pet_pk = visit.pet.pk
    visit.delete()
    messages.success(request, "Ветеринарното посещение бе изтрито.")
    return redirect(f"/pets/{pet_pk}/?tab=visits")


# --- REMINDERS CRUD ---

@login_required
def reminder_list_view(request):
    today = date.today()
    reminders = Reminder.objects.filter(owner=request.user)

    status_filter = request.GET.get('status', 'all')
    pet_filter = request.GET.get('pet', '')
    type_filter = request.GET.get('type', '')
    query = request.GET.get('q', '').strip()

    if query:
        reminders = reminders.filter(
            Q(title__icontains=query) |
            Q(notes__icontains=query) |
            Q(pet__name__icontains=query)
        )

    if pet_filter:
        reminders = reminders.filter(pet_id=pet_filter)

    if type_filter:
        reminders = reminders.filter(reminder_type=type_filter)

    if status_filter == 'overdue':
        reminders = reminders.filter(is_completed=False, due_date__lt=today).order_by('due_date')
    elif status_filter == 'today':
        reminders = reminders.filter(is_completed=False, due_date=today).order_by('due_time')
    elif status_filter == 'upcoming':
        reminders = reminders.filter(is_completed=False, due_date__gt=today).order_by('due_date')
    elif status_filter == 'completed':
        reminders = reminders.filter(is_completed=True).order_by('-completed_at', '-due_date')
    else:
        # Default all: uncompleted first, then completed
        reminders = reminders.order_by('is_completed', 'due_date', 'due_time')

    pets = Pet.objects.filter(owner=request.user)

    context = {
        'reminders': reminders,
        'status_filter': status_filter,
        'pet_filter': pet_filter,
        'type_filter': type_filter,
        'query': query,
        'pets': pets,
        'today': today,
        'type_choices': Reminder.TYPE_CHOICES,
    }
    return render(request, 'pets/reminder_list.html', context)


@login_required
def reminder_create_view(request):
    initial_data = {'due_date': date.today()}
    pet_id = request.GET.get('pet')
    if pet_id:
        initial_data['pet'] = pet_id

    if request.method == 'POST':
        form = ReminderForm(request.POST, user=request.user)
        if form.is_valid():
            rem = form.save(commit=False)
            rem.owner = request.user
            rem.save()
            messages.success(request, f"Напомнянето '{rem.title}' бе създадено успешно!")
            return redirect('pets:reminder_list')
    else:
        form = ReminderForm(user=request.user, initial=initial_data)

    return render(request, 'pets/reminder_form.html', {
        'form': form,
        'title': 'Създаване на ново напомняне',
        'button_text': 'Запази напомнянето',
    })


@login_required
def reminder_update_view(request, pk):
    rem = get_object_or_404(Reminder, pk=pk, owner=request.user)

    if request.method == 'POST':
        form = ReminderForm(request.POST, instance=rem, user=request.user)
        if form.is_valid():
            reminder = form.save()
            if reminder.is_completed and not reminder.completed_at:
                reminder.completed_at = timezone.now()
                reminder.save()
            elif not reminder.is_completed:
                reminder.completed_at = None
                reminder.save()
            messages.success(request, f"Напомнянето '{rem.title}' бе обновено!")
            return redirect('pets:reminder_list')
    else:
        form = ReminderForm(instance=rem, user=request.user)

    return render(request, 'pets/reminder_form.html', {
        'form': form,
        'rem': rem,
        'title': f'Редакция на напомняне: {rem.title}',
        'button_text': 'Запази промените',
    })


@login_required
def reminder_toggle_complete_view(request, pk):
    rem = get_object_or_404(Reminder, pk=pk, owner=request.user)
    rem.is_completed = not rem.is_completed
    if rem.is_completed:
        rem.completed_at = timezone.now()
        messages.success(request, f"Напомнянето '{rem.title}' бе отбелязано като изпълнено! Браво!")
    else:
        rem.completed_at = None
        messages.info(request, f"Напомнянето '{rem.title}' бе върнато като активно.")
    rem.save()

    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('pets:reminder_list')


@login_required
def reminder_delete_view(request, pk):
    rem = get_object_or_404(Reminder, pk=pk, owner=request.user)
    title = rem.title
    rem.delete()
    messages.success(request, f"Напомнянето '{title}' бе изтрито.")
    return redirect('pets:reminder_list')
