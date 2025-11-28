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

class FormattedPaper(models.Model):
    """AI-reformatted exam papers with extracted questions and memos"""
    QUESTION_TYPE_CHOICES = [
        ('mcq', 'Multiple Choice'),
        ('structured', 'Structured'),
        ('free_response', 'Free Response'),
        ('mixed', 'Mixed'),
    ]
    
    # Link to original past paper
    source_paper = models.ForeignKey(PastPaper, on_delete=models.CASCADE, related_name='formatted_versions')
    
    # Metadata (inherited from source paper for quick filtering)
    title = models.CharField(max_length=300)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)
    exam_board = models.CharField(max_length=50, choices=PastPaper.EXAM_BOARD_CHOICES)
    year = models.IntegerField()
    
    # Formatted content
    questions_json = models.JSONField()
    memo_json = models.JSONField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES, default='mixed')
    total_questions = models.IntegerField(default=0)
    total_marks = models.IntegerField(default=0)
    
    # Image storage - directory path where extracted images are stored
    images_directory = models.CharField(max_length=500, blank=True)
    has_extracted_images = models.BooleanField(default=False)
    
    # AI processing metadata
    is_ai_generated = models.BooleanField(default=True)
    ai_model_used = models.CharField(max_length=50, blank=True)
    processing_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='pending')
    error_message = models.TextField(blank=True)
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subject', 'grade', 'exam_board']),
            models.Index(fields=['processing_status']),
            models.Index(fields=['is_published']),
        ]
    
    def __str__(self):
        return f"Formatted: {self.title}"
    
    @property
    def has_images(self):
        """Check if any questions contain image references"""
        if not self.questions_json:
            return False
        for q in self.questions_json.get('questions', []):
            if q.get('image_path') or any(opt.get('image_path') for opt in q.get('options', [])):
                return True
        return False

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

class Announcement(models.Model):
    """Platform announcements and notifications"""
    TARGET_CHOICES = [
        ('all', 'All Users'),
        ('teachers', 'Teachers Only'),
        ('content_managers', 'Content Managers Only'),
        ('admins', 'Admins Only'),
    ]
    
    PRIORITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]
    
    DISPLAY_CHOICES = [
        ('banner', 'Banner'),
        ('modal', 'Modal'),
    ]
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    target_audience = models.CharField(max_length=20, choices=TARGET_CHOICES, default='all')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='info')
    display_type = models.CharField(max_length=10, choices=DISPLAY_CHOICES, default='banner')
    
    # Scheduling
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Track which users have dismissed this announcement
    dismissed_by = models.ManyToManyField(User, related_name='dismissed_announcements', blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.target_audience})"
    
    def is_visible_to(self, user):
        """Check if announcement should be shown to this user"""
        from django.utils import timezone
        
        # Check if active and not expired
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        
        # Check if user has dismissed it
        if user in self.dismissed_by.all():
            return False
        
        # Check target audience
        if self.target_audience == 'all':
            return True
        elif self.target_audience == 'teachers':
            return not user.is_staff
        elif self.target_audience == 'content_managers':
            return user.groups.filter(name='content_manager').exists()
        elif self.target_audience == 'admins':
            return user.is_staff
        
        return False

class EmailBlast(models.Model):
    """Email campaigns and bulk communications"""
    TARGET_CHOICES = [
        ('all', 'All Users'),
        ('teachers', 'Teachers Only'),
        ('content_managers', 'Content Managers Only'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]
    
    subject = models.CharField(max_length=200)
    message = models.TextField()
    target_audience = models.CharField(max_length=20, choices=TARGET_CHOICES, default='all')
    
    # Tracking
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    recipient_count = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.subject} - {self.target_audience} ({self.status})"


class StudentProfile(models.Model):
    """Student user profile - independent from teacher system"""
    SUBSCRIPTION_CHOICES = [
        ('free', 'Free'),
        ('pro', 'Pro - R100/month'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    subscription = models.CharField(max_length=20, choices=SUBSCRIPTION_CHOICES, default='free')
    parent_email = models.EmailField(blank=True)
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True)
    email_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True)
    verification_token_created = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    onboarding_completed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Student: {self.user.username}"
    
    def get_exam_board_limit(self):
        """Free: 2 boards, Pro: 5 boards"""
        return 2 if self.subscription == 'free' else 5
    
    def get_subject_limit_per_board(self):
        """Maximum 10 subjects per board"""
        return 10


