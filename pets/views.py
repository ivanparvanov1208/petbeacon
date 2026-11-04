from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import date, timedelta
import logging
from .models import (
    Pet, Vaccination, MedicalRecord, Medication, VetVisit, Reminder,
    Consultation, ConsultationMessage,
)
from .forms import (
    PetForm, VaccinationForm, MedicalRecordForm,
    MedicationForm, VetVisitForm, ReminderForm,
    ConsultationRequestForm, ConsultationMessageForm,
)
from accounts.models import UserProfile

PETS_PER_PAGE = 12
REMINDERS_PER_PAGE = 20

UPCOMING_REMINDER_DAYS = 14
DUE_SOON_VACCINATION_DAYS = 30
logger = logging.getLogger(__name__)


def _safe_next_url(request, fallback):
    candidate = request.POST.get('next') or request.GET.get('next') or ''
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


def _pet_detail_url(pet_pk, tab=None):
    url = reverse('pets:pet_detail', kwargs={'pk': pet_pk})
    return f"{url}?tab={tab}" if tab else url


def home_view(request):
    if request.user.is_authenticated:
        return redirect('pets:dashboard')

    features = [
        ('fa-solid fa-id-card', 'brand',
         _('Клинично досие на пациента'),
         _('Основна информация, идентификация, алергии и важни особености за пациента.')),
        ('fa-solid fa-syringe', 'blue',
         _('Медицинска история'),
         _('Прегледайте ваксинациите, диагнозите, процедурите и приложените изследвания.')),
        ('fa-solid fa-bell', 'purple',
         _('Документиране на прегледи'),
         _('Записвайте резултати, диагнози, лечение и препоръки след всяко посещение.')),
        ('fa-solid fa-file-medical', 'amber',
         _('Медицинска история'),
         _('Поддържайте подредена история на прегледите и разходите с прикачени резултати.')),
        ('fa-solid fa-pills', 'rose',
         _('Прием на лекарства'),
         _('Записвайте предписани медикаменти, дозировки, честота и указания за прием.')),
        ('fa-solid fa-print', 'emerald',
         _('Електронен здравен паспорт'),
         _('Подгответе обобщение на здравното досие за собственика и следващия преглед.')),
        ('fa-solid fa-comments', 'purple',
         _('Платена онлайн консултация'),
         _('Свържете стопанина с избран ветеринар в личен чат, с checkout и история на разговора.')),
    ]

    return render(request, 'pets/home.html', {'features': features})


