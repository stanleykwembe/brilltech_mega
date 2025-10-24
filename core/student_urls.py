from django.urls import path
from . import student_views

urlpatterns = [
    path('register/', student_views.student_register, name='student_register'),
    path('login/', student_views.student_login, name='student_login'),
    path('logout/', student_views.student_logout, name='student_logout'),
    path('verify-email/<str:token>/', student_views.student_verify_email, name='student_verify_email'),
    path('onboarding/', student_views.student_onboarding, name='student_onboarding'),
    path('dashboard/', student_views.student_dashboard, name='student_dashboard'),
    
    path('quizzes/', student_views.student_quizzes_list, name='student_quizzes_list'),
    path('quiz/<int:quiz_id>/start/', student_views.student_quiz_start, name='student_quiz_start'),
    path('quiz/<int:quiz_id>/take/', student_views.student_quiz_take, name='student_quiz_take'),
    path('quiz/submit/', student_views.student_quiz_submit, name='student_quiz_submit'),
    path('quiz/<int:attempt_id>/results/', student_views.student_quiz_results, name='student_quiz_results'),
    path('quiz/history/', student_views.student_quiz_history, name='student_quiz_history'),
    
    path('notes/', student_views.student_notes, name='student_notes'),
    path('note/<int:note_id>/', student_views.student_note_view, name='student_note_view'),
    path('flashcards/', student_views.student_flashcards, name='student_flashcards'),
    path('flashcards/study/<int:subject_id>/', student_views.student_flashcard_study, name='student_flashcard_study'),
    path('exam-papers/', student_views.student_exam_papers, name='student_exam_papers'),
    path('exam-paper/<int:paper_id>/', student_views.student_exam_paper_view, name='student_exam_paper_view'),
    
    path('subscription/', student_views.student_subscription, name='student_subscription'),
    path('subscription/upgrade/', student_views.student_upgrade_to_pro, name='student_upgrade_to_pro'),
    path('subscription/payfast-notify/', student_views.student_payfast_notify, name='student_payfast_notify'),
    path('subscription/payfast-return/', student_views.student_payfast_return, name='student_payfast_return'),
    path('subscription/payfast-cancel/', student_views.student_payfast_cancel, name='student_payfast_cancel'),
    path('subscription/cancel/', student_views.student_subscription_cancel, name='student_subscription_cancel'),
]
