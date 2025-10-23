from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend


class IsFreeQuizOrAuthenticated(permissions.BasePermission):
    """
    Custom permission: Allow access to free quizzes for all,
    but require authentication for premium quizzes.
    """
    def has_object_permission(self, request, view, obj):
        # Allow access if quiz is free, otherwise require authentication
        if not obj.is_premium:
            return True
        return request.user and request.user.is_authenticated
from .models import (
    PastPaper, Quiz, Subject, Grade, ExamBoard,
    FormattedPaper, GeneratedAssignment
)
from .serializers import (
    PastPaperSerializer, QuizSerializer, SubjectSerializer,
    GradeSerializer, ExamBoardSerializer, FormattedPaperSerializer,
    GeneratedAssignmentSerializer
)


class ExamBoardViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for exam boards.
    
    List all exam boards or retrieve a specific one.
    Public access - no authentication required.
    """
    queryset = ExamBoard.objects.all()
    serializer_class = ExamBoardSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name_full', 'abbreviation', 'region']
    ordering_fields = ['name_full', 'abbreviation']
    ordering = ['abbreviation']


class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for subjects.
    
    List all subjects or retrieve a specific one.
    Public access - no authentication required.
    """
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']
    ordering = ['name']


class GradeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for grades.
    
    List all grades or retrieve a specific one.
    Public access - no authentication required.
    """
    queryset = Grade.objects.all()
    serializer_class = GradeSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['number']
    ordering = ['number']


class PastPaperViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for past papers.
    
    Public access - government exam papers available to all.
    
    Filter by:
    - exam_board (text match)
    - subject (ID)
    - grade (ID)
    - year (exact match)
    - chapter (text contains)
    - section (text contains)
    
    Search: title, chapter, section
    """
    queryset = PastPaper.objects.select_related('subject', 'grade').all()
    serializer_class = PastPaperSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['exam_board', 'subject', 'grade', 'year']
    search_fields = ['title', 'chapter', 'section']
    ordering_fields = ['year', 'uploaded_at', 'title']
    ordering = ['-year', '-uploaded_at']


class FormattedPaperViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for AI-formatted papers.
    
    Filter by:
    - exam_board (text match)
    - subject (ID)
    - grade (ID)
    - year (exact match)
    - processing_status (pending, processing, completed, failed)
    - is_published (boolean)
    
    Search: title
    """
    queryset = FormattedPaper.objects.select_related('subject', 'grade', 'source_paper').filter(is_published=True)
    serializer_class = FormattedPaperSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['exam_board', 'subject', 'grade', 'year', 'processing_status', 'is_published']
    search_fields = ['title']
    ordering_fields = ['year', 'created_at', 'total_questions']
    ordering = ['-year', '-created_at']


class QuizViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for quizzes.
    
    Public access for free quizzes, authentication required for premium quizzes.
    
    Filter by:
    - exam_board (text match)
    - subject (ID)
    - grade (ID)
    - topic (text contains)
    - is_premium (boolean)
    
    Search: title, topic
    """
    queryset = Quiz.objects.select_related('subject', 'grade').all()
    serializer_class = QuizSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['exam_board', 'subject', 'grade', 'is_premium']
    search_fields = ['title', 'topic']
    ordering_fields = ['created_at', 'title']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter premium quizzes based on authentication"""
        queryset = super().get_queryset()
        # If user is not authenticated, only show free quizzes
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(is_premium=False)
        return queryset


class AssignmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for assignments.
    
    Filter by:
    - subject (ID)
    - grade (ID)
    - topic (text contains)
    - assignment_type (text match)
    
    Search: topic, content
    """
    queryset = GeneratedAssignment.objects.select_related('subject', 'grade').all()
    serializer_class = GeneratedAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['subject', 'grade', 'assignment_type']
    search_fields = ['topic', 'content']
    ordering_fields = ['created_at', 'topic']
    ordering = ['-created_at']
