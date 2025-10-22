from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name='signup'),
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<str:token>/', views.reset_password, name='reset_password'),
    path('account/settings/', views.account_settings, name='account_settings'),
    path('', views.dashboard_view, name='dashboard'),
    path('lesson-plans/', views.lesson_plans_view, name='lesson_plans'),
    path('classwork/', views.classwork_view, name='classwork'),
    path('homework/', views.homework_view, name='homework'),
    path('tests/', views.tests_view, name='tests'),
    path('exams/', views.exams_view, name='exams'),
    path('assignments/', views.assignments_view, name='assignments'),
    path('questions/', views.questions_view, name='questions'),
    path('documents/', views.documents_view, name='documents'),
    path('documents/upload/', views.upload_document, name='upload_document'),
    path('subscription/', views.subscription_view, name='subscription'),
    path('classes/', views.classes_view, name='classes'),
    path('classes/create/', views.create_class, name='create_class'),
    path('classes/<int:class_id>/edit/', views.edit_class, name='edit_class'),
    path('classes/<int:class_id>/delete/', views.delete_class, name='delete_class'),
    # File operations
    path('document/<int:doc_id>/delete/', views.delete_document, name='delete_document'),
    path('document/<int:doc_id>/download/', views.download_document, name='download_document'),
    path('document/<int:doc_id>/view/', views.view_document, name='view_document'),
    path('document/<int:doc_id>/inline/', views.view_document_inline, name='view_document_inline'),
    # AI generation endpoints
    path('generate-assignment/', views.generate_assignment_ai, name='generate_assignment'),
    path('generate-questions/', views.generate_questions_ai, name='generate_questions'),
    # Assignment sharing endpoints
    path('assignments/share/create/', views.create_share, name='create_share'),
    path('assignments/share/<int:share_id>/revoke/', views.revoke_share, name='revoke_share'),
    # Public access endpoints (no login required)
    path('share/a/<str:token>/', views.public_assignment_view, name='public_assignment'),
    path('share/a/<str:token>/download/', views.public_assignment_download, name='public_assignment_download'),
    # Payment and subscription endpoints
    path('subscription/dashboard/', views.subscription_dashboard, name='subscription_dashboard'),
    path('subscription/initiate/<int:plan_id>/', views.initiate_subscription, name='initiate_subscription'),
    path('payfast/notify/', views.payfast_notify, name='payfast_notify'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('payment/cancelled/', views.payment_cancelled, name='payment_cancelled'),
]