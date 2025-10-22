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
    region = models.CharField(max_length=100, default='')  # e.g., "South Africa", "Zimbabwe"
    
    def __str__(self):
        return f"{self.abbreviation} ({self.region})" if self.region else self.abbreviation

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('teacher', 'Teacher'),
        ('content_manager', 'Content Manager'),
        ('admin', 'Admin'),
    ]
    
    SUBSCRIPTION_CHOICES = [
        ('free', 'Free'),
        ('starter', 'Starter'),
        ('growth', 'Growth'),
        ('premium', 'Premium'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='teacher')
    subscription = models.CharField(max_length=20, choices=SUBSCRIPTION_CHOICES, default='free')
    email_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True)
    verification_token_created = models.DateTimeField(null=True, blank=True)
    bio = models.TextField(blank=True)
    institution = models.CharField(max_length=200, blank=True)
    email_notifications = models.BooleanField(default=True)
    teacher_code = models.CharField(max_length=10, unique=True, null=True, blank=True)  # Unique code for Google Forms
    
    def __str__(self):
        return f"{self.user.username} ({self.role})" if self.user else f"Profile ({self.role})"
    
    def get_subject_limit(self):
        """Returns the number of subjects allowed based on subscription tier"""
        limits = {
            'free': 1,
            'starter': 1,
            'growth': 2,
            'premium': 3,
        }
        return limits.get(self.subscription, 1)
    
    def get_lesson_plan_limit_per_subject(self):
        """Returns monthly lesson plan limit per subject based on tier"""
        limits = {
            'free': 2,
            'starter': 10,
            'growth': 20,
            'premium': 0,  # 0 means unlimited
        }
        return limits.get(self.subscription, 2)
    
    def can_use_ai(self):
        """Check if user can use AI features"""
        return self.subscription in ['growth', 'premium']
    
    def get_ai_model(self):
        """Returns AI model to use based on tier"""
        if self.subscription == 'growth':
            return 'gpt-3.5-turbo'  # Basic AI
        elif self.subscription == 'premium':
            return 'gpt-4'  # Advanced AI
        return None

class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Password reset for {self.user.username}"
    
    def is_valid(self):
        from django.utils import timezone
        return not self.used and timezone.now() < self.expires_at

class UploadedDocument(models.Model):
    DOC_TYPES = [
        ('lesson_plan', 'Lesson Plan'),
        ('classwork', 'Classwork'),
        ('homework', 'Homework'),
        ('assignment', 'Assignment'),
        ('test', 'Test'),
        ('exam', 'Exam'),
        ('general', 'General Document'),
    ]
    
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)
    board = models.ForeignKey(ExamBoard, on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=DOC_TYPES, default='general')
    file_url = models.URLField(blank=True)
    file = models.FileField(upload_to='documents/%Y/%m/', null=True, blank=True)
    ai_content = models.JSONField(null=True, blank=True)  # Store AI-generated content
    created_at = models.DateTimeField(auto_now_add=True)
    tags = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']  # Sort by upload date, newest first
    
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

