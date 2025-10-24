from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils import timezone
from .models import (
    PastPaper, Quiz, Subject, Grade, ExamBoard, 
    FormattedPaper, GeneratedAssignment, StudentProfile,
    StudentExamBoard, StudentSubject, InteractiveQuestion,
    StudentQuiz, StudentQuizAttempt, Note, Flashcard,
    ExamPaper, StudentProgress, StudentQuizQuota
)


class ExamBoardSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamBoard
        fields = ['id', 'name_full', 'abbreviation', 'region']


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name']


class GradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = ['id', 'number']


class PastPaperSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    grade = GradeSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    
    class Meta:
        model = PastPaper
        fields = [
            'id', 'title', 'exam_board', 'year', 'subject', 'grade',
            'chapter', 'section', 'file_url', 'file_size', 'uploaded_at'
        ]
    
    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None
    
    def get_file_size(self, obj):
        if obj.file:
            return obj.file.size
        return None


class FormattedPaperSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    grade = GradeSerializer(read_only=True)
    source_paper = PastPaperSerializer(read_only=True)
    
    class Meta:
        model = FormattedPaper
        fields = [
            'id', 'title', 'exam_board', 'year', 'subject', 'grade',
            'questions_json', 'memo_json', 'total_questions', 'total_marks',
            'question_type', 'processing_status', 'is_published',
            'source_paper', 'created_at'
        ]


class QuizSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    grade = GradeSerializer(read_only=True)
    
    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'exam_board', 'subject', 'grade', 'topic',
            'is_premium', 'google_form_link', 'created_at'
        ]


class GeneratedAssignmentSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    grade = GradeSerializer(read_only=True)
    board = ExamBoardSerializer(read_only=True)
    
    class Meta:
        model = GeneratedAssignment
        fields = [
            'id', 'title', 'subject', 'grade', 'board', 'question_type',
            'instructions', 'content', 'file_url', 'created_at', 'due_date'
        ]
        read_only_fields = ['id', 'created_at']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class StudentProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    grade = GradeSerializer(read_only=True)
    exam_board_limit = serializers.SerializerMethodField()
    subject_limit_per_board = serializers.SerializerMethodField()
    
    class Meta:
        model = StudentProfile
        fields = [
            'id', 'user', 'subscription', 'parent_email', 'grade',
            'email_verified', 'created_at', 'onboarding_completed',
            'exam_board_limit', 'subject_limit_per_board'
        ]
        read_only_fields = ['id', 'user', 'email_verified', 'created_at']
    
    def get_exam_board_limit(self, obj):
        return obj.get_exam_board_limit()
    
    def get_subject_limit_per_board(self, obj):
        return obj.get_subject_limit_per_board()


class StudentExamBoardSerializer(serializers.ModelSerializer):
    exam_board = ExamBoardSerializer(read_only=True)
    exam_board_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = StudentExamBoard
        fields = ['id', 'exam_board', 'exam_board_id', 'selected_at']
        read_only_fields = ['id', 'selected_at']


class StudentSubjectSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    exam_board = ExamBoardSerializer(read_only=True)
    subject_id = serializers.IntegerField(write_only=True)
    exam_board_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = StudentSubject
        fields = [
            'id', 'subject', 'exam_board', 'subject_id', 
            'exam_board_id', 'selected_at'
        ]
        read_only_fields = ['id', 'selected_at']


class InteractiveQuestionSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    exam_board = ExamBoardSerializer(read_only=True)
    grade = GradeSerializer(read_only=True)
    question_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = InteractiveQuestion
        fields = [
            'id', 'subject', 'exam_board', 'grade', 'topic',
            'question_type', 'difficulty', 'question_text', 
            'question_image_url', 'options', 'correct_answer',
            'matching_pairs', 'explanation', 'points', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_question_image_url(self, obj):
        if obj.question_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.question_image.url)
            return obj.question_image.url
        return None


class InteractiveQuestionWithoutAnswerSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    exam_board = ExamBoardSerializer(read_only=True)
    grade = GradeSerializer(read_only=True)
    question_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = InteractiveQuestion
        fields = [
            'id', 'subject', 'exam_board', 'grade', 'topic',
            'question_type', 'difficulty', 'question_text', 
            'question_image_url', 'options', 'matching_pairs', 
            'points'
        ]
        read_only_fields = ['id']
    
    def get_question_image_url(self, obj):
        if obj.question_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.question_image.url)
            return obj.question_image.url
        return None


class StudentQuizSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    exam_board = ExamBoardSerializer(read_only=True)
    grade = GradeSerializer(read_only=True)
    question_count = serializers.SerializerMethodField()
    questions = InteractiveQuestionWithoutAnswerSerializer(many=True, read_only=True)
    
    class Meta:
        model = StudentQuiz
        fields = [
            'id', 'title', 'subject', 'exam_board', 'grade', 'topic',
            'difficulty', 'length', 'is_pro_content', 'created_at',
            'question_count', 'questions'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_question_count(self, obj):
        return obj.questions.count()


class StudentQuizListSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    exam_board = ExamBoardSerializer(read_only=True)
    grade = GradeSerializer(read_only=True)
    question_count = serializers.SerializerMethodField()
    
    class Meta:
        model = StudentQuiz
        fields = [
            'id', 'title', 'subject', 'exam_board', 'grade', 'topic',
            'difficulty', 'length', 'is_pro_content', 'created_at',
            'question_count'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_question_count(self, obj):
        return obj.questions.count()


class StudentQuizAttemptSerializer(serializers.ModelSerializer):
    quiz = StudentQuizListSerializer(read_only=True)
    quiz_id = serializers.IntegerField(write_only=True)
    percentage_display = serializers.SerializerMethodField()
    
    class Meta:
        model = StudentQuizAttempt
        fields = [
            'id', 'quiz', 'quiz_id', 'started_at', 'completed_at',
            'is_timed', 'time_limit_minutes', 'show_instant_feedback',
            'answers', 'score', 'percentage', 'percentage_display'
        ]
        read_only_fields = ['id', 'started_at', 'score', 'percentage']
    
    def get_percentage_display(self, obj):
        if obj.percentage:
            return f"{obj.percentage}%"
        return None


class NoteSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    exam_board = ExamBoardSerializer(read_only=True)
    grade = GradeSerializer(read_only=True)
    full_version_url = serializers.SerializerMethodField()
    summary_version_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Note
        fields = [
            'id', 'title', 'subject', 'exam_board', 'grade', 'topic',
            'full_version_url', 'summary_version_url', 
            'full_version_text', 'summary_version_text',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_full_version_url(self, obj):
        if obj.full_version:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.full_version.url)
            return obj.full_version.url
        return None
    
    def get_summary_version_url(self, obj):
        if obj.summary_version:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.summary_version.url)
            return obj.summary_version.url
        return None


class FlashcardSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    exam_board = ExamBoardSerializer(read_only=True)
    grade = GradeSerializer(read_only=True)
    image_front_url = serializers.SerializerMethodField()
    image_back_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Flashcard
        fields = [
            'id', 'subject', 'exam_board', 'grade', 'topic',
            'front_text', 'back_text', 'image_front_url', 
            'image_back_url', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_image_front_url(self, obj):
        if obj.image_front:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image_front.url)
            return obj.image_front.url
        return None
    
    def get_image_back_url(self, obj):
        if obj.image_back:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image_back.url)
            return obj.image_back.url
        return None


class ExamPaperSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    exam_board = ExamBoardSerializer(read_only=True)
    grade = GradeSerializer(read_only=True)
    paper_file_url = serializers.SerializerMethodField()
    marking_scheme_url = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ExamPaper
        fields = [
            'id', 'title', 'subject', 'exam_board', 'grade', 'year',
            'paper_file_url', 'marking_scheme_url', 'has_interactive_version',
            'is_pro_content', 'created_at', 'question_count'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_paper_file_url(self, obj):
        if obj.paper_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.paper_file.url)
            return obj.paper_file.url
        return None
    
    def get_marking_scheme_url(self, obj):
        if obj.marking_scheme:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.marking_scheme.url)
            return obj.marking_scheme.url
        return None
    
    def get_question_count(self, obj):
        return obj.interactive_questions.count()


class StudentProgressSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    pass_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = StudentProgress
        fields = [
            'id', 'subject', 'topic', 'quizzes_attempted', 
            'quizzes_passed', 'average_score', 'pass_rate',
            'notes_viewed', 'flashcards_reviewed', 'last_activity'
        ]
        read_only_fields = ['id', 'last_activity']
    
    def get_pass_rate(self, obj):
        if obj.quizzes_attempted > 0:
            return (obj.quizzes_passed / obj.quizzes_attempted) * 100
        return 0


class StudentRegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    parent_email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    
    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists.")
        return value
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered.")
        return value
    
    def create(self, validated_data):
        parent_email = validated_data.pop('parent_email', '')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            is_active=False
        )
        
        import secrets
        verification_token = secrets.token_urlsafe(32)
        
        StudentProfile.objects.create(
            user=user,
            parent_email=parent_email,
            verification_token=verification_token,
            verification_token_created=timezone.now()
        )
        
        return user


class StudentLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            user = authenticate(username=username, password=password)
            
            if not user:
                raise serializers.ValidationError("Invalid credentials.")
            
            if not user.is_active:
                raise serializers.ValidationError("Email verification required.")
            
            if not hasattr(user, 'student_profile'):
                raise serializers.ValidationError("Not a student account.")
            
            attrs['user'] = user
            return attrs
        
        raise serializers.ValidationError("Must include username and password.")


class StudentOnboardingSerializer(serializers.Serializer):
    grade_id = serializers.IntegerField()
    exam_board_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=5
    )
    subject_data = serializers.ListField(
        child=serializers.DictField(),
        min_length=1
    )
    
    def validate_grade_id(self, value):
        if not Grade.objects.filter(id=value).exists():
            raise serializers.ValidationError("Invalid grade ID.")
        return value
    
    def validate_exam_board_ids(self, value):
        student_profile = self.context['request'].user.student_profile
        if len(value) > student_profile.get_exam_board_limit():
            raise serializers.ValidationError(
                f"Maximum {student_profile.get_exam_board_limit()} exam boards allowed."
            )
        
        if not all(ExamBoard.objects.filter(id=board_id).exists() for board_id in value):
            raise serializers.ValidationError("One or more invalid exam board IDs.")
        
        return value
    
    def validate_subject_data(self, value):
        for item in value:
            if 'subject_id' not in item or 'exam_board_id' not in item:
                raise serializers.ValidationError(
                    "Each subject must have subject_id and exam_board_id."
                )
        return value