class StudentExamBoard(models.Model):
    """Student's selected exam boards"""
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='exam_boards')
    exam_board = models.ForeignKey(ExamBoard, on_delete=models.CASCADE)
    selected_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('student', 'exam_board')
    
    def __str__(self):
        return f"{self.student.user.username} - {self.exam_board.abbreviation}"


class StudentSubject(models.Model):
    """Student's selected subjects per exam board"""
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='subjects')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    exam_board = models.ForeignKey(ExamBoard, on_delete=models.CASCADE)
    selected_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('student', 'subject', 'exam_board')
    
    def __str__(self):
        return f"{self.student.user.username} - {self.subject.name} ({self.exam_board.abbreviation})"


class Note(models.Model):
    """Study notes uploaded by content managers"""
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    exam_board = models.ForeignKey(ExamBoard, on_delete=models.CASCADE)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200)
    
    full_version = models.FileField(upload_to='notes/full/%Y/%m/', null=True, blank=True)
    summary_version = models.FileField(upload_to='notes/summary/%Y/%m/', null=True, blank=True)
    full_version_text = models.TextField(blank=True)
    summary_version_text = models.TextField(blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['subject', 'topic']
    
    def __str__(self):
        return f"{self.title} - {self.subject.name}"


class Flashcard(models.Model):
    """Flashcards for memorization"""
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    exam_board = models.ForeignKey(ExamBoard, on_delete=models.CASCADE)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200)
    
    front_text = models.TextField()
    back_text = models.TextField()
    image_front = models.ImageField(upload_to='flashcards/images/', null=True, blank=True)
    image_back = models.ImageField(upload_to='flashcards/images/', null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['subject', 'topic']
    
    def __str__(self):
        return f"{self.subject.name} - {self.topic[:50]}"


class InteractiveQuestion(models.Model):
    """Interactive questions for quizzes"""
    QUESTION_TYPES = [
        ('mcq', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('fill_blank', 'Fill in the Blank'),
        ('matching', 'Matching'),
        ('essay', 'Essay/Free Response'),
    ]
    
    DIFFICULTY_LEVELS = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    exam_board = models.ForeignKey(ExamBoard, on_delete=models.CASCADE)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200)
    
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_LEVELS)
    
    question_text = models.TextField()
    question_image = models.ImageField(upload_to='questions/images/', null=True, blank=True)
    
    # For MCQ - JSON array of options
    options = models.JSONField(null=True, blank=True)
    
    # Correct answer(s) - can be text, index, or JSON for complex types
    correct_answer = models.TextField()
    
    # For matching questions - JSON with pairs
    matching_pairs = models.JSONField(null=True, blank=True)
    
    explanation = models.TextField(blank=True)
    points = models.IntegerField(default=1)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['subject', 'topic', 'difficulty']
    
    def __str__(self):
        return f"{self.question_type} - {self.topic[:50]}"


class StudentQuiz(models.Model):
    """Interactive quiz collections for students"""
    LENGTH_CHOICES = [
        (5, '5 Questions'),
        (10, '10 Questions'),
        (20, '20 Questions'),
        (50, '50 Questions'),
    ]
    
    DIFFICULTY_LEVELS = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
        ('mixed', 'Mixed'),
    ]
    
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    exam_board = models.ForeignKey(ExamBoard, on_delete=models.CASCADE)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200)
    
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_LEVELS)
    length = models.IntegerField(choices=LENGTH_CHOICES, default=10)
    
    questions = models.ManyToManyField(InteractiveQuestion, related_name='student_quizzes')
    
    is_pro_content = models.BooleanField(default=False)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Student Quizzes'
    
    def __str__(self):
        return f"{self.title} - {self.subject.name}"


class StudentQuizAttempt(models.Model):
    """Student quiz attempts and results"""
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(StudentQuiz, on_delete=models.CASCADE)
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Student preferences
    is_timed = models.BooleanField(default=False)
    time_limit_minutes = models.IntegerField(null=True, blank=True)
    show_instant_feedback = models.BooleanField(default=True)
    
    # Results
    answers = models.JSONField(default=dict)
    score = models.IntegerField(null=True, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.student.user.username} - {self.quiz.title}"


