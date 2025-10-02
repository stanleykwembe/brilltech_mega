from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    Subject, Grade, ExamBoard, UserProfile, UploadedDocument, 
    GeneratedAssignment, UsageQuota, SubscriptionPlan, UserSubscription, PayFastPayment
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

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'status', 'current_period_start', 'current_period_end', 'selected_subject']
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
            'fields': ('selected_subject', 'payfast_token', 'created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'plan', 'selected_subject')

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

# Customize admin site
admin.site.site_header = "EduTech Platform Admin"
admin.site.site_title = "EduTech Admin"
admin.site.index_title = "Welcome to EduTech Administration"