@login_required
def dashboard_view(request):
    today = date.today()
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    user_pets = Pet.objects.filter(owner=request.user)

    if profile.is_vet:
        # Veterinarian accounts manage patient records registered under their account.
        vet_visits = VetVisit.objects.filter(pet__owner=request.user)
        followups = Reminder.objects.filter(
            owner=request.user, is_completed=False, due_date__gte=today,
            due_date__lte=today + timedelta(days=30),
        )
        context = {
            'is_vet_dashboard': True,
            'total_pets': user_pets.count(),
            'pets': user_pets.order_by('-created_at', 'name')[:8],
            'visit_count': vet_visits.count(),
            'recent_visits': vet_visits.select_related('pet').order_by('-visit_date')[:8],
            'followup_count': followups.count(),
            'upcoming_followups': followups.select_related('pet').order_by('due_date')[:8],
            'today': today,
        }
        return render(request, 'pets/vet_dashboard.html', context)

    base_reminders = Reminder.objects.filter(
        owner=request.user, is_completed=False
    ).select_related('pet')
    overdue_reminders = base_reminders.filter(due_date__lt=today).order_by('due_date')
    today_reminders = base_reminders.filter(due_date=today).order_by('due_time')
    upcoming_reminders = base_reminders.filter(
        due_date__gt=today,
        due_date__lte=today + timedelta(days=UPCOMING_REMINDER_DAYS)
    ).order_by('due_date', 'due_time')


    base_vaccinations = Vaccination.objects.filter(pet__owner=request.user)
    vaccinations_overdue = base_vaccinations.filter(
        next_due_date__lt=today
    ).select_related('pet').order_by('next_due_date')

    vaccinations_due_soon = base_vaccinations.filter(
        next_due_date__gte=today,
        next_due_date__lte=today + timedelta(days=DUE_SOON_VACCINATION_DAYS)
    ).select_related('pet').order_by('next_due_date')

    active_meds = Medication.objects.filter(
        pet__owner=request.user,
        is_active=True
    ).select_related('pet').order_by('end_date')

    recent_visits = VetVisit.objects.filter(
        pet__owner=request.user
    ).select_related('pet').order_by('-visit_date')[:5]

    urgent_total = overdue_reminders.count() + vaccinations_overdue.count()

    context = {
        'total_pets': user_pets.count(),
        'pets': user_pets[:6],
        'urgent_total': urgent_total,
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


@login_required
def consultation_list_view(request):
    profile, _created = UserProfile.objects.get_or_create(user=request.user)
    if profile.is_vet:
        consultations = Consultation.objects.filter(veterinarian=request.user)
    else:
        consultations = Consultation.objects.filter(owner=request.user)
    return render(request, 'pets/consultation_list.html', {
        'consultations': consultations.select_related('pet', 'owner', 'veterinarian'),
        'is_vet': profile.is_vet,
    })


@login_required
def consultation_create_view(request):
    profile, _created = UserProfile.objects.get_or_create(user=request.user)
    if profile.is_vet:
        messages.error(request, _('Само стопанин може да заяви консултация.'))
        return redirect('pets:consultation_list')
    if request.method == 'POST':
        form = ConsultationRequestForm(request.POST, owner=request.user)
        if form.is_valid():
            consultation = form.save(commit=False)
            consultation.owner = request.user
            consultation.status = Consultation.STATUS_PENDING_PAYMENT
            consultation.payment_status = Consultation.PAYMENT_PENDING
            consultation.save()
            return redirect('pets:consultation_detail', pk=consultation.pk)
    else:
        form = ConsultationRequestForm(owner=request.user)
    return render(request, 'pets/consultation_request.html', {
        'form': form,
        'cancel_url': reverse('pets:consultation_list'),
    })


def _stripe_client():
    import os
    import stripe
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')
    if not stripe.api_key:
        raise RuntimeError('STRIPE_SECRET_KEY is not configured.')
    return stripe


@login_required
@require_POST
def consultation_checkout_view(request, pk):
    consultation = get_object_or_404(Consultation, pk=pk, owner=request.user)
    if consultation.status != Consultation.STATUS_PENDING_PAYMENT:
        return redirect('pets:consultation_detail', pk=pk)
    try:
        stripe = _stripe_client()
        coupon = stripe.Coupon.create(
            percent_off=100,
            duration='once',
            name='PetBeacon demo 100% off',
            metadata={'consultation_id': str(consultation.pk)},
        )
        success_url = request.build_absolute_uri(
            reverse('pets:consultation_checkout_success', kwargs={'pk': pk})
        ) + '?session_id={CHECKOUT_SESSION_ID}'
        cancel_url = request.build_absolute_uri(
            reverse('pets:consultation_detail', kwargs={'pk': pk})
        )
        session = stripe.checkout.Session.create(
            mode='payment',
            customer_email=request.user.email or None,
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': consultation.listed_price_cents,
                    'product_data': {
                        'name': 'Online veterinary consultation',
                        'description': f"{consultation.subject} · {consultation.pet.name}",
                    },
                },
                'quantity': 1,
            }],
            discounts=[{'coupon': coupon.id}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={'consultation_id': str(consultation.pk), 'owner_id': str(request.user.pk)},
        )
        consultation.stripe_session_id = session.id
        consultation.save(update_fields=['stripe_session_id', 'updated_at'])
        return redirect(session.url)
    except Exception:
        logger.exception('Could not create Stripe Checkout session for consultation %s.', pk)
        messages.error(request, _('Неуспешно създаване на Stripe Checkout. Проверете тестовия Stripe ключ и опитайте отново.'))
        return redirect('pets:consultation_detail', pk=pk)


def _stripe_field(resource, name, default=None):
    """Read a field from StripeObject resources or ordinary dictionaries."""
    if isinstance(resource, dict):
        return resource.get(name, default)
    return getattr(resource, name, default)


