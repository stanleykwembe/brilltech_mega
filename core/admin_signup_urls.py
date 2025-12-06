from django.urls import path
from . import admin_signup_views

urlpatterns = [
    path('', admin_signup_views.admin_signup, name='admin_signup'),
]
