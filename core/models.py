from django.db import models
from django.contrib.auth.models import User

class Subject(models.Model):
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return str(self.name)

class Grade(models.Model):
    number = models.IntegerField()
    
    def __str__(self):
        return f"Grade {self.number}"

class ExamBoard(models.Model):
    name_full = models.CharField(max_length=200)  # e.g., "Cambridge International"
    abbreviation = models.CharField(max_length=10)  # e.g., "CIE"
    
    def __str__(self):
        return f"{self.name_full} ({self.abbreviation})"

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('teacher', 'Teacher'),
        ('admin', 'Admin'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='teacher')
    subscription = models.CharField(max_length=20, default='free')
    email_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True)
    verification_token_created = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} ({self.role})" if self.user else f"Profile ({self.role})"

class UploadedDocument(models.Model):
    DOC_TYPES = [
        ('lesson_plan', 'Lesson Plan'),
        ('homework', 'Homework'),
        ('past_paper', 'Past Paper'),
        ('sample_questions', 'Sample Questions'),
    ]
    
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)
    board = models.ForeignKey(ExamBoard, on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=DOC_TYPES)
    file_url = models.URLField(blank=True)
    file = models.FileField(upload_to='documents/%Y/%m/', null=True, blank=True)
    ai_content = models.JSONField(null=True, blank=True)  # Store AI-generated content
    created_at = models.DateTimeField(auto_now_add=True)
    tags = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.title} - {self.subject} Grade {self.grade}"

class GeneratedAssignment(models.Model):
    QUESTION_TYPES = [
        ('MCQ', 'Multiple Choice'),
        ('Structured', 'Structured/Short Answer'),
        ('Free Response', 'Free Response/Essay'),
        ('Cambridge-style', 'Cambridge-style Structured'),
    ]
    
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)
    board = models.ForeignKey(ExamBoard, on_delete=models.CASCADE)
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    due_date = models.DateTimeField()
    file_url = models.URLField(blank=True)
    instructions = models.TextField(blank=True)
    shared_link = models.CharField(max_length=500, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    content = models.JSONField()  # Store the generated questions
    
    def __str__(self):
        return f"{self.title} - {self.subject} Grade {self.grade}"

class UsageQuota(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    lesson_plans_used = models.JSONField(default=dict)  # {"subject_id": count}
    assignments_used = models.JSONField(default=dict)  # {"subject_id": count}
    
    def __str__(self):
        return f"Quota for {self.user.username}" if self.user else "Quota"