def _complete_consultation_from_session(session):
    metadata = _stripe_field(session, 'metadata', {}) or {}
    consultation_id = _stripe_field(metadata, 'consultation_id')
    if not consultation_id:
        return
    consultation = Consultation.objects.filter(pk=consultation_id).first()
    if not consultation or _stripe_field(session, 'id') != consultation.stripe_session_id:
        return
    payment_status = _stripe_field(session, 'payment_status')
    if payment_status == 'paid':
        consultation.payment_status = Consultation.PAYMENT_PAID
    elif payment_status == 'no_payment_required':
        consultation.payment_status = Consultation.PAYMENT_COMPED
    else:
        return
    consultation.status = Consultation.STATUS_OPEN
    consultation.save(update_fields=['payment_status', 'status', 'updated_at'])


@login_required
def consultation_checkout_success_view(request, pk):
    consultation = get_object_or_404(Consultation, pk=pk, owner=request.user)
    session_id = request.GET.get('session_id', '')
    if session_id and session_id == consultation.stripe_session_id:
        try:
            stripe = _stripe_client()
            session = stripe.checkout.Session.retrieve(session_id)
            _complete_consultation_from_session(session)
        except Exception:
            messages.info(request, _('Плащането се потвърждава. Обновете страницата след малко.'))
    return redirect('pets:consultation_detail', pk=pk)


@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    import os
    try:
        stripe = _stripe_client()
        event = stripe.Webhook.construct_event(
            request.body,
            request.META.get('HTTP_STRIPE_SIGNATURE', ''),
            os.environ.get('STRIPE_WEBHOOK_SECRET', ''),
        )
    except Exception:
        return HttpResponseBadRequest('Invalid Stripe webhook.')
    if _stripe_field(event, 'type') == 'checkout.session.completed':
        event_data = _stripe_field(event, 'data', {})
        session = _stripe_field(event_data, 'object', {})
        _complete_consultation_from_session(session)
    return HttpResponse(status=200)


@login_required
def consultation_detail_view(request, pk):
    consultation = get_object_or_404(
        Consultation.objects.select_related('owner', 'veterinarian', 'pet'), pk=pk
    )
    if request.user.pk not in (consultation.owner_id, consultation.veterinarian_id):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    if request.method == 'POST':
        form = ConsultationMessageForm(request.POST)
        if form.is_valid():
            if consultation.status != Consultation.STATUS_OPEN:
                messages.error(request, _('Чатът не е отворен за съобщения.'))
            else:
                message = form.save(commit=False)
                message.consultation = consultation
                message.sender = request.user
                message.save()
                consultation.save(update_fields=['updated_at'])
                return redirect('pets:consultation_detail', pk=pk)
    else:
        form = ConsultationMessageForm()
    return render(request, 'pets/consultation_detail.html', {
        'consultation': consultation,
        'chat_messages': consultation.messages.select_related('sender'),
        'form': form,
        'is_vet': request.user.pk == consultation.veterinarian_id,
    })


@login_required
@require_POST
def consultation_close_view(request, pk):
    consultation = get_object_or_404(Consultation, pk=pk, veterinarian=request.user)
    consultation.status = Consultation.STATUS_CLOSED
    consultation.closed_at = timezone.now()
    consultation.save(update_fields=['status', 'closed_at', 'updated_at'])
    messages.success(request, _('Консултацията е приключена.'))
    return redirect('pets:consultation_detail', pk=pk)


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

    pets = pets.annotate(
        vaccination_count=Count('vaccinations', distinct=True),
        record_count=Count('medical_records', distinct=True),
    ).order_by('name')

    paginator = Paginator(pets, PETS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'pets': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'query': query,
        'selected_species': species,
        'species_choices': Pet.SPECIES_CHOICES,
        'filter_qs': request.GET.copy(),
    }
    return render(request, 'pets/pet_list.html', context)


