from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q, Avg, Count
from decimal import Decimal
import secrets


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


class IsStudent(permissions.BasePermission):
    """
    Custom permission to only allow students to access student endpoints.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and hasattr(request.user, 'student_profile')


from .models import (
    PastPaper, Quiz, Subject, Grade, ExamBoard,
    FormattedPaper, GeneratedAssignment, StudentProfile,
    StudentExamBoard, StudentSubject, InteractiveQuestion,
    StudentQuiz, StudentQuizAttempt, Note, Flashcard,
    ExamPaper, StudentProgress, StudentQuizQuota
)
from .serializers import (
    PastPaperSerializer, QuizSerializer, SubjectSerializer,
    GradeSerializer, ExamBoardSerializer, FormattedPaperSerializer,
    GeneratedAssignmentSerializer, StudentProfileSerializer,
    StudentExamBoardSerializer, StudentSubjectSerializer,
    InteractiveQuestionSerializer, StudentQuizSerializer,
    StudentQuizListSerializer, StudentQuizAttemptSerializer,
    NoteSerializer, FlashcardSerializer, ExamPaperSerializer,
    StudentProgressSerializer, StudentRegisterSerializer,
    StudentLoginSerializer, StudentOnboardingSerializer,
    InteractiveQuestionWithoutAnswerSerializer
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
    - question_type (text match)
    
    Search: title, instructions
    """
    queryset = GeneratedAssignment.objects.select_related('subject', 'grade').all()
    serializer_class = GeneratedAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['subject', 'grade', 'question_type']
    search_fields = ['title', 'instructions']
    ordering_fields = ['created_at', 'title']
    ordering = ['-created_at']