class StudentQuizQuota(models.Model):
    """Track free tier quiz quotas - 2 different quizzes per topic lifetime"""
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='quiz_quotas')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200)
    
    quizzes_completed = models.ManyToManyField(StudentQuiz, blank=True)
    attempt_count = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ('student', 'subject', 'topic')
    
    def __str__(self):
        return f"{self.student.user.username} - {self.topic}"
    
    def has_free_attempts_left(self):
        """Free users get 2 different quizzes per topic"""
        return self.quizzes_completed.count() < 2
    
    def can_attempt_quiz(self, quiz, is_pro):
        """Check if student can attempt this quiz"""
        if is_pro:
            return True
        
        # Free users: check if already attempted 2 different quizzes
        if self.quizzes_completed.count() >= 2:
            # Can only retry already attempted quizzes
            return quiz in self.quizzes_completed.all()
        
        return True


class ExamPaper(models.Model):
    """Full exam papers for practice"""
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    exam_board = models.ForeignKey(ExamBoard, on_delete=models.CASCADE)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)
    year = models.IntegerField(null=True, blank=True)
    
    paper_file = models.FileField(upload_to='exam_papers/%Y/%m/')
    marking_scheme = models.FileField(upload_to='exam_papers/marking/%Y/%m/', null=True, blank=True)
    
    # Interactive version (questions extracted)
    has_interactive_version = models.BooleanField(default=False)
    interactive_questions = models.ManyToManyField(InteractiveQuestion, blank=True)
    
    is_pro_content = models.BooleanField(default=False)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-year', 'subject']
    
    def __str__(self):
        return f"{self.title} - {self.subject.name}"


class StudentProgress(models.Model):
    """Track student learning progress"""
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='progress')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200)
    
    quizzes_attempted = models.IntegerField(default=0)
    quizzes_passed = models.IntegerField(default=0)
    average_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    notes_viewed = models.BooleanField(default=False)
    flashcards_reviewed = models.IntegerField(default=0)
    
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('student', 'subject', 'topic')
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"{self.student.user.username} - {self.subject.name} - {self.topic}"


class OfficialExamPaper(models.Model):
    """Official exam papers from various boards for free download and AI training"""
    
    SESSION_CHOICES = [
        ('june', 'June'),
        ('november', 'November'),
        ('may', 'May/June'),
        ('february', 'February/March'),
        ('october', 'October/November'),
        ('summer', 'Summer'),
        ('winter', 'Winter'),
        ('other', 'Other'),
    ]
    
    PAPER_TYPE_CHOICES = [
        ('qp', 'Question Paper'),
        ('ms', 'Marking Scheme'),
        ('er', 'Examiner Report'),
        ('gt', 'Grade Thresholds'),
        ('ir', 'Insert/Resource Booklet'),
        ('specimen', 'Specimen Paper'),
        ('other', 'Other'),
    ]
    
    # Board and Subject (with ForeignKeys for proper filtering)
    exam_board = models.ForeignKey(ExamBoard, on_delete=models.CASCADE, help_text="Exam board")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True, blank=True, help_text="Optional subject mapping")
    subject_code = models.CharField(max_length=50, help_text="Official subject code (e.g., 0580, 9MA0, PHYS-01)")
    subject_name = models.CharField(max_length=200, blank=True, help_text="e.g., Mathematics, Physics")
    module_code = models.CharField(max_length=50, blank=True, help_text="Optional module/component code")
    
    # Paper details
    year = models.IntegerField(help_text="e.g., 2023")
    session = models.CharField(max_length=20, choices=SESSION_CHOICES)
    paper_number = models.CharField(max_length=20, help_text="e.g., 1, 2, 3, 4H, 1F")
    variant = models.CharField(max_length=10, blank=True, help_text="e.g., 1, 2, 3 for Cambridge variants")
    paper_type = models.CharField(max_length=20, choices=PAPER_TYPE_CHOICES, default='qp')
    
    # File storage
    original_filename = models.CharField(max_length=255, help_text="Original file name for reference")
    file = models.FileField(upload_to='official_exam_papers/%Y/%m/')
    
    # Metadata and flags
    metadata_json = models.JSONField(default=dict, blank=True, help_text="Additional parsed metadata")
    is_public = models.BooleanField(default=True, help_text="Visible on public download page")
    can_use_for_training = models.BooleanField(default=True, help_text="Use for AI training")
    
    # Tracking
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-year', 'exam_board', 'subject_code', 'session', 'paper_number']
        unique_together = [
            ('exam_board', 'subject_code', 'year', 'session', 'paper_number', 'variant', 'paper_type')
        ]
        indexes = [
            models.Index(fields=['exam_board', 'subject_code', 'year']),
            models.Index(fields=['is_public']),
            models.Index(fields=['subject', 'year']),
        ]
    
    def __str__(self):
        variant_str = f"v{self.variant}" if self.variant else ""
        return f"{self.exam_board.abbreviation} {self.subject_code} {self.year} {self.session} Paper {self.paper_number}{variant_str}"
    
    def get_display_name(self):
        """Generate human-readable display name"""
        parts = [self.exam_board.name_full, self.subject_name or self.subject_code]
        parts.append(f"({self.year})")
        parts.append(self.get_session_display())
        parts.append(f"Paper {self.paper_number}")
        if self.variant:
            parts.append(f"Variant {self.variant}")
        parts.append(f"[{self.get_paper_type_display()}]")
        return " ".join(parts)
    
    def get_search_text(self):
        """Combined text for full-text search"""
        board_name = self.exam_board.name_full if self.exam_board else ""
        return f"{board_name} {self.subject_code} {self.subject_name} {self.year} {self.session} {self.paper_number} {self.variant} {self.original_filename}"


