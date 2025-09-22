from django.db import models
from django.contrib.auth.models import User
import secrets
import string

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

def generate_share_token():
    """Generate a secure random token for sharing"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

class ClassGroup(models.Model):
    """Represents a class/group of students for assignment distribution"""
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # e.g., "Grade 7A", "Advanced Math"
    description = models.TextField(blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True)
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['teacher', 'name']  # Teacher can't have duplicate class names
    
    def __str__(self):
        return f"{self.name} ({self.teacher.username})"

class AssignmentShare(models.Model):
    """Tracks when assignments are shared with classes"""
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    class_group = models.ForeignKey(ClassGroup, on_delete=models.CASCADE)
    
    # Either generated assignment OR uploaded document (not both)
    generated_assignment = models.ForeignKey(GeneratedAssignment, on_delete=models.CASCADE, null=True, blank=True)
    uploaded_document = models.ForeignKey(UploadedDocument, on_delete=models.CASCADE, null=True, blank=True)
    
    # Sharing details
    token = models.CharField(max_length=32, unique=True, default=generate_share_token)
    shared_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    
    # Analytics
    view_count = models.IntegerField(default=0)
    last_accessed = models.DateTimeField(null=True, blank=True)
    
    # Optional teacher notes
    notes = models.TextField(blank=True)
    
    class Meta:
        # Ensure exactly one assignment type is set
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(generated_assignment__isnull=False, uploaded_document__isnull=True) |
                    models.Q(generated_assignment__isnull=True, uploaded_document__isnull=False)
                ),
                name='exactly_one_assignment_type'
            ),
            # Prevent duplicate shares of the same generated assignment to the same class
            models.UniqueConstraint(
                fields=['class_group', 'generated_assignment'],
                condition=models.Q(generated_assignment__isnull=False, revoked_at__isnull=True),
                name='unique_active_generated_share'
            ),
            # Prevent duplicate shares of the same uploaded document to the same class
            models.UniqueConstraint(
                fields=['class_group', 'uploaded_document'],
                condition=models.Q(uploaded_document__isnull=False, revoked_at__isnull=True),
                name='unique_active_uploaded_share'
            )
        ]
    
    def clean(self):
        """Validate ownership and data integrity"""
        from django.core.exceptions import ValidationError
        
        # Ensure teacher owns the class group
        if self.class_group and self.teacher != self.class_group.teacher:
            raise ValidationError("Teacher must own the class group being shared to.")
        
        # Ensure teacher owns the assignment being shared
        if self.generated_assignment and self.teacher != self.generated_assignment.teacher:
            raise ValidationError("Teacher must own the generated assignment being shared.")
        
        if self.uploaded_document and self.teacher != self.uploaded_document.uploaded_by:
            raise ValidationError("Teacher must own the uploaded document being shared.")
    
    def save(self, *args, **kwargs):
        """Override save to always run validation"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        assignment_title = self.generated_assignment.title if self.generated_assignment else self.uploaded_document.title
        return f"{assignment_title} shared with {self.class_group.name}"
    
    @property
    def assignment_title(self):
        """Get the title of the shared assignment regardless of type"""
        return self.generated_assignment.title if self.generated_assignment else self.uploaded_document.title
    
    @property
    def assignment_subject(self):
        """Get the subject of the shared assignment"""
        return self.generated_assignment.subject if self.generated_assignment else self.uploaded_document.subject
    
    @property
    def assignment_grade(self):
        """Get the grade of the shared assignment"""
        return self.generated_assignment.grade if self.generated_assignment else self.uploaded_document.grade
    
    @property
    def is_active(self):
        """Check if the share is currently active (not revoked or expired)"""
        from django.utils import timezone
        now = timezone.now()
        
        if self.revoked_at:
            return False
        if self.expires_at and self.expires_at < now:
            return False
        return True
    
    @property
    def assignment_type(self):
        """Get the type of assignment being shared"""
        return 'Generated' if self.generated_assignment else 'Uploaded'