@login_required
def pet_detail_view(request, pk):
    pet = get_object_or_404(Pet, pk=pk, owner=request.user)
    valid_tabs = {'overview', 'vaccinations', 'records', 'meds', 'visits', 'reminders'}
    active_tab = request.GET.get('tab', 'overview')
    if active_tab not in valid_tabs:
        active_tab = 'overview'

    vaccinations = pet.vaccinations.all()
    medical_records = pet.medical_records.all()
    medications = pet.medications.all()
    vet_visits = pet.vet_visits.all()
    reminders = pet.reminders.all().order_by('is_completed', 'due_date', 'due_time')

    tabs = [
        ('overview', _('Общ преглед'), 'fa-solid fa-clipboard-list', None),
        ('vaccinations', _('Ваксинации'), 'fa-solid fa-syringe', vaccinations.count()),
        ('records', _('Медицинска история'), 'fa-solid fa-file-medical', medical_records.count()),
        ('meds', _('Лекарства'), 'fa-solid fa-pills', medications.count()),
        ('visits', _('Визити'), 'fa-solid fa-stethoscope', vet_visits.count()),
        ('reminders', _('Напомняния'), 'fa-solid fa-bell', reminders.count()),
    ]

    facts = [
        (_('Възраст'), pet.age_display, 'fa-regular fa-clock'),
        (_('Тегло'), _('%(weight)s кг') % {"weight": pet.weight} if pet.weight
         else _('Не е въведено'), 'fa-solid fa-weight-hanging'),
        (_('Пол'), pet.get_gender_display(), 'fa-solid fa-venus-mars'),
        (_('Кастрация'), _('Да') if pet.is_neutered else _('Не'), 'fa-solid fa-shield-halved'),
    ]

    name = pet.name
    context = {
        'pet': pet,
        'active_tab': active_tab,
        'vaccinations': vaccinations,
        'medical_records': medical_records,
        'medications': medications,
        'vet_visits': vet_visits,
        'reminders': reminders,
        'tabs': tabs,
        'facts': facts,
        'empty_vaccinations': _('Все още няма въведени ваксинации за %(name)s.') % {"name": name},
        'empty_records': _('Няма въведени медицински записи за %(name)s.') % {"name": name},
        'empty_meds': _('Няма регистрирани медикаменти за %(name)s.') % {"name": name},
        'empty_visits': _('Няма записани посещения за %(name)s.') % {"name": name},
        'empty_reminders': _('Няма създадени напомняния за %(name)s.') % {"name": name},
        'record_create_url': reverse('pets:medical_record_create', args=[pet.pk]),
        'medication_create_url': reverse('pets:medication_create', args=[pet.pk]),
        'visit_create_url': reverse('pets:vet_visit_create', args=[pet.pk]),
        'pet_reminder_create_url': f"{reverse('pets:reminder_create')}?pet={pet.pk}",
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
            messages.success(request, _("Успешно добавихте профил на %(name)s!") % {"name": pet.name})
            return redirect('pets:pet_detail', pk=pet.pk)
    else:
        form = PetForm()

    return render(request, 'pets/pet_form.html', {
        'form': form,
        'title': _('Добавяне на нов домашен любимец'),
        'button_text': _('Запази любимеца'),
        'cancel_url': reverse('pets:pet_list'),
    })


@login_required
def pet_update_view(request, pk):
    pet = get_object_or_404(Pet, pk=pk, owner=request.user)

    if request.method == 'POST':
        form = PetForm(request.POST, request.FILES, instance=pet)
        if form.is_valid():
            form.save()
            messages.success(request, _("Данните за %(name)s бяха обновени успешно!") % {"name": pet.name})
            return redirect('pets:pet_detail', pk=pet.pk)
    else:
        form = PetForm(instance=pet)

    return render(request, 'pets/pet_form.html', {
        'form': form,
        'pet': pet,
        'title': _('Редакция на профила на %(name)s') % {"name": pet.name},
        'button_text': _('Запази промените'),
        'cancel_url': _pet_detail_url(pet.pk),
    })


@login_required
def pet_delete_view(request, pk):
    pet = get_object_or_404(Pet, pk=pk, owner=request.user)

    if request.method == 'POST':
        name = pet.name
        pet.delete()
        messages.success(request, _("Профилът на %(name)s бе изтрит успешно.") % {"name": name})
        return redirect('pets:pet_list')

    return render(request, 'pets/pet_confirm_delete.html', {
        'pet': pet,
        'related': {
            'vaccinations': pet.vaccinations.count(),
            'records': pet.medical_records.count(),
            'medications': pet.medications.count(),
            'visits': pet.vet_visits.count(),
            'reminders': pet.reminders.count(),
        },
    })


@login_required
def pet_passport_view(request, pk):
    pet = get_object_or_404(Pet, pk=pk, owner=request.user)
    return render(request, 'pets/pet_passport_print.html', {
        'pet': pet,
        'vaccinations': pet.vaccinations.all(),
        'medications': pet.medications.all(),
        'medical_records': pet.medical_records.all(),
        'vet_visits': pet.vet_visits.all(),
        'today': date.today(),
    })


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
                    title=_("Ваксинация: %(name)s") % {"name": vac.name},
                    due_date=vac.next_due_date,
                    priority='high',
                    notes=_("Следваща доза за %(vaccine)s. Предишна поставена на %(date)s.")
                    % {"vaccine": vac.name, "date": vac.date_administered},
                )

            messages.success(
                request,
                _("Ваксинацията '%(vaccine)s' бе добавена успешно за %(pet)s!")
                % {"vaccine": vac.name, "pet": pet.name},
            )
            return redirect(_pet_detail_url(pet.pk, tab="vaccinations"))
    else:
        form = VaccinationForm(initial={'date_administered': date.today()})

    return render(request, 'pets/vaccination_form.html', {
        'form': form,
        'pet': pet,
        'title': _('Добавяне на ваксинация за %(name)s') % {"name": pet.name},
        'subtitle': _('Ваксинационен запис за %(name)s') % {"name": pet.name},
        'cancel_url': _pet_detail_url(pet.pk, tab="vaccinations"),
    })


