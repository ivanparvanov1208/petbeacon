from django.urls import path
from . import views

app_name = 'pets'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Pets
    path('pets/', views.pet_list_view, name='pet_list'),
    path('pets/new/', views.pet_create_view, name='pet_create'),
    path('pets/<int:pk>/', views.pet_detail_view, name='pet_detail'),
    path('pets/<int:pk>/edit/', views.pet_update_view, name='pet_update'),
    path('pets/<int:pk>/delete/', views.pet_delete_view, name='pet_delete'),
    path('pets/<int:pk>/passport/', views.pet_passport_view, name='pet_passport'),

    # Vaccinations
    path('pets/<int:pet_pk>/vaccinations/new/', views.vaccination_create_view, name='vaccination_create'),
    path('vaccinations/<int:pk>/edit/', views.vaccination_update_view, name='vaccination_update'),
    path('vaccinations/<int:pk>/delete/', views.vaccination_delete_view, name='vaccination_delete'),

    # Medical records
    path('pets/<int:pet_pk>/records/new/', views.medical_record_create_view, name='medical_record_create'),
    path('records/<int:pk>/edit/', views.medical_record_update_view, name='medical_record_update'),
    path('records/<int:pk>/delete/', views.medical_record_delete_view, name='medical_record_delete'),

    # Medications
    path('pets/<int:pet_pk>/medications/new/', views.medication_create_view, name='medication_create'),
    path('medications/<int:pk>/edit/', views.medication_update_view, name='medication_update'),
    path('medications/<int:pk>/toggle/', views.medication_toggle_active_view, name='medication_toggle_active'),
    path('medications/<int:pk>/delete/', views.medication_delete_view, name='medication_delete'),

    # Vet visits
    path('pets/<int:pet_pk>/visits/new/', views.vet_visit_create_view, name='vet_visit_create'),
    path('visits/<int:pk>/edit/', views.vet_visit_update_view, name='vet_visit_update'),
    path('visits/<int:pk>/delete/', views.vet_visit_delete_view, name='vet_visit_delete'),

    # Reminders
    path('reminders/', views.reminder_list_view, name='reminder_list'),
    path('reminders/new/', views.reminder_create_view, name='reminder_create'),
    path('reminders/<int:pk>/edit/', views.reminder_update_view, name='reminder_update'),
    path('reminders/<int:pk>/toggle/', views.reminder_toggle_complete_view, name='reminder_toggle_complete'),
    path('reminders/<int:pk>/delete/', views.reminder_delete_view, name='reminder_delete'),
]
