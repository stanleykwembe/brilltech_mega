from django.urls import path
from . import views

urlpatterns = [
    # Landing pages
    path('welcome/teacher/', views.teacher_landing, name='teacher_landing'),
    path('welcome/student/', views.student_landing, name='student_landing'),
    
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name='signup'),
    path('register/', views.signup_view, name='register'),  # Alias for landing page links
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
    # Admin panel endpoints (using /panel/ to avoid conflict with Django's /admin/)
    path('panel/', views.admin_dashboard, name='admin_dashboard'),
    path('panel/users/', views.admin_users, name='admin_users'),
    path('panel/users/<int:user_id>/change-subscription/', views.admin_change_subscription, name='admin_change_subscription'),
    path('panel/users/<int:user_id>/toggle-status/', views.admin_toggle_user_status, name='admin_toggle_user_status'),
    path('panel/subscriptions/', views.admin_subscriptions, name='admin_subscriptions'),
    path('panel/api-test/', views.admin_api_test, name='admin_api_test'),
    path('panel/features/', views.admin_features, name='admin_features'),
    path('panel/features/exam-boards/', views.admin_exam_boards, name='admin_exam_boards'),
    path('panel/features/subjects/', views.admin_subjects, name='admin_subjects'),
    path('panel/features/grades/', views.admin_grades, name='admin_grades'),
    path('panel/features/teachers/plans/', views.admin_teacher_subscription_plans, name='admin_teacher_subscription_plans'),
    path('panel/features/student/plans/', views.admin_student_subscription_plans, name='admin_student_subscription_plans'),
    path('panel/communications/', views.admin_communications, name='admin_communications'),
    path('panel/communications/announcements/', views.admin_announcements, name='admin_announcements'),
    path('panel/communications/announcements/<int:announcement_id>/dismiss/', views.dismiss_announcement, name='dismiss_announcement'),
    path('panel/communications/emails/', views.admin_email_blasts, name='admin_email_blasts'),
    path('panel/communications/emails/send/', views.send_email_blast, name='send_email_blast'),
    # Content manager endpoints
    path('content/', views.content_dashboard, name='content_dashboard'),
    path('content/papers/', views.content_papers, name='content_papers'),
    path('content/papers/upload/', views.content_upload_paper, name='content_upload_paper'),
    path('content/papers/<int:paper_id>/reformat/', views.content_reformat_paper, name='content_reformat_paper'),
    path('content/formatted-papers/', views.content_formatted_papers, name='content_formatted_papers'),
    path('content/formatted-papers/<int:paper_id>/review/', views.content_review_formatted_paper, name='content_review_formatted_paper'),
    path('content/quizzes/', views.content_quizzes, name='content_quizzes'),
    path('content/quizzes/create/', views.content_create_quiz, name='content_create_quiz'),
    path('content/bulk-upload/', views.content_bulk_upload, name='content_bulk_upload'),
    path('content/papers/official-bulk-upload/', views.official_papers_bulk_upload, name='official_papers_bulk_upload'),
    # Student content management endpoints
    path('content/interactive-question/create/', views.create_interactive_question, name='create_interactive_question'),
    path('content/interactive-questions/', views.manage_interactive_questions, name='manage_interactive_questions'),
    path('content/interactive-question/<int:question_id>/edit/', views.edit_interactive_question, name='edit_interactive_question'),
    path('content/interactive-question/<int:question_id>/delete/', views.delete_interactive_question, name='delete_interactive_question'),
    path('content/student-quiz/create/', views.create_student_quiz, name='create_student_quiz'),
    path('content/student-quizzes/', views.manage_student_quizzes, name='manage_student_quizzes'),
    path('content/student-quiz/<int:quiz_id>/delete/', views.delete_student_quiz, name='delete_student_quiz'),
    path('content/note/create/', views.create_note, name='create_note'),
    path('content/notes/', views.manage_notes, name='manage_notes'),
    path('content/note/<int:note_id>/delete/', views.delete_note, name='delete_note'),
    path('content/flashcard/create/', views.create_flashcard, name='create_flashcard'),
    path('content/flashcards/', views.manage_flashcards, name='manage_flashcards'),
    path('content/flashcard/<int:flashcard_id>/delete/', views.delete_flashcard, name='delete_flashcard'),
    path('content/exam-paper/create/', views.upload_exam_paper, name='upload_exam_paper'),
    path('content/exam-papers/', views.manage_exam_papers, name='manage_exam_papers'),
    path('content/exam-paper/<int:paper_id>/delete/', views.delete_exam_paper, name='delete_exam_paper'),
    path('content/syllabi/', views.manage_syllabi, name='manage_syllabi'),
    path('content/syllabus/create/', views.create_syllabus, name='create_syllabus'),
    path('content/syllabus/<int:syllabus_id>/delete/', views.delete_syllabus, name='delete_syllabus'),
    path('content/ajax/get-questions/', views.get_questions_ajax, name='get_questions_ajax'),
    
    # Teacher Assessment Builder
    path('create/', views.create_assessment, name='create_assessment'),
    path('assessment/save/', views.save_assessment, name='save_assessment'),
    path('assessment/<int:assessment_id>/edit/', views.edit_assessment, name='edit_assessment'),
    path('assessment/<int:assessment_id>/delete/', views.delete_assessment, name='delete_assessment'),
    path('assessment/<int:assessment_id>/', views.view_assessment, name='view_assessment'),
    
    # Public exam papers browse (no login required)
    path('papers/', views.public_papers_browse, name='public_papers_browse'),
    path('papers/api/', views.public_papers_api, name='public_papers_api'),
    path('papers/filters/', views.public_papers_filters, name='public_papers_filters'),
    path('papers/view/<int:paper_id>/', views.public_paper_view, name='public_paper_view'),
    path('papers/download/<int:paper_id>/', views.public_paper_download, name='public_paper_download'),
    
    # BrillTech corporate pages (no login required)
    path('brilltech/', views.brilltech_landing, name='brilltech_landing'),
    path('brilltech/services/', views.brilltech_services, name='brilltech_services'),
    path('brilltech/learning/', views.brilltech_learning, name='brilltech_learning'),
    path('brilltech/store/', views.brilltech_store, name='brilltech_store'),
    path('brilltech/dashboard/', views.brilltech_dashboard, name='brilltech_dashboard'),
    path('brilltech/apps/', views.brilltech_apps, name='brilltech_apps'),
    path('brilltech/about/', views.brilltech_about, name='brilltech_about'),
    path('brilltech/contact/', views.brilltech_contact, name='brilltech_contact'),
    
    # BrillTech Admin Portal (separate from EduTech admin)
    path('brilltech/admin/', views.brilltech_admin_dashboard, name='brilltech_admin_dashboard'),
    path('brilltech/admin/login/', views.brilltech_admin_login, name='brilltech_admin_login'),
    path('brilltech/admin/logout/', views.brilltech_admin_logout, name='brilltech_admin_logout'),
    path('brilltech/admin/submissions/', views.brilltech_admin_submissions, name='brilltech_admin_submissions'),
    path('brilltech/admin/submissions/<int:submission_id>/', views.brilltech_admin_submission_detail, name='brilltech_admin_submission_detail'),
    path('brilltech/admin/change-password/', views.brilltech_admin_change_password, name='brilltech_admin_change_password'),
    
    # BrillTech CRM - Tasks
    path('brilltech/admin/crm/tasks/', views.crm_tasks_list, name='crm_tasks_list'),
    path('brilltech/admin/crm/tasks/create/', views.crm_task_create, name='crm_task_create'),
    path('brilltech/admin/crm/tasks/<int:task_id>/edit/', views.crm_task_edit, name='crm_task_edit'),
    path('brilltech/admin/crm/tasks/<int:task_id>/delete/', views.crm_task_delete, name='crm_task_delete'),
    
    # BrillTech CRM - Leads
    path('brilltech/admin/crm/leads/', views.crm_leads_list, name='crm_leads_list'),
    path('brilltech/admin/crm/leads/create/', views.crm_lead_create, name='crm_lead_create'),
    path('brilltech/admin/crm/leads/<int:lead_id>/', views.crm_lead_detail, name='crm_lead_detail'),
    path('brilltech/admin/crm/leads/<int:lead_id>/edit/', views.crm_lead_edit, name='crm_lead_edit'),
    path('brilltech/admin/crm/leads/<int:lead_id>/delete/', views.crm_lead_delete, name='crm_lead_delete'),
    path('brilltech/admin/crm/leads/<int:lead_id>/activity/', views.crm_activity_add, name='crm_activity_add'),
    
    # BrillTech CRM - Mailing
    path('brilltech/admin/crm/mailing/', views.crm_mailing_lists, name='crm_mailing_lists'),
    path('brilltech/admin/crm/mailing/create/', views.crm_mailing_list_create, name='crm_mailing_list_create'),
    path('brilltech/admin/crm/mailing/<int:list_id>/', views.crm_mailing_list_detail, name='crm_mailing_list_detail'),
    path('brilltech/admin/crm/mailing/<int:list_id>/subscriber/', views.crm_subscriber_add, name='crm_subscriber_add'),
    path('brilltech/admin/crm/campaigns/', views.crm_email_campaigns, name='crm_email_campaigns'),
    path('brilltech/admin/crm/campaigns/create/', views.crm_email_campaign_create, name='crm_email_campaign_create'),
    
    # Content Manager - Topics/Subtopics/Concepts/Video Lessons Management
    path('content/topics/', views.manage_topics, name='manage_topics'),
    path('content/topics/add/', views.add_topic, name='add_topic'),
    path('content/topics/<int:topic_id>/edit/', views.edit_topic, name='edit_topic'),
    path('content/topics/<int:topic_id>/delete/', views.delete_topic, name='delete_topic'),
    path('content/subtopics/', views.manage_subtopics, name='manage_subtopics'),
    path('content/subtopics/add/', views.add_subtopic, name='add_subtopic'),
    path('content/subtopics/<int:subtopic_id>/edit/', views.edit_subtopic, name='edit_subtopic'),
    path('content/subtopics/<int:subtopic_id>/delete/', views.delete_subtopic, name='delete_subtopic'),
    path('content/concepts/', views.manage_concepts, name='manage_concepts'),
    path('content/concepts/add/', views.add_concept, name='add_concept'),
    path('content/concepts/<int:concept_id>/edit/', views.edit_concept, name='edit_concept'),
    path('content/concepts/<int:concept_id>/delete/', views.delete_concept, name='delete_concept'),
    path('content/video-lessons/', views.manage_video_lessons, name='manage_video_lessons'),
    path('content/video-lessons/add/', views.add_video_lesson, name='add_video_lesson'),
    path('content/video-lessons/<int:video_id>/edit/', views.edit_video_lesson, name='edit_video_lesson'),
    path('content/video-lessons/<int:video_id>/delete/', views.delete_video_lesson, name='delete_video_lesson'),
    
    # Public share links for students (token-based, no login required)
    path('share/<str:token>/', views.share_content_view, name='share_content_view'),
    
    # Create share link (requires teacher login)
    path('api/create-share/', views.create_share_link, name='create_share_link'),
]