@login_required
def vaccination_update_view(request, pk):
    vac = get_object_or_404(Vaccination, pk=pk, pet__owner=request.user)
    pet = vac.pet

    if request.method == 'POST':
        form = VaccinationForm(request.POST, instance=vac)
        if form.is_valid():
            form.save()
            messages.success(request, _("Ваксинацията '%(name)s' бе обновена успешно!") % {"name": vac.name})
            return redirect(_pet_detail_url(pet.pk, tab="vaccinations"))
    else:
        form = VaccinationForm(instance=vac)

    return render(request, 'pets/vaccination_form.html', {
        'form': form,
        'pet': pet,
        'vac': vac,
        'title': _('Редакция на ваксинация: %(name)s') % {"name": vac.name},
        'subtitle': _('Ваксинационен запис за %(name)s') % {"name": pet.name},
        'cancel_url': _pet_detail_url(pet.pk, tab="vaccinations"),
    })


@login_required
@require_POST
def vaccination_delete_view(request, pk):
    vac = get_object_or_404(Vaccination, pk=pk, pet__owner=request.user)
    pet_pk = vac.pet.pk
    vac_name = vac.name
    vac.delete()
    messages.success(request, _("Ваксинацията '%(name)s' бе изтрита.") % {"name": vac_name})
    return redirect(_pet_detail_url(pet_pk, tab="vaccinations"))


@login_required
def medical_record_create_view(request, pet_pk):
    pet = get_object_or_404(Pet, pk=pet_pk, owner=request.user)

    if request.method == 'POST':
        form = MedicalRecordForm(request.POST, request.FILES)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.pet = pet
            rec.save()
            messages.success(request, _("Медицинският запис '%(title)s' бе добавен успешно!") % {"title": rec.title})
            return redirect(_pet_detail_url(pet.pk, tab="records"))
    else:
        form = MedicalRecordForm(initial={'date': date.today()})

    return render(request, 'pets/medical_record_form.html', {
        'form': form,
        'pet': pet,
        'title': _('Добавяне на медицински запис за %(name)s') % {"name": pet.name},
        'subtitle': _('Медицински запис за %(name)s') % {"name": pet.name},
        'cancel_url': _pet_detail_url(pet.pk, tab="records"),
    })


@login_required
def medical_record_update_view(request, pk):
    rec = get_object_or_404(MedicalRecord, pk=pk, pet__owner=request.user)
    pet = rec.pet

    if request.method == 'POST':
        form = MedicalRecordForm(request.POST, request.FILES, instance=rec)
        if form.is_valid():
            form.save()
            messages.success(request, _("Записът '%(title)s' бе обновен успешно!") % {"title": rec.title})
            return redirect(_pet_detail_url(pet.pk, tab="records"))
    else:
        form = MedicalRecordForm(instance=rec)

    return render(request, 'pets/medical_record_form.html', {
        'form': form,
        'pet': pet,
        'rec': rec,
        'title': _('Редакция на медицински запис: %(title)s') % {"title": rec.title},
        'subtitle': _('Медицински запис за %(name)s') % {"name": pet.name},
        'cancel_url': _pet_detail_url(pet.pk, tab="records"),
    })


