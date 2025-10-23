from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from .api_views import (
    ExamBoardViewSet, SubjectViewSet, GradeViewSet,
    PastPaperViewSet, FormattedPaperViewSet, QuizViewSet,
    AssignmentViewSet
)

router = DefaultRouter()
router.register(r'exam-boards', ExamBoardViewSet, basename='examboard')
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'grades', GradeViewSet, basename='grade')
router.register(r'past-papers', PastPaperViewSet, basename='pastpaper')
router.register(r'formatted-papers', FormattedPaperViewSet, basename='formattedpaper')
router.register(r'quizzes', QuizViewSet, basename='quiz')
router.register(r'assignments', AssignmentViewSet, basename='assignment')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/token/', obtain_auth_token, name='api_token_auth'),
]
