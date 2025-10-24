from django.urls import path
from . import student_views

urlpatterns = [
    path('register/', student_views.student_register, name='student_register'),
    path('login/', student_views.student_login, name='student_login'),
    path('logout/', student_views.student_logout, name='student_logout'),
    path('verify-email/<str:token>/', student_views.student_verify_email, name='student_verify_email'),
    path('onboarding/', student_views.student_onboarding, name='student_onboarding'),
    path('dashboard/', student_views.student_dashboard, name='student_dashboard'),
]