@login_required
@require_POST
def medical_record_delete_view(request, pk):
    rec = get_object_or_404(MedicalRecord, pk=pk, pet__owner=request.user)
    pet_pk = rec.pet.pk
    rec_title = rec.title
    rec.delete()
    messages.success(request, _("Медицинският запис '%(title)s' бе изтрит.") % {"title": rec_title})
    return redirect(_pet_detail_url(pet_pk, tab="records"))


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
                    title=_("Прием на лекарство: %(name)s (%(dosage)s)")
                    % {"name": med.name, "dosage": med.dosage},
                    due_date=med.start_date,
                    priority='high',
                    notes=_("Честота: %(frequency)s. %(instructions)s")
                    % {"frequency": med.frequency, "instructions": med.instructions},
                )

            messages.success(request, _("Медикаментът '%(name)s' бе добавен успешно!") % {"name": med.name})
            return redirect(_pet_detail_url(pet.pk, tab="meds"))
    else:
        form = MedicationForm(initial={'start_date': date.today()})

    return render(request, 'pets/medication_form.html', {
        'form': form,
        'pet': pet,
        'title': _('Предписване на медикамент за %(name)s') % {"name": pet.name},
        'subtitle': _('Прием на лекарство за %(name)s') % {"name": pet.name},
        'cancel_url': _pet_detail_url(pet.pk, tab="meds"),
    })


@login_required
def medication_update_view(request, pk):
    med = get_object_or_404(Medication, pk=pk, pet__owner=request.user)
    pet = med.pet

    if request.method == 'POST':
        form = MedicationForm(request.POST, instance=med)
        if form.is_valid():
            form.save()
            messages.success(request, _("Медикаментът '%(name)s' бе обновен успешно!") % {"name": med.name})
            return redirect(_pet_detail_url(pet.pk, tab="meds"))
    else:
        form = MedicationForm(instance=med)

    return render(request, 'pets/medication_form.html', {
        'form': form,
        'pet': pet,
        'med': med,
        'title': _('Редакция на медикамент: %(name)s') % {"name": med.name},
        'subtitle': _('Прием на лекарство за %(name)s') % {"name": pet.name},
        'cancel_url': _pet_detail_url(pet.pk, tab="meds"),
    })


@login_required
@require_POST
def medication_toggle_active_view(request, pk):
    med = get_object_or_404(Medication, pk=pk, pet__owner=request.user)
    med.is_active = not med.is_active
    med.save(update_fields=['is_active'])
    if med.is_active:
        messages.success(request, _("Лекарството '%(name)s' е отбелязано като активно.") % {"name": med.name})
    else:
        messages.success(request, _("Лекарството '%(name)s' е отбелязано като приключило.") % {"name": med.name})
    return redirect(_safe_next_url(
        request,
        _pet_detail_url(med.pet.pk, tab="meds"),
    ))


@login_required
@require_POST
def medication_delete_view(request, pk):
    med = get_object_or_404(Medication, pk=pk, pet__owner=request.user)
    pet_pk = med.pet.pk
    med_name = med.name
    med.delete()
    messages.success(request, _("Лекарството '%(name)s' бе изтрито.") % {"name": med_name})
    return redirect(_pet_detail_url(pet_pk, tab="meds"))


@login_required
def vet_visit_create_view(request, pet_pk):
    pet = get_object_or_404(Pet, pk=pet_pk, owner=request.user)

    if request.method == 'POST':
        form = VetVisitForm(request.POST)
        if form.is_valid():
            visit = form.save(commit=False)
            visit.pet = pet
            visit.save()
            messages.success(request, _("Ветеринарното посещение на %(name)s бе записано успешно!") % {"name": pet.name})
            return redirect(_pet_detail_url(pet.pk, tab="visits"))
    else:
        form = VetVisitForm(initial={'visit_date': date.today()})

    return render(request, 'pets/vet_visit_form.html', {
        'form': form,
        'pet': pet,
        'title': _('Записване на ветеринарно посещение за %(name)s') % {"name": pet.name},
        'subtitle': _('Посещение при ветеринарен лекар за %(name)s') % {"name": pet.name},
        'cancel_url': _pet_detail_url(pet.pk, tab="visits"),
    })