class StudentRegisterView(APIView):
    """
    Student registration endpoint.
    Creates a new student account and returns authentication token.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = StudentRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, created = Token.objects.get_or_create(user=user)
            
            return Response({
                'token': token.key,
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'message': 'Registration successful. Please verify your email.'
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudentLoginView(APIView):
    """
    Student login endpoint.
    Returns authentication token for valid credentials.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = StudentLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, created = Token.objects.get_or_create(user=user)
            
            profile = user.student_profile
            
            return Response({
                'token': token.key,
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'subscription': profile.subscription,
                'onboarding_completed': profile.onboarding_completed
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudentVerifyEmailView(APIView):
    """
    Email verification endpoint.
    Activates student account with verification token.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        token = request.data.get('token')
        
        if not token:
            return Response({'error': 'Token required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            profile = StudentProfile.objects.get(verification_token=token)
            
            if profile.verification_token_created:
                time_diff = timezone.now() - profile.verification_token_created
                if time_diff.days > 1:
                    return Response({'error': 'Token expired.'}, status=status.HTTP_400_BAD_REQUEST)
            
            profile.email_verified = True
            profile.user.is_active = True
            profile.user.save()
            profile.save()
            
            return Response({'message': 'Email verified successfully.'}, status=status.HTTP_200_OK)
        
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)


class StudentOnboardingView(APIView):
    """
    Student onboarding endpoint.
    Completes student profile with grade, exam boards, and subjects.
    """
    permission_classes = [IsStudent]
    
    def post(self, request):
        serializer = StudentOnboardingSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            student_profile = request.user.student_profile
            grade_id = serializer.validated_data['grade_id']
            exam_board_ids = serializer.validated_data['exam_board_ids']
            subject_data = serializer.validated_data['subject_data']
            
            student_profile.grade_id = grade_id
            student_profile.onboarding_completed = True
            student_profile.save()
            
            StudentExamBoard.objects.filter(student=student_profile).delete()
            for board_id in exam_board_ids:
                StudentExamBoard.objects.create(
                    student=student_profile,
                    exam_board_id=board_id
                )
            
            StudentSubject.objects.filter(student=student_profile).delete()
            for item in subject_data:
                StudentSubject.objects.create(
                    student=student_profile,
                    subject_id=item['subject_id'],
                    exam_board_id=item['exam_board_id']
                )
            
            return Response({
                'message': 'Onboarding completed successfully.',
                'profile': StudentProfileSerializer(student_profile, context={'request': request}).data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudentProfileViewSet(viewsets.ModelViewSet):
    """
    Student profile endpoint.
    GET: Retrieve current student profile
    PATCH: Update profile (subscription, parent_email)
    """
    serializer_class = StudentProfileSerializer
    permission_classes = [IsStudent]
    http_method_names = ['get', 'patch']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return StudentProfile.objects.none()
        
        return StudentProfile.objects.filter(user=self.request.user)
    
    def get_object(self):
        return self.request.user.student_profile
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current student profile"""
        profile = request.user.student_profile
        serializer = self.get_serializer(profile)
        return Response(serializer.data)


class StudentQuizViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Student quiz endpoint.
    LIST: Get quizzes filtered by student's subjects
    RETRIEVE: Get quiz details with questions (without answers)
    """
    permission_classes = [IsStudent]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['subject', 'exam_board', 'grade', 'difficulty', 'topic']
    search_fields = ['title', 'topic']
    ordering_fields = ['created_at', 'difficulty', 'title']
    ordering = ['-created_at']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return StudentQuiz.objects.none()
        
        student_profile = self.request.user.student_profile
        student_subjects = student_profile.subjects.values_list('subject_id', flat=True)
        
        queryset = StudentQuiz.objects.filter(
            subject_id__in=student_subjects
        ).select_related('subject', 'exam_board', 'grade')
        
        if student_profile.subscription != 'pro':
            queryset = queryset.filter(is_pro_content=False)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return StudentQuizListSerializer
        return StudentQuizSerializer


class StudentQuizAttemptViewSet(viewsets.ModelViewSet):
    """
    Student quiz attempt endpoint.
    CREATE: Start a new quiz attempt
    LIST: Get all attempts for current student
    RETRIEVE: Get specific attempt with results
    """
    serializer_class = StudentQuizAttemptSerializer
    permission_classes = [IsStudent]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['quiz', 'completed_at']
    ordering_fields = ['started_at', 'score', 'percentage']
    ordering = ['-started_at']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return StudentQuizAttempt.objects.none()
        
        return StudentQuizAttempt.objects.filter(
            student=self.request.user.student_profile
        ).select_related('quiz', 'quiz__subject', 'quiz__exam_board', 'quiz__grade')
    
    def perform_create(self, serializer):
        student_profile = self.request.user.student_profile
        quiz_id = self.request.data.get('quiz_id')
        
        try:
            quiz = StudentQuiz.objects.get(id=quiz_id)
        except StudentQuiz.DoesNotExist:
            from rest_framework import serializers as drf_serializers
            raise drf_serializers.ValidationError({'quiz_id': 'Quiz not found.'})
        
        if quiz.is_pro_content and student_profile.subscription != 'pro':
            from rest_framework import serializers as drf_serializers
            raise drf_serializers.ValidationError({'error': 'Pro subscription required for this quiz.'})
        
        quota, created = StudentQuizQuota.objects.get_or_create(
            student=student_profile,
            subject=quiz.subject,
            topic=quiz.topic
        )
        
        if not quota.can_attempt_quiz(quiz, student_profile.subscription == 'pro'):
            from rest_framework import serializers as drf_serializers
            raise drf_serializers.ValidationError({
                'error': 'Free tier limit reached for this topic. Upgrade to Pro or retry completed quizzes.'
            })
        
        serializer.save(student=student_profile)
    
    @action(detail=True, methods=['post'])
    def submit_answer(self, request, pk=None):
        """Submit answer for a single question (for instant feedback)"""
        attempt = self.get_object()
        
        question_id = request.data.get('question_id')
        answer = request.data.get('answer')
        
        if not question_id or answer is None:
            return Response({'error': 'question_id and answer required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            question = InteractiveQuestion.objects.get(id=question_id)
        except InteractiveQuestion.DoesNotExist:
            return Response({'error': 'Question not found.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if question not in attempt.quiz.questions.all():
            return Response({'error': 'Question not in this quiz.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not isinstance(attempt.answers, dict):
            attempt.answers = {}
        
        attempt.answers[str(question_id)] = answer
        attempt.save()
        
        is_correct = str(answer).strip().lower() == str(question.correct_answer).strip().lower()
        
        response_data = {
            'question_id': question_id,
            'submitted_answer': answer,
            'is_correct': is_correct
        }
        
        if attempt.show_instant_feedback:
            response_data['correct_answer'] = question.correct_answer
            response_data['explanation'] = question.explanation
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete quiz and calculate final score"""
        attempt = self.get_object()
        
        if attempt.completed_at:
            return Response({'error': 'Quiz already completed.'}, status=status.HTTP_400_BAD_REQUEST)
        
        final_answers = request.data.get('answers', {})
        if final_answers:
            attempt.answers = final_answers
        
        questions = attempt.quiz.questions.all()
        total_points = sum(q.points for q in questions)
        earned_points = 0
        
        for question in questions:
            student_answer = attempt.answers.get(str(question.id), '')
            if str(student_answer).strip().lower() == str(question.correct_answer).strip().lower():
                earned_points += question.points
        
        attempt.score = earned_points
        if total_points > 0:
            attempt.percentage = Decimal((earned_points / total_points) * 100).quantize(Decimal('0.01'))
        else:
            attempt.percentage = Decimal('0.00')
        
        attempt.completed_at = timezone.now()
        attempt.save()
        
        student_profile = request.user.student_profile
        quota, created = StudentQuizQuota.objects.get_or_create(
            student=student_profile,
            subject=attempt.quiz.subject,
            topic=attempt.quiz.topic
        )
        if attempt.quiz not in quota.quizzes_completed.all():
            quota.quizzes_completed.add(attempt.quiz)
        quota.attempt_count += 1
        quota.save()
        
        progress, created = StudentProgress.objects.get_or_create(
            student=student_profile,
            subject=attempt.quiz.subject,
            topic=attempt.quiz.topic
        )
        progress.quizzes_attempted += 1
        if attempt.percentage >= 50:
            progress.quizzes_passed += 1
        
        if progress.quizzes_attempted > 0:
            progress.average_score = (
                (progress.average_score * (progress.quizzes_attempted - 1) + attempt.percentage) 
                / progress.quizzes_attempted
            )
        
        progress.save()
        
        return Response({
            'message': 'Quiz completed successfully.',
            'score': attempt.score,
            'total_points': total_points,
            'percentage': float(attempt.percentage),
            'passed': attempt.percentage >= 50
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        """Get detailed results with correct answers and explanations"""
        attempt = self.get_object()
        
        if not attempt.completed_at:
            return Response({'error': 'Quiz not completed yet.'}, status=status.HTTP_400_BAD_REQUEST)
        
        questions = attempt.quiz.questions.all()
        results = []
        
        for question in questions:
            student_answer = attempt.answers.get(str(question.id), '')
            is_correct = str(student_answer).strip().lower() == str(question.correct_answer).strip().lower()
            
            results.append({
                'question': InteractiveQuestionSerializer(question, context={'request': request}).data,
                'student_answer': student_answer,
                'is_correct': is_correct
            })
        
        return Response({
            'attempt': StudentQuizAttemptSerializer(attempt, context={'request': request}).data,
            'results': results
        }, status=status.HTTP_200_OK)


class NoteViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Notes endpoint.
    LIST: Get notes filtered by student's subjects
    RETRIEVE: Get note content (full and summary versions)
    """
    serializer_class = NoteSerializer
    permission_classes = [IsStudent]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['subject', 'exam_board', 'grade', 'topic']
    search_fields = ['title', 'topic', 'full_version_text', 'summary_version_text']
    ordering_fields = ['created_at', 'title']
    ordering = ['subject', 'topic']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Note.objects.none()
        
        student_profile = self.request.user.student_profile
        student_subjects = student_profile.subjects.values_list('subject_id', flat=True)
        
        return Note.objects.filter(
            subject_id__in=student_subjects
        ).select_related('subject', 'exam_board', 'grade')
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        student_profile = request.user.student_profile
        progress, created = StudentProgress.objects.get_or_create(
            student=student_profile,
            subject=instance.subject,
            topic=instance.topic
        )
        progress.notes_viewed = True
        progress.save()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class FlashcardViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Flashcards endpoint.
    LIST: Get flashcards filtered by subject/topic
    RETRIEVE: Get individual flashcard
    """
    serializer_class = FlashcardSerializer
    permission_classes = [IsStudent]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['subject', 'exam_board', 'grade', 'topic']
    search_fields = ['topic', 'front_text', 'back_text']
    ordering_fields = ['created_at', 'topic']
    ordering = ['subject', 'topic']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Flashcard.objects.none()
        
        student_profile = self.request.user.student_profile
        student_subjects = student_profile.subjects.values_list('subject_id', flat=True)
        
        return Flashcard.objects.filter(
            subject_id__in=student_subjects
        ).select_related('subject', 'exam_board', 'grade')
    
    @action(detail=False, methods=['get'])
    def by_topic(self, request):
        """Get all flashcards for a specific topic"""
        topic = request.query_params.get('topic')
        subject_id = request.query_params.get('subject_id')
        
        if not topic or not subject_id:
            return Response({'error': 'topic and subject_id required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        flashcards = self.get_queryset().filter(topic=topic, subject_id=subject_id)
        serializer = self.get_serializer(flashcards, many=True)
        
        student_profile = request.user.student_profile
        progress, created = StudentProgress.objects.get_or_create(
            student=student_profile,
            subject_id=subject_id,
            topic=topic
        )
        progress.flashcards_reviewed += len(flashcards)
        progress.save()
        
        return Response(serializer.data)


class ExamPaperViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Exam papers endpoint.
    LIST: Get exam papers filtered by subject/year
    RETRIEVE: Get paper details with file URLs
    """
    serializer_class = ExamPaperSerializer
    permission_classes = [IsStudent]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['subject', 'exam_board', 'grade', 'year']
    search_fields = ['title']
    ordering_fields = ['year', 'created_at', 'title']
    ordering = ['-year', 'subject']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ExamPaper.objects.none()
        
        student_profile = self.request.user.student_profile
        student_subjects = student_profile.subjects.values_list('subject_id', flat=True)
        
        queryset = ExamPaper.objects.filter(
            subject_id__in=student_subjects
        ).select_related('subject', 'exam_board', 'grade')
        
        if student_profile.subscription != 'pro':
            queryset = queryset.filter(is_pro_content=False)
        
        return queryset


class StudentProgressViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Student progress endpoint.
    LIST: Get progress for all subjects/topics
    RETRIEVE: Get progress for specific subject/topic
    """
    serializer_class = StudentProgressSerializer
    permission_classes = [IsStudent]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['subject', 'topic']
    ordering_fields = ['average_score', 'quizzes_attempted', 'last_activity']
    ordering = ['-last_activity']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return StudentProgress.objects.none()
        
        return StudentProgress.objects.filter(
            student=self.request.user.student_profile
        ).select_related('subject')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get overall progress summary"""
        student_profile = request.user.student_profile
        progress_data = StudentProgress.objects.filter(student=student_profile)
        
        total_quizzes = progress_data.aggregate(total=Count('quizzes_attempted'))['total'] or 0
        total_passed = progress_data.aggregate(total=Count('quizzes_passed'))['total'] or 0
        avg_score = progress_data.aggregate(avg=Avg('average_score'))['avg'] or 0
        
        return Response({
            'total_quizzes_attempted': total_quizzes,
            'total_quizzes_passed': total_passed,
            'overall_average_score': float(avg_score),
            'subjects_studied': progress_data.values('subject').distinct().count(),
            'topics_covered': progress_data.count()
        })


class BulkQuizzesView(APIView):
    """
    Bulk download endpoint for quizzes (offline support).
    Returns all quizzes for student's subjects.
    """
    permission_classes = [IsStudent]
    
    def get(self, request):
        student_profile = request.user.student_profile
        student_subjects = student_profile.subjects.values_list('subject_id', flat=True)
        
        quizzes = StudentQuiz.objects.filter(
            subject_id__in=student_subjects
        ).select_related('subject', 'exam_board', 'grade').prefetch_related('questions')
        
        if student_profile.subscription != 'pro':
            quizzes = quizzes.filter(is_pro_content=False)
        
        serializer = StudentQuizSerializer(quizzes, many=True, context={'request': request})
        
        return Response({
            'count': quizzes.count(),
            'quizzes': serializer.data
        })


class BulkNotesView(APIView):
    """
    Bulk download endpoint for notes (offline support).
    Returns all notes for student's subjects.
    """
    permission_classes = [IsStudent]
    
    def get(self, request):
        student_profile = request.user.student_profile
        student_subjects = student_profile.subjects.values_list('subject_id', flat=True)
        
        notes = Note.objects.filter(
            subject_id__in=student_subjects
        ).select_related('subject', 'exam_board', 'grade')
        
        serializer = NoteSerializer(notes, many=True, context={'request': request})
        
        return Response({
            'count': notes.count(),
            'notes': serializer.data
        })


class BulkFlashcardsView(APIView):
    """
    Bulk download endpoint for flashcards (offline support).
    Returns all flashcards for student's subjects.
    """
    permission_classes = [IsStudent]
    
    def get(self, request):
        student_profile = request.user.student_profile
        student_subjects = student_profile.subjects.values_list('subject_id', flat=True)
        
        flashcards = Flashcard.objects.filter(
            subject_id__in=student_subjects
        ).select_related('subject', 'exam_board', 'grade')
        
        serializer = FlashcardSerializer(flashcards, many=True, context={'request': request})
        
        return Response({
            'count': flashcards.count(),
            'flashcards': serializer.data
        })


class SyncView(APIView):
    """
    Sync endpoint for offline mode.
    Upload offline quiz attempts and download new content.
    """
    permission_classes = [IsStudent]
    
    def post(self, request):
        student_profile = request.user.student_profile
        offline_attempts = request.data.get('quiz_attempts', [])
        
        synced_attempts = []
        errors = []
        
        for attempt_data in offline_attempts:
            try:
                quiz_id = attempt_data.get('quiz_id')
                answers = attempt_data.get('answers', {})
                
                quiz = StudentQuiz.objects.get(id=quiz_id)
                
                attempt = StudentQuizAttempt.objects.create(
                    student=student_profile,
                    quiz=quiz,
                    answers=answers,
                    is_timed=attempt_data.get('is_timed', False),
                    time_limit_minutes=attempt_data.get('time_limit_minutes'),
                    show_instant_feedback=attempt_data.get('show_instant_feedback', True)
                )
                
                questions = quiz.questions.all()
                total_points = sum(q.points for q in questions)
                earned_points = 0
                
                for question in questions:
                    student_answer = answers.get(str(question.id), '')
                    if str(student_answer).strip().lower() == str(question.correct_answer).strip().lower():
                        earned_points += question.points
                
                attempt.score = earned_points
                if total_points > 0:
                    attempt.percentage = Decimal((earned_points / total_points) * 100).quantize(Decimal('0.01'))
                attempt.completed_at = timezone.now()
                attempt.save()
                
                synced_attempts.append(attempt.id)
            
            except Exception as e:
                errors.append({'quiz_id': quiz_id, 'error': str(e)})
        
        last_sync = request.data.get('last_sync')
        new_quizzes = StudentQuiz.objects.filter(
            subject__in=student_profile.subjects.values_list('subject_id', flat=True)
        )
        
        if last_sync:
            try:
                last_sync_time = timezone.datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
                new_quizzes = new_quizzes.filter(created_at__gt=last_sync_time)
            except:
                pass
        
        return Response({
            'synced_attempts': synced_attempts,
            'errors': errors,
            'new_content': {
                'quizzes_count': new_quizzes.count(),
                'last_sync': timezone.now().isoformat()
            }
        })
