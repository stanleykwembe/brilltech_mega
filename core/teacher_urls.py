from django.urls import path
from . import views

urlpatterns = [
    # Teacher portal landing page
    path('', views.teacher_landing, name='teacher_landing'),
    
    # Authentication
    path('login/', views.login_view, name='teacher_login'),
    path('logout/', views.logout_view, name='teacher_logout'),
    path('signup/', views.signup_view, name='teacher_signup'),
    path('register/', views.signup_view, name='teacher_register'),
    path('verify-email/<str:token>/', views.verify_email, name='teacher_verify_email'),
    path('resend-verification/', views.resend_verification, name='teacher_resend_verification'),
    path('forgot-password/', views.forgot_password, name='teacher_forgot_password'),
    path('reset-password/<str:token>/', views.reset_password, name='teacher_reset_password'),
    
    # Teacher dashboard and main features
    path('dashboard/', views.dashboard_view, name='teacher_dashboard'),
    path('account/settings/', views.account_settings, name='teacher_account_settings'),
    path('lesson-plans/', views.lesson_plans_view, name='teacher_lesson_plans'),
    path('classwork/', views.classwork_view, name='teacher_classwork'),
    path('homework/', views.homework_view, name='teacher_homework'),
    path('tests/', views.tests_view, name='teacher_tests'),
    path('exams/', views.exams_view, name='teacher_exams'),
    path('assignments/', views.assignments_view, name='teacher_assignments'),
    path('questions/', views.questions_view, name='teacher_questions'),
    path('documents/', views.documents_view, name='teacher_documents'),
    path('documents/upload/', views.upload_document, name='teacher_upload_document'),
    path('subscription/', views.subscription_view, name='teacher_subscription'),
    path('classes/', views.classes_view, name='teacher_classes'),
    path('classes/create/', views.create_class, name='teacher_create_class'),
    path('classes/<int:class_id>/edit/', views.edit_class, name='teacher_edit_class'),
    path('classes/<int:class_id>/delete/', views.delete_class, name='teacher_delete_class'),
    
    # File operations
    path('document/<int:doc_id>/delete/', views.delete_document, name='teacher_delete_document'),
    path('document/<int:doc_id>/download/', views.download_document, name='teacher_download_document'),
    path('document/<int:doc_id>/view/', views.view_document, name='teacher_view_document'),
    path('document/<int:doc_id>/inline/', views.view_document_inline, name='teacher_view_document_inline'),
    
    # AI generation endpoints
    path('generate-assignment/', views.generate_assignment_ai, name='teacher_generate_assignment'),
    path('generate-questions/', views.generate_questions_ai, name='teacher_generate_questions'),
    
    # Assignment sharing endpoints
    path('assignments/share/create/', views.create_share, name='teacher_create_share'),
    path('assignments/share/<int:share_id>/revoke/', views.revoke_share, name='teacher_revoke_share'),
    
    # Payment and subscription endpoints
    path('subscription/dashboard/', views.subscription_dashboard, name='teacher_subscription_dashboard'),
    path('subscription/initiate/<int:plan_id>/', views.initiate_subscription, name='teacher_initiate_subscription'),
    
    # Teacher Assessment Builder
    path('create/', views.create_assessment, name='teacher_create_assessment'),
    path('assessment/save/', views.save_assessment, name='teacher_save_assessment'),
    path('assessment/<int:assessment_id>/edit/', views.edit_assessment, name='teacher_edit_assessment'),
    path('assessment/<int:assessment_id>/delete/', views.delete_assessment, name='teacher_delete_assessment'),
    path('assessment/<int:assessment_id>/', views.view_assessment, name='teacher_view_assessment'),
]