@login_required
def vet_visit_update_view(request, pk):
    visit = get_object_or_404(VetVisit, pk=pk, pet__owner=request.user)
    pet = visit.pet

    if request.method == 'POST':
        form = VetVisitForm(request.POST, instance=visit)
        if form.is_valid():
            form.save()
            messages.success(request, _("Ветеринарното посещение бе обновено успешно!"))
            return redirect(_pet_detail_url(pet.pk, tab="visits"))
    else:
        form = VetVisitForm(instance=visit)

    return render(request, 'pets/vet_visit_form.html', {
        'form': form,
        'pet': pet,
        'visit': visit,
        'title': _('Редакция на посещение от %(date)s') % {"date": visit.visit_date},
        'subtitle': _('Посещение при ветеринарен лекар за %(name)s') % {"name": pet.name},
        'cancel_url': _pet_detail_url(pet.pk, tab="visits"),
    })


@login_required
@require_POST
def vet_visit_delete_view(request, pk):
    visit = get_object_or_404(VetVisit, pk=pk, pet__owner=request.user)
    pet_pk = visit.pet.pk
    visit.delete()
    messages.success(request, _("Ветеринарното посещение бе изтрито."))
    return redirect(_pet_detail_url(pet_pk, tab="visits"))


@login_required
def reminder_list_view(request):
    today = date.today()
    # Load pet relations with the reminders to avoid per-row template queries.
    reminders = Reminder.objects.filter(owner=request.user).select_related('pet')

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

    if pet_filter.isdigit():
        reminders = reminders.filter(pet_id=pet_filter)
    else:
        pet_filter = ''

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
        reminders = reminders.order_by('is_completed', 'due_date', 'due_time')

    paginator = Paginator(reminders, REMINDERS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    has_active_filters = bool(query or pet_filter or type_filter or status_filter != 'all')

    context = {
        'reminders': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'status_filter': status_filter,
        'pet_filter': pet_filter,
        'type_filter': type_filter,
        'query': query,
        'pets': Pet.objects.filter(owner=request.user),
        'today': today,
        'type_choices': Reminder.TYPE_CHOICES,
        'empty_body': (
            _('Няма напомняния, отговарящи на избраните филтри.')
            if has_active_filters else
            _('Все още нямате планирани напомняния. Добавете напомняне за ваксина, '
              'лекарство или преглед!')
        ),
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
            messages.success(request, _("Напомнянето '%(title)s' бе създадено успешно!") % {"title": rem.title})
            return redirect('pets:reminder_list')
    else:
        form = ReminderForm(user=request.user, initial=initial_data)

    return render(request, 'pets/reminder_form.html', {
        'form': form,
        'title': _('Създаване на ново напомняне'),
        'button_text': _('Запази напомнянето'),
        'cancel_url': reverse('pets:reminder_list'),
    })


@login_required
def reminder_update_view(request, pk):
    rem = get_object_or_404(Reminder, pk=pk, owner=request.user)

    if request.method == 'POST':
        form = ReminderForm(request.POST, instance=rem, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Напомнянето '%(title)s' бе обновено!") % {"title": rem.title})
            return redirect('pets:reminder_list')
    else:
        form = ReminderForm(instance=rem, user=request.user)

    return render(request, 'pets/reminder_form.html', {
        'form': form,
        'rem': rem,
        'title': _('Редакция на напомняне: %(title)s') % {"title": rem.title},
        'button_text': _('Запази промените'),
        'cancel_url': reverse('pets:reminder_list'),
    })


@login_required
@require_POST
def reminder_toggle_complete_view(request, pk):
    rem = get_object_or_404(Reminder, pk=pk, owner=request.user)
    rem.is_completed = not rem.is_completed
    rem.save(update_fields=['is_completed', 'completed_at'])

    if rem.is_completed:
        messages.success(request, _("Напомнянето '%(title)s' бе отбелязано като изпълнено! Браво!") % {"title": rem.title})
    else:
        messages.info(request, _("Напомнянето '%(title)s' бе върнато като активно.") % {"title": rem.title})

    return redirect(_safe_next_url(request, reverse('pets:reminder_list')))


@login_required
@require_POST
def reminder_delete_view(request, pk):
    rem = get_object_or_404(Reminder, pk=pk, owner=request.user)
    title = rem.title
    rem.delete()
    messages.success(request, _("Напомнянето '%(title)s' бе изтрито.") % {"title": title})
    return redirect('pets:reminder_list')
