from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from .api_views import (
    ExamBoardViewSet, SubjectViewSet, GradeViewSet,
    PastPaperViewSet, FormattedPaperViewSet, QuizViewSet,
    AssignmentViewSet, StudentRegisterView, StudentLoginView,
    StudentVerifyEmailView, StudentOnboardingView, StudentProfileViewSet,
    StudentQuizViewSet, StudentQuizAttemptViewSet, NoteViewSet,
    FlashcardViewSet, ExamPaperViewSet, StudentProgressViewSet,
    BulkQuizzesView, BulkNotesView, BulkFlashcardsView, SyncView
)

schema_view = get_schema_view(
    openapi.Info(
        title="Student EdTech API",
        default_version='v1',
        description="""
        Comprehensive REST API for Student Mobile Application
        
        ## Authentication
        Use Token authentication for all protected endpoints.
        Include the token in the Authorization header: `Authorization: Token <your-token>`
        
        ## Student Features
        - User registration and authentication
        - Profile management with onboarding
        - Interactive quizzes with instant feedback
        - Study notes and flashcards
        - Past exam papers
        - Progress tracking and analytics
        - Offline support with bulk download and sync
        
        ## Free vs Pro Subscription
        - Free: Access to 2 exam boards, limited quizzes per topic
        - Pro (R100/month): Access to 5 exam boards, unlimited quizzes, premium content
        """,
        terms_of_service="https://www.example.com/terms/",
        contact=openapi.Contact(email="support@example.com"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

router = DefaultRouter()
router.register(r'exam-boards', ExamBoardViewSet, basename='examboard')
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'grades', GradeViewSet, basename='grade')
router.register(r'past-papers', PastPaperViewSet, basename='pastpaper')
router.register(r'formatted-papers', FormattedPaperViewSet, basename='formattedpaper')
router.register(r'quizzes', QuizViewSet, basename='quiz')
router.register(r'assignments', AssignmentViewSet, basename='assignment')

student_router = DefaultRouter()
student_router.register(r'profile', StudentProfileViewSet, basename='student-profile')
student_router.register(r'quizzes', StudentQuizViewSet, basename='student-quiz')
student_router.register(r'quiz-attempts', StudentQuizAttemptViewSet, basename='student-quiz-attempt')
student_router.register(r'notes', NoteViewSet, basename='student-note')
student_router.register(r'flashcards', FlashcardViewSet, basename='student-flashcard')
student_router.register(r'exam-papers', ExamPaperViewSet, basename='student-exam-paper')
student_router.register(r'progress', StudentProgressViewSet, basename='student-progress')

urlpatterns = [
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    
    path('', include(router.urls)),
    path('auth/token/', obtain_auth_token, name='api_token_auth'),
    
    path('student/register/', StudentRegisterView.as_view(), name='student-register'),
    path('student/login/', StudentLoginView.as_view(), name='student-login'),
    path('student/verify-email/', StudentVerifyEmailView.as_view(), name='student-verify-email'),
    path('student/onboarding/', StudentOnboardingView.as_view(), name='student-onboarding'),
    
    path('student/', include(student_router.urls)),
    
    path('student/bulk/quizzes/', BulkQuizzesView.as_view(), name='student-bulk-quizzes'),
    path('student/bulk/notes/', BulkNotesView.as_view(), name='student-bulk-notes'),
    path('student/bulk/flashcards/', BulkFlashcardsView.as_view(), name='student-bulk-flashcards'),
    path('student/sync/', SyncView.as_view(), name='student-sync'),
]
