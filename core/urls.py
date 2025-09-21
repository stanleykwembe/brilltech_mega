from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard_view, name='dashboard'),
    path('lesson-plans/', views.lesson_plans_view, name='lesson_plans'),
    path('assignments/', views.assignments_view, name='assignments'),
    path('questions/', views.questions_view, name='questions'),
    path('documents/', views.documents_view, name='documents'),
    path('subscription/', views.subscription_view, name='subscription'),
    # File operations
    path('document/<int:doc_id>/delete/', views.delete_document, name='delete_document'),
    path('document/<int:doc_id>/download/', views.download_document, name='download_document'),
    path('document/<int:doc_id>/view/', views.view_document, name='view_document'),
    # AI generation endpoints
    path('generate-assignment/', views.generate_assignment_ai, name='generate_assignment'),
    path('generate-questions/', views.generate_questions_ai, name='generate_questions'),
]