class SubscribedSubject(models.Model):
    """Tracks which subjects a user has subscribed to"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscribed_subjects')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'subject']
        ordering = ['subscribed_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.subject.name}"

class UsageQuota(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    lesson_plans_used = models.JSONField(default=dict)  # {"subject_id": count}
    assignments_used = models.JSONField(default=dict)  # {"subject_id": count}
    last_reset = models.DateTimeField(auto_now_add=True, null=True, blank=True)  # Track when quotas were last reset
    
    def __str__(self):
        return f"Quota for {self.user.username}" if self.user else "Quota"
    
    def get_lesson_plans_used(self, subject_id):
        """Get lesson plans used for a specific subject"""
        return self.lesson_plans_used.get(str(subject_id), 0)
    
    def increment_lesson_plans(self, subject_id):
        """Increment lesson plan count for a subject"""
        subject_key = str(subject_id)
        current = self.lesson_plans_used.get(subject_key, 0)
        self.lesson_plans_used[subject_key] = current + 1
        self.save()
    
    def reset_monthly_quotas(self):
        """Reset quotas at the start of each month"""
        self.lesson_plans_used = {}
        self.assignments_used = {}
        from django.utils import timezone
        self.last_reset = timezone.now()
        self.save()

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

class PastPaper(models.Model):
    """Past examination papers uploaded by admin"""
    EXAM_BOARD_CHOICES = [
        ('Cambridge', 'Cambridge International'),
        ('Edexcel', 'Edexcel'),
        ('GED', 'GED'),
        ('CAPS', 'CAPS (South Africa)'),
        ('IEB', 'IEB (South Africa)'),
        ('ZIMSEC', 'ZIMSEC (Zimbabwe)'),
        ('NSSC', 'Namibia Senior Secondary Certificate'),
        ('ZEC', 'Zambia Examinations Council'),
        ('other', 'Other (Specify in notes)'),
    ]
    
    PAPER_TYPE_CHOICES = [
        ('paper1', 'Paper 1'),
        ('paper2', 'Paper 2'),
        ('paper3', 'Paper 3'),
        ('practical', 'Practical'),
        ('coursework', 'Coursework'),
    ]
    
    title = models.CharField(max_length=200)
    exam_board = models.CharField(max_length=50, choices=EXAM_BOARD_CHOICES)
    exam_board_custom = models.CharField(max_length=100, blank=True)  # For manual entry
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    paper_type = models.CharField(max_length=20, choices=PAPER_TYPE_CHOICES)
    paper_code = models.CharField(max_length=50)  # Unique code from exam board
    year = models.IntegerField()
    chapter = models.CharField(max_length=100, blank=True)  # e.g., "Cells"
    section = models.CharField(max_length=100, blank=True)  # e.g., "Section A"
    file = models.FileField(upload_to='past_papers/%Y/%m/')
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['exam_board', 'paper_code', 'year']
        ordering = ['-year', 'subject', 'grade']
    
    def __str__(self):
        board = self.exam_board_custom if self.exam_board == 'other' else self.exam_board
        return f"{board} {self.subject.name} Grade {self.grade.number} - {self.paper_code} ({self.year})"

class Quiz(models.Model):
    """Quizzes created from past papers or topics"""
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)
    exam_board = models.CharField(max_length=50, choices=PastPaper.EXAM_BOARD_CHOICES)
    topic = models.CharField(max_length=200)
    chapter = models.CharField(max_length=100, blank=True)
    section = models.CharField(max_length=100, blank=True)
    
    # Quiz metadata
    google_form_link = models.URLField()
    is_premium = models.BooleanField(default=False)  # Free or premium quiz
    is_ai_generated = models.BooleanField(default=False)
    difficulty_level = models.CharField(max_length=20, choices=[
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ], default='medium')
    
    # Link to source past paper if generated from one
    created_from_paper = models.ForeignKey(PastPaper, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Analytics
    times_used = models.IntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Quizzes'
    
    def __str__(self):
        return f"{self.title} - {self.subject.name} Grade {self.grade.number}"

class QuizResponse(models.Model):
    """Student responses to quizzes (fetched from Google Forms)"""
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='responses')
    teacher_code = models.CharField(max_length=10)  # Teacher's unique code
    student_name = models.CharField(max_length=200)
    answers_json = models.JSONField()  # Store all answers from Google Form
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    submitted_at = models.DateTimeField()
    
    # Link to teacher for quick filtering
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_responses', null=True)
    
    class Meta:
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"{self.student_name} - {self.quiz.title} ({self.score}%)"

class SubscriptionPlan(models.Model):
    """Defines available subscription tiers and their features"""
    PLAN_TYPES = [
        ('free', 'Free'),
        ('starter', 'Starter'),
        ('growth', 'Growth'),
        ('premium', 'Premium'),
    ]
    
    name = models.CharField(max_length=50, unique=True)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    billing_period = models.CharField(max_length=20, default='monthly')
    
    # Feature flags
    can_upload_documents = models.BooleanField(default=True)
    can_use_ai = models.BooleanField(default=False)
    can_access_library = models.BooleanField(default=False)
    allowed_subjects_count = models.IntegerField(default=0)  # 0 = unlimited
    
    # Quotas
    monthly_ai_generations = models.IntegerField(default=0)  # 0 = unlimited for premium
    
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['price']
    
    def __str__(self):
        return f"{self.name} - R{self.price}/{self.billing_period}"

class UserSubscription(models.Model):
    """Tracks user subscriptions and payment status"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('pending', 'Pending Payment'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription_record')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Subscription dates
    started_at = models.DateTimeField(auto_now_add=True)
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # PayFast subscription token (for recurring payments)
    payfast_token = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.status})"
    
    @property
    def is_active(self):
        """Check if subscription is currently active"""
        from django.utils import timezone
        return self.status == 'active' and self.current_period_end > timezone.now()

class PayFastPayment(models.Model):
    """Records all PayFast payment transactions"""
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('complete', 'Complete'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subscription = models.ForeignKey(UserSubscription, on_delete=models.SET_NULL, null=True, blank=True)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    
    # PayFast transaction details
    payfast_payment_id = models.CharField(max_length=100, unique=True)
    merchant_id = models.CharField(max_length=100)
    amount_gross = models.DecimalField(max_digits=10, decimal_places=2)
    amount_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_net = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_status_text = models.CharField(max_length=50, blank=True)
    
    # ITN data
    itn_data = models.JSONField(null=True, blank=True)  # Store raw ITN notification
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payment {self.payfast_payment_id} - {self.user.username} - R{self.amount_gross}"