class TeacherAssessment(models.Model):
    """Teacher-created assessments (exams, tests, assignments, homework)"""
    
    CATEGORY_CHOICES = [
        ('exam', 'Exam'),
        ('test', 'Test'),
        ('assignment', 'Assignment'),
        ('homework', 'Homework'),
        ('classwork', 'Classwork'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assessments')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True)
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True, blank=True)
    
    time_limit = models.IntegerField(null=True, blank=True, help_text="Time limit in minutes")
    total_marks = models.IntegerField(default=0)
    passing_marks = models.IntegerField(null=True, blank=True)
    instructions = models.TextField(blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_shuffle_questions = models.BooleanField(default=False)
    show_correct_answers = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['teacher', 'category']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"
    
    def get_question_count(self):
        return self.questions.count()
    
    def calculate_total_marks(self):
        return self.questions.aggregate(total=models.Sum('marks'))['total'] or 0


class TeacherQuestion(models.Model):
    """Questions within a teacher assessment"""
    
    QUESTION_TYPE_CHOICES = [
        ('mcq', 'Multiple Choice'),
        ('mcq_multi', 'Multiple Choice (Multiple Answers)'),
        ('true_false', 'True/False'),
        ('short_answer', 'Short Answer'),
        ('long_answer', 'Long Answer / Essay'),
        ('matching', 'Matching'),
        ('fill_blank', 'Fill in the Blank'),
    ]
    
    assessment = models.ForeignKey(TeacherAssessment, on_delete=models.CASCADE, related_name='questions')
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES)
    question_text = models.TextField()
    question_image = models.ImageField(upload_to='assessment_questions/%Y/%m/', null=True, blank=True)
    
    marks = models.IntegerField(default=1)
    order = models.IntegerField(default=0)
    
    correct_answer = models.TextField(blank=True, help_text="For short/long answer - expected answer or keywords")
    explanation = models.TextField(blank=True, help_text="Explanation shown after answering")
    
    is_required = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'id']
    
    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}..."


class TeacherQuestionOption(models.Model):
    """Options for MCQ and matching questions"""
    
    question = models.ForeignKey(TeacherQuestion, on_delete=models.CASCADE, related_name='options')
    option_text = models.CharField(max_length=500)
    option_image = models.ImageField(upload_to='assessment_options/%Y/%m/', null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    
    match_pair = models.CharField(max_length=500, blank=True, help_text="For matching questions - the paired answer")
    
    class Meta:
        ordering = ['order', 'id']
    
    def __str__(self):
        return self.option_text[:50]