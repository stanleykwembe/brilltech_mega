from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    Subject, Grade, ExamBoard, UserProfile, UploadedDocument, 
    GeneratedAssignment, UsageQuota, SubscriptionPlan, UserSubscription, PayFastPayment,
    SubscribedSubject, PastPaper, Quiz, QuizResponse, ClassGroup, AssignmentShare,
    StudentSubscriptionPricing, StudentSubscription, SupportEnquiry
)

# Unregister the default User admin
admin.site.unregister(User)

# Define an inline admin descriptor for UserProfile model
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'

# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)

# Re-register UserAdmin
admin.site.register(User, UserAdmin)

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']
    ordering = ['name']

@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ['number']
    ordering = ['number']

@admin.register(ExamBoard)
class ExamBoardAdmin(admin.ModelAdmin):
    list_display = ['name_full', 'abbreviation']
    search_fields = ['name_full', 'abbreviation']
    ordering = ['name_full']

@admin.register(UploadedDocument)
class UploadedDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject', 'grade', 'board', 'type', 'uploaded_by', 'created_at']
    list_filter = ['type', 'subject', 'grade', 'board', 'created_at']
    search_fields = ['title', 'uploaded_by__username']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'uploaded_by', 'type')
        }),
        ('Academic Details', {
            'fields': ('subject', 'grade', 'board')
        }),
        ('File Information', {
            'fields': ('file', 'file_url')
        }),
        ('Additional Info', {
            'fields': ('tags', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('uploaded_by', 'subject', 'grade', 'board')

@admin.register(GeneratedAssignment)
class GeneratedAssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject', 'grade', 'board', 'question_type', 'teacher', 'created_at']
    list_filter = ['question_type', 'subject', 'grade', 'board', 'created_at']
    search_fields = ['title', 'teacher__username']
    readonly_fields = ['created_at', 'shared_link']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'teacher', 'question_type')
        }),
        ('Academic Details', {
            'fields': ('subject', 'grade', 'board')
        }),
        ('Assignment Details', {
            'fields': ('due_date', 'instructions', 'shared_link')
        }),
        ('Generated Content', {
            'fields': ('content',),
            'classes': ('collapse',)
        }),
        ('Additional Info', {
            'fields': ('file_url', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('teacher', 'subject', 'grade', 'board')

@admin.register(UsageQuota)
class UsageQuotaAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_total_lesson_plans', 'get_total_assignments']
    search_fields = ['user__username']
    readonly_fields = ['lesson_plans_used', 'assignments_used']
    
    def get_total_lesson_plans(self, obj):
        return sum(obj.lesson_plans_used.values()) if obj.lesson_plans_used else 0
    get_total_lesson_plans.short_description = 'Total Lesson Plans'
    
    def get_total_assignments(self, obj):
        return sum(obj.assignments_used.values()) if obj.assignments_used else 0
    get_total_assignments.short_description = 'Total Assignments'

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'plan_type', 'price', 'billing_period', 'can_use_ai', 'can_access_library', 'is_active']
    list_filter = ['plan_type', 'is_active', 'can_use_ai', 'can_access_library']
    search_fields = ['name', 'description']
    ordering = ['price']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'plan_type', 'price', 'billing_period', 'description', 'is_active')
        }),
        ('Features', {
            'fields': ('can_upload_documents', 'can_use_ai', 'can_access_library', 'allowed_subjects_count')
        }),
        ('Quotas', {
            'fields': ('monthly_ai_generations',)
        }),
    )

