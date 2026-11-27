from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('email/verify/', views.verify_email_view, name='verify_email'),
    path('email/resend-verification/', views.resend_email_verification_view, name='resend_email_verification'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
]
