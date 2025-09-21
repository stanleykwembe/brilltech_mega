from django.contrib import admin
from .models import Subject, Grade, ExamBoard, UserProfile, UploadedDocument, GeneratedAssignment, UsageQuota

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']

@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ['number']
    ordering = ['number']

@admin.register(ExamBoard)
class ExamBoardAdmin(admin.ModelAdmin):
    list_display = ['name_full', 'abbreviation']
    search_fields = ['name_full', 'abbreviation']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'subscription']
    list_filter = ['role', 'subscription']
    search_fields = ['user__username', 'user__email']

@admin.register(UploadedDocument)
class UploadedDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'uploaded_by', 'subject', 'grade', 'type', 'created_at']
    list_filter = ['type', 'subject', 'grade', 'board']
    search_fields = ['title', 'uploaded_by__username']
    date_hierarchy = 'created_at'

@admin.register(GeneratedAssignment)
class GeneratedAssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'teacher', 'subject', 'grade', 'question_type', 'due_date']
    list_filter = ['question_type', 'subject', 'grade', 'board']
    search_fields = ['title', 'teacher__username']
    date_hierarchy = 'created_at'

@admin.register(UsageQuota)
class UsageQuotaAdmin(admin.ModelAdmin):
    list_display = ['user']
    search_fields = ['user__username']