@admin.register(SubscribedSubject)
class SubscribedSubjectAdmin(admin.ModelAdmin):
    list_display = ['user', 'subject', 'subscribed_at']
    list_filter = ['subject']
    search_fields = ['user__username', 'subject__name']
    readonly_fields = ['subscribed_at']
    ordering = ['-subscribed_at']

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'status', 'current_period_start', 'current_period_end']
    list_filter = ['status', 'plan']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['started_at', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('User & Plan', {
            'fields': ('user', 'plan', 'status')
        }),
        ('Subscription Period', {
            'fields': ('started_at', 'current_period_start', 'current_period_end', 'cancelled_at')
        }),
        ('Additional Info', {
            'fields': ('payfast_token', 'created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'plan')

@admin.register(PayFastPayment)
class PayFastPaymentAdmin(admin.ModelAdmin):
    list_display = ['payfast_payment_id', 'user', 'plan', 'amount_gross', 'status', 'created_at', 'completed_at']
    list_filter = ['status', 'plan', 'created_at']
    search_fields = ['payfast_payment_id', 'user__username', 'user__email']
    readonly_fields = ['payfast_payment_id', 'created_at', 'completed_at', 'itn_data']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Payment Details', {
            'fields': ('user', 'subscription', 'plan', 'status', 'payment_status_text')
        }),
        ('PayFast Information', {
            'fields': ('payfast_payment_id', 'merchant_id')
        }),
        ('Amounts', {
            'fields': ('amount_gross', 'amount_fee', 'amount_net')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completed_at')
        }),
        ('Raw Data', {
            'fields': ('itn_data',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'plan', 'subscription')

@admin.register(PastPaper)
class PastPaperAdmin(admin.ModelAdmin):
    list_display = ['title', 'exam_board', 'subject', 'grade', 'paper_code', 'year', 'uploaded_at']
    list_filter = ['exam_board', 'subject', 'grade', 'year', 'paper_type']
    search_fields = ['title', 'paper_code', 'subject__name']
    readonly_fields = ['uploaded_at']
    ordering = ['-year', 'subject']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'exam_board', 'exam_board_custom', 'subject', 'grade')
        }),
        ('Paper Details', {
            'fields': ('paper_type', 'paper_code', 'year')
        }),
        ('Organization', {
            'fields': ('chapter', 'section')
        }),
        ('File & Upload Info', {
            'fields': ('file', 'notes', 'uploaded_by', 'uploaded_at')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('subject', 'grade', 'uploaded_by')

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject', 'grade', 'exam_board', 'difficulty_level', 'is_premium', 'is_ai_generated', 'times_used', 'is_active']
    list_filter = ['exam_board', 'subject', 'grade', 'difficulty_level', 'is_premium', 'is_ai_generated', 'is_active']
    search_fields = ['title', 'topic', 'subject__name']
    readonly_fields = ['times_used', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'subject', 'grade', 'exam_board')
        }),
        ('Content Organization', {
            'fields': ('topic', 'chapter', 'section')
        }),
        ('Quiz Settings', {
            'fields': ('google_form_link', 'is_premium', 'is_ai_generated', 'difficulty_level', 'is_active')
        }),
        ('Source & Analytics', {
            'fields': ('created_from_paper', 'times_used')
        }),
        ('Timestamps', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('subject', 'grade', 'created_from_paper', 'created_by')

@admin.register(QuizResponse)
class QuizResponseAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'quiz', 'teacher_code', 'score', 'submitted_at']
    list_filter = ['quiz', 'teacher', 'submitted_at']
    search_fields = ['student_name', 'teacher_code', 'quiz__title']
    readonly_fields = ['submitted_at']
    ordering = ['-submitted_at']
    
    fieldsets = (
        ('Student & Quiz', {
            'fields': ('student_name', 'quiz', 'teacher', 'teacher_code')
        }),
        ('Response Data', {
            'fields': ('score', 'answers_json', 'submitted_at')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('quiz', 'teacher')

@admin.register(ClassGroup)
class ClassGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'teacher', 'subject', 'grade', 'is_active', 'created_at']
    list_filter = ['subject', 'grade', 'is_active']
    search_fields = ['name', 'teacher__username', 'description']
    readonly_fields = ['created_at']
    ordering = ['teacher', 'name']

@admin.register(AssignmentShare)
class AssignmentShareAdmin(admin.ModelAdmin):
    list_display = ['assignment_title', 'class_group', 'teacher', 'shared_at', 'is_active']
    list_filter = ['shared_at']
    search_fields = ['teacher__username', 'class_group__name']
    readonly_fields = ['token', 'shared_at', 'last_accessed', 'view_count']
    ordering = ['-shared_at']

@admin.register(StudentSubscriptionPricing)
class StudentSubscriptionPricingAdmin(admin.ModelAdmin):
    list_display = ['starter_price', 'standard_price', 'all_access_price', 'tutor_addon_price', 'is_active', 'updated_at']
    fieldsets = (
        ('Starter Plan (R100)', {
            'fields': ('starter_price', 'starter_subjects', 'starter_boards'),
            'description': '2 subjects, 1 exam board'
        }),
        ('Standard Plan (R200)', {
            'fields': ('standard_price', 'standard_subjects', 'standard_boards'),
            'description': '4 subjects, any exam boards'
        }),
        ('Full Access Plan (R500)', {
            'fields': ('all_access_price',),
            'description': 'Unlimited subjects and exam boards'
        }),
        ('Tutor Add-on', {
            'fields': ('tutor_addon_price',),
            'description': 'Additional fee for tutor support'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )

@admin.register(StudentSubscription)
class StudentSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['student', 'plan', 'status', 'has_tutor_support', 'subjects_count', 'amount_paid', 'expires_at']
    list_filter = ['plan', 'status', 'has_tutor_support']
    search_fields = ['student__user__username', 'student__user__email']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

@admin.register(SupportEnquiry)
class SupportEnquiryAdmin(admin.ModelAdmin):
    list_display = ['subject', 'student', 'enquiry_type', 'priority', 'status', 'created_at', 'responded_at']
    list_filter = ['enquiry_type', 'priority', 'status', 'created_at']
    search_fields = ['subject', 'message', 'student__user__username']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Enquiry Details', {
            'fields': ('student', 'enquiry_type', 'subject', 'message', 'priority', 'status')
        }),
        ('Related Content', {
            'fields': ('related_subject', 'related_topic'),
            'classes': ('collapse',)
        }),
        ('Response', {
            'fields': ('response', 'responded_by', 'responded_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

# Customize admin site
admin.site.site_header = "EduTech Platform Admin"
admin.site.site_title = "EduTech Admin"
admin.site.index_title = "Welcome to EduTech Administration"