from rest_framework import serializers
from .models import (
    PastPaper, Quiz, Subject, Grade, ExamBoard, 
    FormattedPaper, GeneratedAssignment
)


class ExamBoardSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamBoard
        fields = ['id', 'name', 'abbreviation', 'country']


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'code']


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
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = GeneratedAssignment
        fields = [
            'id', 'subject', 'grade', 'topic', 'assignment_type',
            'content', 'file_url', 'created_at'
        ]
    
    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None
