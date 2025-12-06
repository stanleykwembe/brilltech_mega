from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.db import IntegrityError
from django.db.models import Q
import json
import uuid
import os
import mimetypes
import secrets
from datetime import timedelta
from .models import Subject, Grade, ExamBoard, UserProfile, UploadedDocument, GeneratedAssignment, UsageQuota, ClassGroup, AssignmentShare, PasswordResetToken, SubscribedSubject
from .openai_service import generate_lesson_plan, generate_homework, generate_questions
from .subscription_utils import require_premium, get_user_subscription

def teacher_landing(request):
    """Teacher portal landing page with animations"""
    return render(request, 'core/teacher_landing.html')

def student_landing(request):
    """Student portal landing page with animations"""
    return render(request, 'core/student_landing.html')

def login_view(request):
    if request.method == 'POST':
        username_or_email = request.POST['username']
        password = request.POST['password']
        
        # Determine if input is email or username
        username = username_or_email
        if '@' in username_or_email:
            # Input might be email - try to look up username
            try:
                user_by_email = User.objects.get(email=username_or_email)
                username = user_by_email.username
            except User.DoesNotExist:
                # Email not found - treat as username (in case username contains @)
                username = username_or_email
        
        # Check if user exists and is inactive (unverified)
        try:
            existing_user = User.objects.get(username=username)
            if not existing_user.is_active:
                messages.error(request, 'Please verify your email address before signing in. Check your inbox for the verification link.')
                return render(request, 'core/login.html')
        except User.DoesNotExist:
            pass
        
        # Authenticate active user
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Check if this is a student account
            if hasattr(user, 'student_profile'):
                messages.error(request, 'This is a student account. Please use the student login page.')
                return render(request, 'core/login.html', {'show_student_link': True})
            
            login(request, user)
            # Redirect based on user role (3-way routing)
            if user.is_superuser or user.is_staff:
                # Admins go to admin panel
                return redirect('admin_dashboard')
            elif hasattr(user, 'userprofile') and user.userprofile.role == 'content_manager':
                # Content managers go to content portal
                return redirect('content_dashboard')
            else:
                # Teachers go to teacher dashboard
                return redirect('dashboard')
        else:
            messages.error(request, 'Invalid credentials. Please check your username/email and password.')
    return render(request, 'core/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

def require_teacher(view_func):
    """Decorator to ensure user is a teacher (not admin, content manager, or student)"""
    @login_required
    def wrapper(request, *args, **kwargs):
        # Redirect students to their own portal
        if hasattr(request.user, 'student_profile'):
            messages.info(request, 'Redirecting you to the student portal.')
            if not request.user.student_profile.onboarding_completed:
                return redirect('student_onboarding')
            return redirect('student_dashboard')
        
        # Redirect admins to admin panel
        if request.user.is_superuser or request.user.is_staff:
            return redirect('admin_dashboard')
        
        # Redirect content managers to content portal
        if hasattr(request.user, 'userprofile') and request.user.userprofile.role == 'content_manager':
            return redirect('content_dashboard')
        
        # Proceed with teacher view
        return view_func(request, *args, **kwargs)
    return wrapper

@require_teacher
def dashboard_view(request):
    # All role checks passed - safe to run teacher-specific queries
    profile = UserProfile.objects.get_or_create(user=request.user)[0]
    quota = UsageQuota.objects.get_or_create(user=request.user)[0]
    
    context = {
        'user_profile': profile,
        'quota': quota,
        'total_documents': UploadedDocument.objects.filter(uploaded_by=request.user).count(),
        'total_assignments': GeneratedAssignment.objects.filter(teacher=request.user).count(),
    }
    return render(request, 'core/dashboard.html', context)

@login_required
def lesson_plans_view(request):
    subscribed_subjects = SubscribedSubject.objects.filter(user=request.user).select_related('subject')
    grades = Grade.objects.all().order_by('number')
    boards = ExamBoard.objects.all().order_by('name_full')
    
    my_documents = UploadedDocument.objects.filter(
        uploaded_by=request.user,
        type='lesson_plan'
    ).order_by('-created_at')
    
    shared_documents = AssignmentShare.objects.filter(
        teacher=request.user,
        uploaded_document__type='lesson_plan',
        revoked_at__isnull=True
    ).select_related('class_group', 'uploaded_document').order_by('-shared_at')
    
    context = {
        'document_type': 'lesson_plan',
        'document_type_display': 'Lesson Plans',
        'subscribed_subjects': subscribed_subjects,
        'grades': grades,
        'boards': boards,
        'my_documents': my_documents,
        'shared_documents': shared_documents,
    }
    
    return render(request, 'core/document_type_base.html', context)

@login_required
def classwork_view(request):
    from .models import TeacherAssessment, ContentShare
    subscribed_subjects = SubscribedSubject.objects.filter(user=request.user).select_related('subject')
    grades = Grade.objects.all().order_by('number')
    boards = ExamBoard.objects.all().order_by('name_full')
    
    my_documents = UploadedDocument.objects.filter(
        uploaded_by=request.user,
        type='classwork'
    ).order_by('-created_at')
    
    shared_documents = AssignmentShare.objects.filter(
        teacher=request.user,
        uploaded_document__type='classwork',
        revoked_at__isnull=True
    ).select_related('class_group', 'uploaded_document').order_by('-shared_at')
    
    # Get teacher-created assessments
    my_assessments = TeacherAssessment.objects.filter(
        teacher=request.user,
        category='classwork'
    ).order_by('-created_at')
    
    # Get shared content (via ContentShare tokens)
    shared_assessments = ContentShare.objects.filter(
        teacher=request.user,
        assessment__isnull=False,
        assessment__category='classwork',
        is_active=True
    ).select_related('assessment', 'assessment__subject', 'assessment__grade').order_by('-created_at')
    
    shared_docs = ContentShare.objects.filter(
        teacher=request.user,
        document__isnull=False,
        document__type='classwork',
        is_active=True
    ).select_related('document').order_by('-created_at')
    
    # Add has_share flag to assessments and documents
    shared_assessment_ids = set(shared_assessments.values_list('assessment_id', flat=True))
    shared_doc_ids = set(shared_docs.values_list('document_id', flat=True))
    
    for assessment in my_assessments:
        assessment.has_share = assessment.id in shared_assessment_ids
    
    for doc in my_documents:
        doc.has_share = doc.id in shared_doc_ids
    
    context = {
        'document_type': 'classwork',
        'document_type_display': 'Classwork',
        'subscribed_subjects': subscribed_subjects,
        'grades': grades,
        'boards': boards,
        'my_documents': my_documents,
        'shared_documents': shared_documents,
        'my_assessments': my_assessments,
        'shared_assessments': shared_assessments,
        'shared_docs': shared_docs,
    }
    
    return render(request, 'core/document_type_base.html', context)

@login_required
def homework_view(request):
    from .models import TeacherAssessment, ContentShare
    subscribed_subjects = SubscribedSubject.objects.filter(user=request.user).select_related('subject')
    grades = Grade.objects.all().order_by('number')
    boards = ExamBoard.objects.all().order_by('name_full')
    
    my_documents = UploadedDocument.objects.filter(
        uploaded_by=request.user,
        type='homework'
    ).order_by('-created_at')
    
    shared_documents = AssignmentShare.objects.filter(
        teacher=request.user,
        uploaded_document__type='homework',
        revoked_at__isnull=True
    ).select_related('class_group', 'uploaded_document').order_by('-shared_at')
    
    # Get teacher-created assessments
    my_assessments = TeacherAssessment.objects.filter(
        teacher=request.user,
        category='homework'
    ).order_by('-created_at')
    
    # Get shared content (via ContentShare tokens)
    shared_assessments = ContentShare.objects.filter(
        teacher=request.user,
        assessment__isnull=False,
        assessment__category='homework',
        is_active=True
    ).select_related('assessment', 'assessment__subject', 'assessment__grade').order_by('-created_at')
    
    shared_docs = ContentShare.objects.filter(
        teacher=request.user,
        document__isnull=False,
        document__type='homework',
        is_active=True
    ).select_related('document').order_by('-created_at')
    
    # Add has_share flag to assessments and documents
    shared_assessment_ids = set(shared_assessments.values_list('assessment_id', flat=True))
    shared_doc_ids = set(shared_docs.values_list('document_id', flat=True))
    
    for assessment in my_assessments:
        assessment.has_share = assessment.id in shared_assessment_ids
    
    for doc in my_documents:
        doc.has_share = doc.id in shared_doc_ids
    
    context = {
        'document_type': 'homework',
        'document_type_display': 'Homework',
        'subscribed_subjects': subscribed_subjects,
        'grades': grades,
        'boards': boards,
        'my_documents': my_documents,
        'shared_documents': shared_documents,
        'my_assessments': my_assessments,
        'shared_assessments': shared_assessments,
        'shared_docs': shared_docs,
    }
    
    return render(request, 'core/document_type_base.html', context)

@login_required
def tests_view(request):
    from .models import TeacherAssessment, ContentShare
    subscribed_subjects = SubscribedSubject.objects.filter(user=request.user).select_related('subject')
    grades = Grade.objects.all().order_by('number')
    boards = ExamBoard.objects.all().order_by('name_full')
    
    my_documents = UploadedDocument.objects.filter(
        uploaded_by=request.user,
        type='test'
    ).order_by('-created_at')
    
    shared_documents = AssignmentShare.objects.filter(
        teacher=request.user,
        uploaded_document__type='test',
        revoked_at__isnull=True
    ).select_related('class_group', 'uploaded_document').order_by('-shared_at')
    
    # Get teacher-created assessments
    my_assessments = TeacherAssessment.objects.filter(
        teacher=request.user,
        category='test'
    ).order_by('-created_at')
    
    # Get shared content (via ContentShare tokens)
    shared_assessments = ContentShare.objects.filter(
        teacher=request.user,
        assessment__isnull=False,
        assessment__category='test',
        is_active=True
    ).select_related('assessment', 'assessment__subject', 'assessment__grade').order_by('-created_at')
    
    shared_docs = ContentShare.objects.filter(
        teacher=request.user,
        document__isnull=False,
        document__type='test',
        is_active=True
    ).select_related('document').order_by('-created_at')
    
    # Add has_share flag to assessments and documents
    shared_assessment_ids = set(shared_assessments.values_list('assessment_id', flat=True))
    shared_doc_ids = set(shared_docs.values_list('document_id', flat=True))
    
    for assessment in my_assessments:
        assessment.has_share = assessment.id in shared_assessment_ids
    
    for doc in my_documents:
        doc.has_share = doc.id in shared_doc_ids
    
    context = {
        'document_type': 'test',
        'document_type_display': 'Tests',
        'subscribed_subjects': subscribed_subjects,
        'grades': grades,
        'boards': boards,
        'my_documents': my_documents,
        'shared_documents': shared_documents,
        'my_assessments': my_assessments,
        'shared_assessments': shared_assessments,
        'shared_docs': shared_docs,
    }
    
    return render(request, 'core/document_type_base.html', context)

@login_required
def exams_view(request):
    from .models import TeacherAssessment, ContentShare
    subscribed_subjects = SubscribedSubject.objects.filter(user=request.user).select_related('subject')
    grades = Grade.objects.all().order_by('number')
    boards = ExamBoard.objects.all().order_by('name_full')
    
    my_documents = UploadedDocument.objects.filter(
        uploaded_by=request.user,
        type='exam'
    ).order_by('-created_at')
    
    shared_documents = AssignmentShare.objects.filter(
        teacher=request.user,
        uploaded_document__type='exam',
        revoked_at__isnull=True
    ).select_related('class_group', 'uploaded_document').order_by('-shared_at')
    
    # Get teacher-created assessments
    my_assessments = TeacherAssessment.objects.filter(
        teacher=request.user,
        category='exam'
    ).order_by('-created_at')
    
    # Get shared content (via ContentShare tokens)
    shared_assessments = ContentShare.objects.filter(
        teacher=request.user,
        assessment__isnull=False,
        assessment__category='exam',
        is_active=True
    ).select_related('assessment', 'assessment__subject', 'assessment__grade').order_by('-created_at')
    
    shared_docs = ContentShare.objects.filter(
        teacher=request.user,
        document__isnull=False,
        document__type='exam',
        is_active=True
    ).select_related('document').order_by('-created_at')
    
    # Add has_share flag to assessments and documents
    shared_assessment_ids = set(shared_assessments.values_list('assessment_id', flat=True))
    shared_doc_ids = set(shared_docs.values_list('document_id', flat=True))
    
    for assessment in my_assessments:
        assessment.has_share = assessment.id in shared_assessment_ids
    
    for doc in my_documents:
        doc.has_share = doc.id in shared_doc_ids
    
    context = {
        'document_type': 'exam',
        'document_type_display': 'Exams',
        'subscribed_subjects': subscribed_subjects,
        'grades': grades,
        'boards': boards,
        'my_documents': my_documents,
        'shared_documents': shared_documents,
        'my_assessments': my_assessments,
        'shared_assessments': shared_assessments,
        'shared_docs': shared_docs,
    }
    
    return render(request, 'core/document_type_base.html', context)

@login_required
def assignments_view(request):
    if request.method == 'POST' and 'upload_file' in request.POST:
        # Handle file upload for assignments
        from core.models import SubscribedSubject
        title = request.POST.get('title')
        subject_id = request.POST.get('subject')
        grade_id = request.POST.get('grade')
        board_id = request.POST.get('board')
        uploaded_file = request.FILES.get('file')
        
        if all([title, subject_id, grade_id, board_id, uploaded_file]):
            # Validate subject is subscribed
            if not SubscribedSubject.objects.filter(user=request.user, subject_id=subject_id).exists():
                messages.error(request, 'You can only upload assignments for your subscribed subjects.')
                return redirect('assignments')
            
            document = UploadedDocument(
                uploaded_by=request.user,
                title=title,
                subject_id=subject_id,
                grade_id=grade_id,
                board_id=board_id,
                type='homework',
                file=uploaded_file
            )
            document.save()
            messages.success(request, 'Assignment uploaded successfully!')
        else:
            messages.error(request, 'Please fill all required fields.')
    
    # Get user's subscribed subjects
    from core.models import SubscribedSubject
    user_subject_ids = SubscribedSubject.objects.filter(user=request.user).values_list('subject_id', flat=True)
    
    # Filter assignments by subscribed subjects
    assignments = GeneratedAssignment.objects.filter(
        teacher=request.user,
        subject_id__in=user_subject_ids
    ).order_by('-created_at')
    
    uploaded_assignments = UploadedDocument.objects.filter(
        uploaded_by=request.user,
        type='homework',
        subject_id__in=user_subject_ids
    ).order_by('-created_at')
    
    # Add sharing status to assignments for visual indicators
    for assignment in assignments:
        assignment.active_shares = AssignmentShare.objects.filter(
            generated_assignment=assignment,
            revoked_at__isnull=True
        ).count()
        assignment.is_shared = assignment.active_shares > 0
    
    for document in uploaded_assignments:
        document.active_shares = AssignmentShare.objects.filter(
            uploaded_document=document,
            revoked_at__isnull=True
        ).count()
        document.is_shared = document.active_shares > 0
    
    # Get shared assignments for the shared assignments tab
    shared_assignments = AssignmentShare.objects.filter(
        teacher=request.user
    ).select_related(
        'class_group', 'generated_assignment', 'uploaded_document'
    ).order_by('-shared_at')
    
    # Get teacher's classes for sharing modal
    teacher_classes = ClassGroup.objects.filter(teacher=request.user, is_active=True).order_by('name')
    
    # Only show subscribed subjects in the dropdown
    available_subjects = Subject.objects.filter(id__in=user_subject_ids)
    
    # Get teacher-created assessments
    from .models import TeacherAssessment, ContentShare
    my_assessments = TeacherAssessment.objects.filter(
        teacher=request.user,
        category='assignment'
    ).order_by('-created_at')
    
    # Get shared content (via ContentShare tokens)
    shared_assessments_content = ContentShare.objects.filter(
        teacher=request.user,
        assessment__isnull=False,
        assessment__category='assignment',
        is_active=True
    ).select_related('assessment', 'assessment__subject', 'assessment__grade').order_by('-created_at')
    
    shared_docs = ContentShare.objects.filter(
        teacher=request.user,
        document__isnull=False,
        document__type='assignment',
        is_active=True
    ).select_related('document').order_by('-created_at')
    
    context = {
        'assignments': assignments,
        'uploaded_assignments': uploaded_assignments,
        'documents': uploaded_assignments,  # For backward compatibility with template
        'shared_assignments': shared_assignments,
        'subjects': available_subjects,
        'grades': Grade.objects.all(),
        'exam_boards': ExamBoard.objects.all(),
        'teacher_classes': teacher_classes,
        'my_assessments': my_assessments,
        'shared_assessments': shared_assessments_content,
        'shared_docs': shared_docs,
    }
    return render(request, 'core/assignments.html', context)

@login_required
def questions_view(request):
    # Get user's subscribed subjects
    from core.models import SubscribedSubject
    user_subject_ids = SubscribedSubject.objects.filter(user=request.user).values_list('subject_id', flat=True)
    
    # Only show subscribed subjects in the dropdown
    available_subjects = Subject.objects.filter(id__in=user_subject_ids)
    
    context = {
        'subjects': available_subjects,
        'grades': Grade.objects.all(),
        'exam_boards': ExamBoard.objects.all(),
    }
    return render(request, 'core/questions.html', context)

@login_required
def documents_view(request):
    # Get user's subscribed subjects
    subscribed_subjects = SubscribedSubject.objects.filter(user=request.user).select_related('subject')
    user_subject_ids = subscribed_subjects.values_list('subject_id', flat=True)
    
    # Filter documents by subscribed subjects
    documents = UploadedDocument.objects.filter(
        uploaded_by=request.user,
        subject_id__in=user_subject_ids
    ).select_related('subject', 'grade', 'board').order_by('-created_at')
    
    context = {
        'documents': documents,
        'subscribed_subjects': subscribed_subjects,
        'subjects': Subject.objects.filter(id__in=user_subject_ids),  # for backward compatibility
        'grades': Grade.objects.all().order_by('number'),
        'boards': ExamBoard.objects.all().order_by('name_full'),
        'exam_boards': ExamBoard.objects.all().order_by('name_full'),  # for backward compatibility
    }
    return render(request, 'core/documents.html', context)

@login_required
def upload_document(request):
    """Handle document upload from My Documents page or specific document type pages"""
    if request.method == 'POST':
        try:
            title = request.POST.get('title')
            doc_type = request.POST.get('type') or request.POST.get('document_type', 'general')
            subject_id = request.POST.get('subject')
            grade_id = request.POST.get('grade')
            board_id = request.POST.get('board')
            tags = request.POST.get('tags', '')
            file = request.FILES.get('file')
            
            # Validate required fields
            if not all([title, subject_id, grade_id, board_id, file]):
                messages.error(request, 'All fields are required.')
                return redirect(request.META.get('HTTP_REFERER', 'documents'))
            
            # Validate user has access to this subject
            if not SubscribedSubject.objects.filter(user=request.user, subject_id=subject_id).exists():
                messages.error(request, 'You do not have access to this subject. Please check your subscription.')
                return redirect(request.META.get('HTTP_REFERER', 'documents'))
            
            # Create document
            document = UploadedDocument(
                uploaded_by=request.user,
                title=title,
                type=doc_type,
                subject_id=subject_id,
                grade_id=grade_id,
                board_id=board_id,
                tags=tags,
                file=file
            )
            document.save()
            
            messages.success(request, f'Document "{title}" uploaded successfully!')
            
            # Redirect back to referring page or documents view
            return redirect(request.META.get('HTTP_REFERER', 'documents'))
            
        except Exception as e:
            messages.error(request, f'Error uploading document: {str(e)}')
            return redirect(request.META.get('HTTP_REFERER', 'documents'))
    
    return redirect('documents')

@login_required
def subscription_view(request):
    profile = UserProfile.objects.get_or_create(user=request.user)[0]
    quota = UsageQuota.objects.get_or_create(user=request.user)[0]
    
    context = {
        'user_profile': profile,
        'quota': quota,
    }
    return render(request, 'core/subscription.html', context)

@login_required
def classes_view(request):
    """View for managing teacher's classes"""
    classes = ClassGroup.objects.filter(teacher=request.user, is_active=True).order_by('name')
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    
    context = {
        'classes': classes,
        'subjects': subjects,
        'grades': grades,
    }
    return render(request, 'core/classes.html', context)

@login_required
def create_class(request):
    """Create a new class"""
    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            subject_id = request.POST.get('subject')
            grade_id = request.POST.get('grade')
            
            if not name:
                messages.error(request, 'Class name is required.')
                return redirect('classes')
            
            # Check for duplicate class name
            if ClassGroup.objects.filter(teacher=request.user, name=name, is_active=True).exists():
                messages.error(request, f'You already have a class named "{name}".')
                return redirect('classes')
            
            # Create the class
            class_group = ClassGroup(
                teacher=request.user,
                name=name,
                description=description
            )
            
            if subject_id:
                try:
                    class_group.subject = Subject.objects.get(id=subject_id)
                except Subject.DoesNotExist:
                    pass
            
            if grade_id:
                try:
                    class_group.grade = Grade.objects.get(id=grade_id)
                except Grade.DoesNotExist:
                    pass
            
            class_group.save()
            messages.success(request, f'Class "{name}" created successfully!')
            
        except Exception as e:
            messages.error(request, f'Error creating class: {str(e)}')
    
    return redirect('classes')

@login_required
def edit_class(request, class_id):
    """Edit an existing class"""
    try:
        class_group = ClassGroup.objects.get(id=class_id, teacher=request.user, is_active=True)
        
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            subject_id = request.POST.get('subject')
            grade_id = request.POST.get('grade')
            
            if not name:
                messages.error(request, 'Class name is required.')
                return redirect('classes')
            
            # Check for duplicate class name (excluding current class)
            if ClassGroup.objects.filter(teacher=request.user, name=name, is_active=True).exclude(id=class_id).exists():
                messages.error(request, f'You already have a class named "{name}".')
                return redirect('classes')
            
            # Update the class
            class_group.name = name
            class_group.description = description
            
            if subject_id:
                try:
                    class_group.subject = Subject.objects.get(id=subject_id)
                except Subject.DoesNotExist:
                    class_group.subject = None
            else:
                class_group.subject = None
            
            if grade_id:
                try:
                    class_group.grade = Grade.objects.get(id=grade_id)
                except Grade.DoesNotExist:
                    class_group.grade = None
            else:
                class_group.grade = None
            
            class_group.save()
            messages.success(request, f'Class "{name}" updated successfully!')
            
    except ClassGroup.DoesNotExist:
        messages.error(request, 'Class not found or you do not have permission to edit it.')
    except Exception as e:
        messages.error(request, f'Error updating class: {str(e)}')
    
    return redirect('classes')

@login_required
def delete_class(request, class_id):
    """Delete (deactivate) a class"""
    if request.method == 'POST':
        try:
            class_group = ClassGroup.objects.get(id=class_id, teacher=request.user, is_active=True)
            
            # Check if class has active shares
            active_shares = AssignmentShare.objects.filter(class_group=class_group, revoked_at__isnull=True).count()
            if active_shares > 0:
                messages.error(request, f'Cannot delete class "{class_group.name}" because it has {active_shares} active shared assignments. Please revoke all shares first.')
                return redirect('classes')
            
            # Soft delete by marking as inactive
            class_group.is_active = False
            class_group.save()
            messages.success(request, f'Class "{class_group.name}" deleted successfully!')
            
        except ClassGroup.DoesNotExist:
            messages.error(request, 'Class not found or you do not have permission to delete it.')
        except Exception as e:
            messages.error(request, f'Error deleting class: {str(e)}')
    
    return redirect('classes')

@login_required
def delete_document(request, doc_id):
    """Delete a document"""
    if request.method == 'POST':
        document = get_object_or_404(UploadedDocument, id=doc_id, uploaded_by=request.user)
        doc_type = document.type
        document.delete()
        messages.success(request, 'Document deleted successfully!')
        
        # Redirect based on document type
        if doc_type == 'lesson_plan':
            return redirect('lesson_plans')
        else:
            return redirect('documents')
    
    return redirect('documents')

@login_required
def download_document(request, doc_id):
    """Securely download a document file with owner authorization"""
    document = get_object_or_404(UploadedDocument, id=doc_id, uploaded_by=request.user)
    
    if document.file and os.path.exists(document.file.path):
        # Get proper content type
        content_type, _ = mimetypes.guess_type(document.file.name)
        if not content_type:
            content_type = 'application/octet-stream'
        
        # Secure file serving
        with open(document.file.path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=content_type)
            # Get file extension for proper filename
            filename = f"{document.title}{os.path.splitext(document.file.name)[1]}"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    else:
        raise Http404("File not found")

@login_required
def view_document_inline(request, doc_id):
    """Serve document file inline for browser preview (mainly PDFs)"""
    document = get_object_or_404(UploadedDocument, id=doc_id, uploaded_by=request.user)
    
    if document.file and os.path.exists(document.file.path):
        # Get proper content type
        content_type, _ = mimetypes.guess_type(document.file.name)
        if not content_type:
            content_type = 'application/octet-stream'
        
        # For PDFs, serve inline
        file_extension = os.path.splitext(document.file.name)[1].lower()
        if file_extension == '.pdf':
            content_type = 'application/pdf'
        
        # Serve file inline for browser preview
        with open(document.file.path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=content_type)
            filename = f"{document.title}{os.path.splitext(document.file.name)[1]}"
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            response['Content-Security-Policy'] = "frame-ancestors 'self'"
            return response
    else:
        raise Http404("File not found")

@login_required
def view_document(request, doc_id):
    """View document content (for AI generated content or PDF preview)"""
    document = get_object_or_404(UploadedDocument, id=doc_id, uploaded_by=request.user)
    
    # Get AI content from database
    ai_content = document.ai_content
    
    # Check if document is a PDF for preview
    is_pdf = False
    if document.file:
        file_extension = os.path.splitext(document.file.name)[1].lower()
        is_pdf = file_extension == '.pdf'
    
    context = {
        'document': document,
        'ai_content': ai_content,
        'is_pdf': is_pdf
    }
    return render(request, 'core/view_document.html', context)

@login_required
@require_premium
def generate_assignment_ai(request):
    """Generate homework assignment using AI"""
    if request.method == 'POST':
        try:
            # Get user's AI model
            profile = UserProfile.objects.get(user=request.user)
            ai_model = profile.get_ai_model()
            
            subject = Subject.objects.get(id=request.POST.get('subject'))
            grade = Grade.objects.get(id=request.POST.get('grade'))
            board = ExamBoard.objects.get(id=request.POST.get('board'))
            topic = request.POST.get('topic')
            question_type = request.POST.get('question_type')
            num_questions = int(request.POST.get('num_questions', 5))
            due_date = request.POST.get('due_date')
            
            ai_content = generate_homework(
                subject.name, f"Grade {grade.number}", 
                board.abbreviation, topic, question_type, num_questions, model=ai_model
            )
            
            # Create assignment
            assignment = GeneratedAssignment(
                teacher=request.user,
                title=f"AI Generated: {topic}",
                subject=subject,
                grade=grade,
                board=board,
                question_type=question_type,
                due_date=due_date,
                shared_link=str(uuid.uuid4()),
                content=ai_content
            )
            assignment.save()
            
            messages.success(request, 'Assignment generated successfully!')
            return redirect('assignments')
            
        except Exception as e:
            messages.error(request, f'Failed to generate assignment: {str(e)}')
            return redirect('assignments')
    
    return redirect('assignments')

@login_required
@require_premium
def generate_questions_ai(request):
    """Generate practice questions using AI"""
    if request.method == 'POST':
        try:
            # Get user's AI model
            profile = UserProfile.objects.get(user=request.user)
            ai_model = profile.get_ai_model()
            
            subject = Subject.objects.get(id=request.POST.get('subject'))
            grade = Grade.objects.get(id=request.POST.get('grade'))
            board = ExamBoard.objects.get(id=request.POST.get('board'))
            topic = request.POST.get('topic')
            question_type = request.POST.get('question_type')
            difficulty = request.POST.get('difficulty', 'medium')
            
            ai_content = generate_questions(
                subject.name, f"Grade {grade.number}", 
                board.abbreviation, topic, question_type, difficulty, model=ai_model
            )
            
            return JsonResponse({
                'success': True,
                'content': ai_content
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

def signup_view(request):
    """Teacher signup with email verification and subject selection"""
    from core.models import Subject, SubscribedSubject
    
    subjects = Subject.objects.all().order_by('name')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        selected_subject_ids = request.POST.getlist('subjects')
        
        # Validation
        if not all([username, email, password, password_confirm, first_name, last_name]):
            messages.error(request, 'All fields are required.')
            return render(request, 'core/signup.html', {'subjects': subjects})
        
        if not selected_subject_ids:
            messages.error(request, 'Please select at least one subject to get started.')
            return render(request, 'core/signup.html', {'subjects': subjects})
        
        if len(selected_subject_ids) > 1:
            messages.error(request, 'Free plan allows 1 subject only. Upgrade after signup for more.')
            return render(request, 'core/signup.html', {'subjects': subjects})
        
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'core/signup.html', {'subjects': subjects})
        
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'core/signup.html', {'subjects': subjects})
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken. Try logging in instead.')
            return render(request, 'core/signup.html', {'subjects': subjects})
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'This email is already registered. Try logging in or reset your password.')
            return render(request, 'core/signup.html', {'subjects': subjects})
        
        try:
            # Create user (active but unverified)
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )
            
            # Create profile with verification token and teacher code
            verification_token = secrets.token_urlsafe(50)
            import random
            import string
            
            # Generate unique teacher code
            while True:
                teacher_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                if not UserProfile.objects.filter(teacher_code=teacher_code).exists():
                    break
            
            profile = UserProfile.objects.create(
                user=user,
                role='teacher',
                verification_token=verification_token,
                verification_token_created=timezone.now(),
                teacher_code=teacher_code
            )
            
            # Create subscribed subject entries
            for subject_id in selected_subject_ids:
                SubscribedSubject.objects.create(
                    user=user,
                    subject_id=subject_id
                )
            
            # Send verification email
            # Build proper verification URL using Replit domain
            verification_path = reverse('verify_email', kwargs={'token': verification_token})
            
            # Get the proper domain from environment or request
            import os
            replit_domain = os.environ.get('REPLIT_DEV_DOMAIN')
            if replit_domain:
                verification_url = f"https://{replit_domain}{verification_path}"
            else:
                verification_url = request.build_absolute_uri(verification_path)
            
            send_mail(
                subject='Welcome to EduTech Platform - Verify Your Email',
                message=f'''Hi {first_name},

Welcome to EduTech Platform! Please click the link below to verify your email address:

{verification_url}

This link will expire in 24 hours.

Best regards,
EduTech Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            
            # Auto-login the user
            login(request, user)
            
            messages.success(request, 'Welcome! Please verify your email to access all features.')
            return redirect('dashboard')
            
        except Exception as e:
            messages.error(request, f'Error creating account: {str(e)}')
            return render(request, 'core/signup.html', {'subjects': subjects})
    
    return render(request, 'core/signup.html', {'subjects': subjects})

def verify_email(request, token):
    """Verify email address with token"""
    try:
        # Find profile with matching token
        profile = UserProfile.objects.get(verification_token=token)
        
        # Check if token is expired (24 hours)
        if profile.verification_token_created and timezone.now() > profile.verification_token_created + timedelta(hours=24):
            messages.error(request, 'Verification link has expired. Please request a new one.')
            return redirect('login')
        
        # Activate user and clear token
        user = profile.user
        user.is_active = True
        user.save()
        
        profile.email_verified = True
        profile.verification_token = ''
        profile.verification_token_created = None
        profile.save()
        
        # Create usage quota
        UsageQuota.objects.get_or_create(user=user)
        
        messages.success(request, 'Email verified successfully! You can now sign in.')
        return redirect('login')
        
    except UserProfile.DoesNotExist:
        messages.error(request, 'Invalid verification link.')
        return redirect('login')

def resend_verification(request):
    """Resend verification email"""
    if request.method == 'POST':
        email = request.POST.get('email')
        
        try:
            user = User.objects.get(email=email, is_active=False)
            profile = user.userprofile
            
            # Generate new token
            verification_token = secrets.token_urlsafe(50)
            profile.verification_token = verification_token
            profile.verification_token_created = timezone.now()
            profile.save()
            
            # Send verification email
            verification_url = request.build_absolute_uri(
                reverse('verify_email', kwargs={'token': verification_token})
            )
            
            send_mail(
                subject='EduTech Platform - New Verification Link',
                message=f'''Hi {user.first_name},

Here is your new verification link:

{verification_url}

This link will expire in 24 hours.

Best regards,
EduTech Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            
            messages.success(request, 'Verification email sent! Please check your inbox.')
            
        except User.DoesNotExist:
            messages.error(request, 'No unverified account found with this email address.')
    
    return render(request, 'core/resend_verification.html')

def forgot_password(request):
    """Forgot password - send reset link"""
    if request.method == 'POST':
        email = request.POST.get('email')
        
        try:
            user = User.objects.get(email=email)
            
            # Generate reset token
            reset_token = secrets.token_urlsafe(50)
            expires_at = timezone.now() + timedelta(hours=1)
            
            # Create password reset token
            PasswordResetToken.objects.create(
                user=user,
                token=reset_token,
                expires_at=expires_at
            )
            
            # Build reset URL
            reset_path = reverse('reset_password', kwargs={'token': reset_token})
            
            # Get the proper domain from environment or request
            replit_domain = os.environ.get('REPLIT_DEV_DOMAIN')
            if replit_domain:
                reset_url = f"https://{replit_domain}{reset_path}"
            else:
                reset_url = request.build_absolute_uri(reset_path)
            
            # Send reset email
            send_mail(
                subject='Reset Your EduTech Password',
                message=f'''Hi {user.first_name},

We received a request to reset your password. Click the link below to reset it:

{reset_url}

This link will expire in 1 hour.

If you didn't request this, you can safely ignore this email.

Need help? Contact us at support@edutech.com

Best regards,
EduTech Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            
        except User.DoesNotExist:
            pass
        
        # Always show success message for security
        messages.success(request, 'If an account with that email exists, we have sent password reset instructions.')
        return redirect('login')
    
    return render(request, 'core/forgot_password.html')

def reset_password(request, token):
    """Reset password with token"""
    # Validate token on GET request
    try:
        reset_token = PasswordResetToken.objects.get(token=token)
        
        if not reset_token.is_valid():
            messages.error(request, 'This password reset link has expired or has already been used. Please request a new one.')
            return redirect('forgot_password')
        
        if request.method == 'POST':
            password = request.POST.get('password')
            password_confirm = request.POST.get('password_confirm')
            
            # Validate passwords
            if not password or not password_confirm:
                messages.error(request, 'Please fill in all fields.')
                return render(request, 'core/reset_password.html', {'token': token})
            
            if password != password_confirm:
                messages.error(request, 'Passwords do not match.')
                return render(request, 'core/reset_password.html', {'token': token})
            
            if len(password) < 8:
                messages.error(request, 'Password must be at least 8 characters long.')
                return render(request, 'core/reset_password.html', {'token': token})
            
            # Validate token again
            if not reset_token.is_valid():
                messages.error(request, 'This password reset link has expired or has already been used.')
                return redirect('forgot_password')
            
            # Update password
            user = reset_token.user
            user.set_password(password)
            user.save()
            
            # Mark token as used
            reset_token.used = True
            reset_token.save()
            
            messages.success(request, 'Your password has been reset successfully! You can now sign in with your new password.')
            return redirect('login')
        
        return render(request, 'core/reset_password.html', {'token': token})
        
    except PasswordResetToken.DoesNotExist:
        messages.error(request, 'Invalid password reset link. Please request a new one.')
        return redirect('forgot_password')

@login_required
def account_settings(request):
    """User account settings page with profile, security, and notifications"""
    from core.models import Subject, SubscribedSubject
    
    profile = UserProfile.objects.get_or_create(user=request.user)[0]
    subjects = Subject.objects.all().order_by('name')
    user_subjects = SubscribedSubject.objects.filter(user=request.user).values_list('subject_id', flat=True)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_subjects':
            try:
                selected_subject_ids = request.POST.getlist('subjects')
                max_subjects = profile.get_subject_limit()
                
                if not selected_subject_ids:
                    messages.error(request, 'Please select at least one subject.')
                    return redirect('account_settings')
                
                if len(selected_subject_ids) > max_subjects:
                    messages.error(request, f'Your {profile.get_subscription_display()} plan allows up to {max_subjects} subject(s). Upgrade to add more.')
                    return redirect('account_settings')
                
                # Remove old subjects and add new ones
                SubscribedSubject.objects.filter(user=request.user).delete()
                for subject_id in selected_subject_ids:
                    SubscribedSubject.objects.create(
                        user=request.user,
                        subject_id=subject_id
                    )
                
                messages.success(request, f'Successfully updated your subjects! You now have {len(selected_subject_ids)} subject(s) selected.')
                
            except Exception as e:
                messages.error(request, f'Error updating subjects: {str(e)}')
        
        elif action == 'update_profile':
            try:
                first_name = request.POST.get('first_name', '').strip()
                last_name = request.POST.get('last_name', '').strip()
                email = request.POST.get('email', '').strip()
                bio = request.POST.get('bio', '').strip()
                institution = request.POST.get('institution', '').strip()
                email_notifications = request.POST.get('email_notifications') == 'on'
                
                if not all([first_name, last_name, email]):
                    messages.error(request, 'First name, last name, and email are required.')
                    return redirect('account_settings')
                
                if email != request.user.email:
                    if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                        messages.error(request, 'Email address is already in use.')
                        return redirect('account_settings')
                    request.user.email = email
                    profile.email_verified = False
                
                request.user.first_name = first_name
                request.user.last_name = last_name
                request.user.save()
                
                profile.bio = bio
                profile.institution = institution
                profile.email_notifications = email_notifications
                profile.save()
                
                messages.success(request, 'Profile updated successfully!')
                
            except Exception as e:
                messages.error(request, f'Error updating profile: {str(e)}')
        
        elif action == 'change_password':
            try:
                current_password = request.POST.get('current_password', '')
                new_password = request.POST.get('new_password', '')
                confirm_password = request.POST.get('confirm_password', '')
                
                if not request.user.check_password(current_password):
                    messages.error(request, 'Current password is incorrect.')
                    return redirect('account_settings')
                
                if len(new_password) < 8:
                    messages.error(request, 'New password must be at least 8 characters long.')
                    return redirect('account_settings')
                
                if new_password != confirm_password:
                    messages.error(request, 'New passwords do not match.')
                    return redirect('account_settings')
                
                request.user.set_password(new_password)
                request.user.save()
                
                update_session_auth_hash(request, request.user)
                
                messages.success(request, 'Password changed successfully!')
                
            except Exception as e:
                messages.error(request, f'Error changing password: {str(e)}')
        
        elif action == 'resend_verification':
            try:
                if profile.email_verified:
                    messages.info(request, 'Your email is already verified.')
                    return redirect('account_settings')
                
                verification_token = secrets.token_urlsafe(50)
                profile.verification_token = verification_token
                profile.verification_token_created = timezone.now()
                profile.save()
                
                verification_url = request.build_absolute_uri(
                    reverse('verify_email', kwargs={'token': verification_token})
                )
                
                send_mail(
                    subject='EduTech Platform - Verify Your Email',
                    message=f'''Hi {request.user.first_name},
                    
Please verify your email address by clicking the link below:

{verification_url}

This link will expire in 24 hours.

Best regards,
EduTech Team''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[request.user.email],
                    fail_silently=False,
                )
                
                messages.success(request, 'Verification email sent! Please check your inbox.')
                
            except Exception as e:
                messages.error(request, f'Error sending verification email: {str(e)}')
        
        return redirect('account_settings')
    
    ai_generations = UsageQuota.objects.get_or_create(user=request.user)[0]
    total_ai_gens = sum(ai_generations.lesson_plans_used.values()) + sum(ai_generations.assignments_used.values())
    
    documents_count = UploadedDocument.objects.filter(uploaded_by=request.user).count()
    assignments_count = GeneratedAssignment.objects.filter(teacher=request.user).count()
    shared_count = AssignmentShare.objects.filter(teacher=request.user, revoked_at__isnull=True).count()
    
    context = {
        'user_profile': profile,
        'total_ai_generations': total_ai_gens,
        'documents_count': documents_count,
        'assignments_count': assignments_count,
        'shared_count': shared_count,
        'subjects': subjects,
        'user_subjects': list(user_subjects),
        'max_subjects': profile.get_subject_limit(),
    }
    
    return render(request, 'core/account_settings.html', context)

@login_required
def revoke_share(request, share_id):
    """Revoke access to a shared assignment"""
    if request.method == 'POST':
        try:
            share = AssignmentShare.objects.get(
                id=share_id,
                teacher=request.user  # Ensure teacher owns the share
            )
            from django.utils import timezone
            share.revoked_at = timezone.now()
            share.save()
            messages.success(request, f'Access to "{share.assignment_title}" has been revoked.')
        except AssignmentShare.DoesNotExist:
            messages.error(request, 'Share not found or you do not have permission to revoke it.')
        except Exception as e:
            messages.error(request, f'Error revoking share: {str(e)}')
    
    return redirect('assignments')

@login_required
def create_share(request):
    """Create a new assignment share"""
    if request.method == 'POST':
        try:
            assignment_type = request.POST.get('assignment_type')  # 'generated' or 'uploaded'
            assignment_id = request.POST.get('assignment_id')
            class_name = request.POST.get('class_name')  # For now, just use class name directly
            due_date_str = request.POST.get('due_date')
            expiry_date_str = request.POST.get('expiry_date')
            
            # Parse due date if provided
            due_date = None
            if due_date_str:
                from django.utils.dateparse import parse_datetime, parse_date
                from django.utils import timezone
                try:
                    # Try to parse as date first, then datetime
                    parsed_date = parse_date(due_date_str)
                    if parsed_date:
                        # Convert date to datetime at end of day
                        from datetime import datetime, time
                        due_date = timezone.make_aware(
                            datetime.combine(parsed_date, time.max.replace(microsecond=0))
                        )
                    else:
                        due_date = parse_datetime(due_date_str)
                        # Make naive datetimes timezone-aware
                        if due_date and timezone.is_naive(due_date):
                            due_date = timezone.make_aware(due_date)
                except (ValueError, TypeError):
                    pass  # Leave due_date as None if parsing fails
            
            # Parse expiry date if provided
            expiry_date = None
            if expiry_date_str:
                from django.utils.dateparse import parse_datetime, parse_date
                from django.utils import timezone
                try:
                    # Try to parse as date first, then datetime
                    parsed_date = parse_date(expiry_date_str)
                    if parsed_date:
                        # Convert date to datetime at end of day
                        from datetime import datetime, time
                        expiry_date = timezone.make_aware(
                            datetime.combine(parsed_date, time.max.replace(microsecond=0))
                        )
                    else:
                        expiry_date = parse_datetime(expiry_date_str)
                        # Make naive datetimes timezone-aware
                        if expiry_date and timezone.is_naive(expiry_date):
                            expiry_date = timezone.make_aware(expiry_date)
                except (ValueError, TypeError):
                    pass  # Leave expiry_date as None if parsing fails
            
            # Get or create class group
            class_group, created = ClassGroup.objects.get_or_create(
                teacher=request.user,
                name=class_name,
                defaults={'description': f'Class for {class_name}'}
            )
            
            # Validate assignment ownership and create share
            share = None
            if assignment_type == 'generated':
                assignment = GeneratedAssignment.objects.get(
                    id=assignment_id, 
                    teacher=request.user
                )
                try:
                    share = AssignmentShare.objects.create(
                        teacher=request.user,
                        class_group=class_group,
                        generated_assignment=assignment,
                        due_date=due_date,
                        expires_at=expiry_date
                    )
                except IntegrityError:
                    # Handle duplicate active share
                    messages.error(request, f'Assignment "{assignment.title}" is already shared with {class_name}.')
                    return redirect('assignments')
                    
            elif assignment_type == 'uploaded':
                document = UploadedDocument.objects.get(
                    id=assignment_id,
                    uploaded_by=request.user
                )
                try:
                    share = AssignmentShare.objects.create(
                        teacher=request.user,
                        class_group=class_group,
                        uploaded_document=document,
                        due_date=due_date,
                        expires_at=expiry_date
                    )
                except IntegrityError:
                    # Handle duplicate active share
                    messages.error(request, f'Assignment "{document.title}" is already shared with {class_name}.')
                    return redirect('assignments')
            else:
                raise ValueError("Invalid assignment type")
            
            if share:
                # Generate share URL using reverse
                from django.urls import reverse
                share_url = request.build_absolute_uri(reverse('public_assignment', args=[share.token]))
                
                messages.success(request, f'Assignment shared successfully! Share URL: {share_url}')
                
                # Return the share URL in response (for AJAX if needed)
                if request.headers.get('Accept') == 'application/json':
                    import json
                    return HttpResponse(json.dumps({
                        'success': True,
                        'share_url': share_url,
                        'token': share.token
                    }), content_type='application/json')
            
        except (GeneratedAssignment.DoesNotExist, UploadedDocument.DoesNotExist):
            messages.error(request, 'Assignment not found or you do not have permission to share it.')
        except Exception as e:
            messages.error(request, f'Error creating share: {str(e)}')
    
    return redirect('assignments')

def public_assignment_view(request, token):
    """Public view for students to access shared assignments without login"""
    try:
        share = AssignmentShare.objects.select_related(
            'generated_assignment', 'uploaded_document', 'class_group'
        ).get(token=token)
        
        # Check if share is still active
        if not share.is_active:
            return render(request, 'core/share_expired.html', {
                'share': share,
                'reason': 'revoked' if share.revoked_at else 'expired'
            })
        
        # Update access tracking
        from django.utils import timezone
        share.view_count += 1
        share.last_accessed = timezone.now()
        share.save()
        
        # Determine content type and render appropriate template
        if share.generated_assignment:
            context = {
                'share': share,
                'assignment': share.generated_assignment,
                'content': share.generated_assignment.content,
                'assignment_type': 'generated'
            }
            return render(request, 'core/public_assignment.html', context)
        else:
            # For uploaded documents, we'll serve the file directly
            context = {
                'share': share,
                'document': share.uploaded_document,
                'assignment_type': 'uploaded'
            }
            return render(request, 'core/public_document.html', context)
            
    except AssignmentShare.DoesNotExist:
        return render(request, 'core/share_not_found.html')

def public_assignment_download(request, token):
    """Download endpoint for public shared assignments"""
    try:
        share = AssignmentShare.objects.select_related(
            'uploaded_document'
        ).get(token=token)
        
        # Check if share is still active
        if not share.is_active:
            return HttpResponse('This share has expired or been revoked.', status=403)
        
        # Only uploaded documents can be downloaded
        if not share.uploaded_document:
            return HttpResponse('This assignment cannot be downloaded.', status=400)
        
        # Update access tracking
        from django.utils import timezone
        share.view_count += 1
        share.last_accessed = timezone.now()
        share.save()
        
        # Serve the file
        document = share.uploaded_document
        file_path = document.file.path
        
        if os.path.exists(file_path):
            # Get the original file extension
            file_extension = os.path.splitext(document.file.name)[1]
            filename = f"{document.title}{file_extension}"
            
            # Get proper content type
            content_type, _ = mimetypes.guess_type(document.file.name)
            if not content_type:
                content_type = 'application/octet-stream'
            
            with open(file_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type=content_type)
                # Use inline for PDFs so they can be previewed in the browser
                if file_extension.lower() == '.pdf':
                    response['Content-Disposition'] = f'inline; filename="{filename}"'
                else:
                    response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
        else:
            return HttpResponse('File not found.', status=404)
            
    except AssignmentShare.DoesNotExist:
        return HttpResponse('Share not found.', status=404)

@login_required
def subscription_dashboard(request):
    """View current subscription and manage upgrades"""
    from .models import SubscriptionPlan, SubscribedSubject, UserSubscription, PayFastPayment
    
    # Get user profile with subscription info
    profile = UserProfile.objects.get(user=request.user)
    
    # Get active subscription if exists
    try:
        active_subscription = UserSubscription.objects.get(user=request.user, status='active')
    except UserSubscription.DoesNotExist:
        active_subscription = None
    
    # Get user's subscribed subjects
    subscribed_subjects = SubscribedSubject.objects.filter(user=request.user).select_related('subject')
    
    # Get all available plans
    available_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    
    # Get all subjects for selection
    all_subjects = Subject.objects.all().order_by('name')
    
    # Get usage quota info
    try:
        quota = UsageQuota.objects.get(user=request.user)
    except UsageQuota.DoesNotExist:
        quota = None
    
    # Calculate quota usage per subject
    subject_quotas = []
    for sub in subscribed_subjects:
        subject_id = str(sub.subject.id)
        used = quota.lesson_plans_used.get(subject_id, 0) if quota else 0
        limit = profile.get_lesson_plan_limit_per_subject()
        subject_quotas.append({
            'subject': sub.subject,
            'used': used,
            'limit': limit,
            'percentage': (used / limit * 100) if limit > 0 else 0
        })
    
    # Get payment history
    payment_history = PayFastPayment.objects.filter(
        user=request.user,
        status='complete'
    ).select_related('plan').order_by('-completed_at')[:10]
    
    context = {
        'profile': profile,
        'active_subscription': active_subscription,
        'subscribed_subjects': subscribed_subjects,
        'available_plans': available_plans,
        'all_subjects': all_subjects,
        'subject_quotas': subject_quotas,
        'subject_limit': profile.get_subject_limit(),
        'can_add_subjects': subscribed_subjects.count() < profile.get_subject_limit(),
        'payment_history': payment_history,
    }
    
    return render(request, 'core/subscription.html', context)

@login_required
def initiate_subscription(request, plan_id):
    """Initiate a subscription upgrade"""
    from .models import SubscriptionPlan, UserSubscription
    from .payfast_service import PayFastService
    from django.utils import timezone
    from datetime import timedelta
    
    plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
    
    if plan.plan_type == 'free':
        messages.info(request, 'You are already on the free plan.')
        return redirect('subscription_dashboard')
    
    try:
        user_subscription = UserSubscription.objects.get(user=request.user)
        user_subscription.plan = plan
        user_subscription.status = 'pending'
        user_subscription.save()
    except UserSubscription.DoesNotExist:
        user_subscription = UserSubscription.objects.create(
            user=request.user,
            plan=plan,
            status='pending',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
    
    if request.method == 'POST':
        selected_subject_id = request.POST.get('selected_subject')
        if plan.plan_type == 'growth' and selected_subject_id:
            subject = get_object_or_404(Subject, id=selected_subject_id)
            user_subscription.selected_subject = subject
            user_subscription.save()
    
    payment_data = PayFastService.generate_payment_form_data(
        user=request.user,
        plan=plan,
        subscription=user_subscription
    )
    
    payfast_url = PayFastService.get_payfast_url()
    
    context = {
        'payment_data': payment_data,
        'payfast_url': payfast_url,
        'plan': plan,
        'subscription': user_subscription,
    }
    
    return render(request, 'core/initiate_payment.html', context)

@csrf_exempt
def payfast_notify(request):
    """Handle PayFast ITN (Instant Transaction Notification)"""
    from .models import UserSubscription, SubscriptionPlan, PayFastPayment
    from .payfast_service import PayFastService
    from django.utils import timezone
    from datetime import timedelta
    import logging
    
    logger = logging.getLogger(__name__)
    
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
    
    logger.info(f'PayFast ITN received: {request.POST}')
    
    if not PayFastService.validate_itn_signature(request.POST):
        logger.error('Invalid PayFast signature')
        return HttpResponse('Invalid signature', status=400)
    
    if not PayFastService.verify_payment_with_payfast(request.POST):
        logger.error('PayFast server validation failed')
        return HttpResponse('Payment verification failed', status=400)
    
    if not PayFastService.validate_merchant_id(request.POST):
        logger.error('Invalid merchant ID')
        return HttpResponse('Invalid merchant', status=400)
    
    payment_status = request.POST.get('payment_status')
    user_id = request.POST.get('custom_str1')
    plan_id = request.POST.get('custom_str2')
    subscription_id = request.POST.get('custom_str3')
    payment_id = request.POST.get('pf_payment_id')
    amount_gross = request.POST.get('amount_gross')
    amount_fee = request.POST.get('amount_fee', 0)
    amount_net = request.POST.get('amount_net')
    merchant_id = request.POST.get('merchant_id')
    
    try:
        user = User.objects.get(id=user_id)
        plan = SubscriptionPlan.objects.get(id=plan_id)
        
        if not PayFastService.validate_payment_amount(request.POST, plan.price):
            logger.error(f'Payment amount mismatch: received {amount_gross}, expected {plan.price}')
            return HttpResponse('Payment amount mismatch', status=400)
        
        payment, created = PayFastPayment.objects.get_or_create(
            payfast_payment_id=payment_id,
            defaults={
                'user': user,
                'plan': plan,
                'merchant_id': merchant_id,
                'amount_gross': amount_gross,
                'amount_fee': amount_fee,
                'amount_net': amount_net,
                'status': 'pending',
                'payment_status_text': payment_status,
                'itn_data': dict(request.POST)
            }
        )
        
        if subscription_id:
            try:
                subscription = UserSubscription.objects.get(id=subscription_id)
                payment.subscription = subscription
            except UserSubscription.DoesNotExist:
                logger.warning(f'Subscription {subscription_id} not found')
        
        if payment_status == 'COMPLETE':
            payment.status = 'complete'
            payment.completed_at = timezone.now()
            payment.save()
            
            subscription, created = UserSubscription.objects.get_or_create(
                user=user,
                defaults={
                    'plan': plan,
                    'status': 'active',
                    'current_period_start': timezone.now(),
                    'current_period_end': timezone.now() + timedelta(days=30)
                }
            )
            
            if not created:
                subscription.plan = plan
                subscription.status = 'active'
                subscription.current_period_start = timezone.now()
                subscription.current_period_end = timezone.now() + timedelta(days=30)
                subscription.save()
            
            # Update UserProfile subscription field
            try:
                profile = UserProfile.objects.get(user=user)
                profile.subscription = plan.plan_type
                profile.save()
                logger.info(f'Updated UserProfile subscription to {plan.plan_type} for user {user.username}')
            except UserProfile.DoesNotExist:
                logger.error(f'UserProfile not found for user {user.username}')
            
            logger.info(f'Payment complete for user {user.username}, plan {plan.name}')
        else:
            payment.status = 'failed'
            payment.save()
            logger.warning(f'Payment failed with status: {payment_status}')
        
        return HttpResponse('OK', status=200)
        
    except Exception as e:
        logger.error(f'Error processing PayFast ITN: {str(e)}')
        return HttpResponse('Error processing payment', status=500)

def payment_success(request):
    """Redirect after successful payment"""
    from .models import UserSubscription, SubscriptionPlan, UserProfile, PayFastPayment
    from django.utils import timezone
    from datetime import timedelta
    from django.conf import settings
    
    # In sandbox mode, PayFast might not send ITN immediately
    # So we activate the subscription here as a fallback for testing
    if hasattr(settings, 'PAYFAST_MERCHANT_ID') and settings.PAYFAST_MERCHANT_ID == '10000100':
        try:
            # Get the latest pending subscription for this user
            subscription = UserSubscription.objects.filter(
                user=request.user,
                status='pending'
            ).order_by('-created_at').first()
            
            if subscription and subscription.plan.price > 0:
                # Activate the subscription
                subscription.status = 'active'
                subscription.current_period_start = timezone.now()
                subscription.current_period_end = timezone.now() + timedelta(days=30)
                subscription.save()
                
                # Update UserProfile subscription field
                profile = UserProfile.objects.get(user=request.user)
                profile.subscription = subscription.plan.plan_type
                profile.save()
                
                # Create payment record
                PayFastPayment.objects.create(
                    user=request.user,
                    subscription=subscription,
                    plan=subscription.plan,
                    payfast_payment_id=f'sandbox_{timezone.now().timestamp()}',
                    merchant_id=settings.PAYFAST_MERCHANT_ID,
                    amount_gross=subscription.plan.price,
                    amount_fee=0,
                    amount_net=subscription.plan.price,
                    status='complete',
                    payment_status_text='COMPLETE',
                    completed_at=timezone.now(),
                    itn_data={'sandbox': True}
                )
                
                messages.success(request, f'🎉 Subscription activated! You now have {subscription.plan.name} access.')
                return redirect('subscription_dashboard')
        except Exception as e:
            # Don't fail if this doesn't work - ITN will handle it
            logger.error(f'Error activating subscription in payment_success: {str(e)}')
            pass
    
    messages.success(request, 'Payment received! Your subscription is being activated.')
    return redirect('subscription_dashboard')

def payment_cancelled(request):
    """Redirect after cancelled payment"""
    messages.warning(request, 'Payment was cancelled. You can try again anytime.')
    return redirect('subscription_dashboard')

# ===== ADMIN VIEWS =====

def require_admin(view_func):
    """Decorator to require admin/staff privileges"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not (request.user.is_superuser or request.user.is_staff):
            messages.error(request, 'Access denied. Admin privileges required.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper

def require_content_manager(view_func):
    """Decorator to require content manager or admin privileges"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        # Allow admins and content managers
        is_admin = request.user.is_superuser or request.user.is_staff
        is_content_manager = hasattr(request.user, 'userprofile') and request.user.userprofile.role == 'content_manager'
        if not (is_admin or is_content_manager):
            messages.error(request, 'Access denied. Content manager privileges required.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper

@require_admin
def admin_dashboard(request):
    """Admin dashboard with analytics"""
    
    from .models import UserSubscription, PayFastPayment, SubscriptionPlan
    from django.db.models import Count, Sum, Q
    
    # Get analytics data
    total_users = User.objects.count()
    verified_users = User.objects.filter(is_active=True).count()
    total_teachers = UserProfile.objects.filter(role='teacher').count()
    
    # Subscription breakdown
    free_users = UserProfile.objects.filter(subscription='free').count()
    starter_users = UserProfile.objects.filter(subscription='starter').count()
    growth_users = UserProfile.objects.filter(subscription='growth').count()
    premium_users = UserProfile.objects.filter(subscription='premium').count()
    
    # Revenue calculations
    active_subscriptions = UserSubscription.objects.filter(status='active').select_related('plan')
    total_mrr = sum(sub.plan.price for sub in active_subscriptions)
    
    completed_payments = PayFastPayment.objects.filter(status='complete')
    total_revenue = completed_payments.aggregate(Sum('amount_gross'))['amount_gross__sum'] or 0
    
    # Recent signups (last 7 days)
    from datetime import timedelta
    week_ago = timezone.now() - timedelta(days=7)
    recent_signups = User.objects.filter(date_joined__gte=week_ago).count()
    
    # Recent users
    latest_users = User.objects.select_related('userprofile').order_by('-date_joined')[:10]
    
    # Recent payments
    recent_payments = PayFastPayment.objects.filter(
        status='complete'
    ).select_related('user', 'plan').order_by('-completed_at')[:10]
    
    context = {
        'total_users': total_users,
        'verified_users': verified_users,
        'total_teachers': total_teachers,
        'free_users': free_users,
        'starter_users': starter_users,
        'growth_users': growth_users,
        'premium_users': premium_users,
        'total_mrr': total_mrr,
        'total_revenue': total_revenue,
        'recent_signups': recent_signups,
        'latest_users': latest_users,
        'recent_payments': recent_payments,
    }
    
    return render(request, 'core/admin/dashboard.html', context)

@require_admin
def admin_users(request):
    """User management interface"""
    
    # Get search and filter parameters
    search_query = request.GET.get('search', '')
    subscription_filter = request.GET.get('subscription', '')
    status_filter = request.GET.get('status', '')
    
    # Base queryset
    users = User.objects.select_related('userprofile').order_by('-date_joined')
    
    # Apply filters
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    if subscription_filter:
        users = users.filter(userprofile__subscription=subscription_filter)
    
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    
    context = {
        'users': users,
        'search_query': search_query,
        'subscription_filter': subscription_filter,
        'status_filter': status_filter,
    }
    
    return render(request, 'core/admin/users.html', context)

@require_admin
def admin_change_subscription(request, user_id):
    """Change user's subscription tier"""
    
    if request.method == 'POST':
        from .models import UserSubscription, SubscriptionPlan
        
        user = get_object_or_404(User, id=user_id)
        new_subscription = request.POST.get('subscription')
        
        if new_subscription in ['free', 'starter', 'growth', 'premium']:
            profile = UserProfile.objects.get(user=user)
            profile.subscription = new_subscription
            profile.save()
            
            # Update or create UserSubscription
            plan = SubscriptionPlan.objects.get(plan_type=new_subscription)
            subscription, created = UserSubscription.objects.get_or_create(
                user=user,
                defaults={
                    'plan': plan,
                    'status': 'active',
                    'current_period_start': timezone.now(),
                    'current_period_end': timezone.now() + timedelta(days=30)
                }
            )
            
            if not created:
                subscription.plan = plan
                subscription.status = 'active'
                subscription.current_period_start = timezone.now()
                subscription.current_period_end = timezone.now() + timedelta(days=30)
                subscription.save()
            
            messages.success(request, f'Updated {user.username} to {new_subscription.title()} plan.')
        else:
            messages.error(request, 'Invalid subscription tier.')
    
    return redirect('admin_users')

@require_admin
def admin_toggle_user_status(request, user_id):
    """Activate or deactivate user account"""
    
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        
        if user.id == request.user.id:
            messages.error(request, 'You cannot deactivate your own account.')
        else:
            user.is_active = not user.is_active
            user.save()
            status = 'activated' if user.is_active else 'deactivated'
            messages.success(request, f'User {user.username} has been {status}.')
    
    return redirect('admin_users')

@require_admin
def admin_subscriptions(request):
    """Subscription management view"""
    
    from .models import UserSubscription, SubscriptionPlan, PayFastPayment
    from django.db.models import Sum
    
    # Get all active subscriptions
    active_subscriptions = UserSubscription.objects.filter(
        status='active'
    ).select_related('user', 'plan').order_by('-current_period_end')
    
    # Get all subscription plans
    plans = SubscriptionPlan.objects.all().order_by('price')
    
    # Calculate revenue per plan
    plan_revenue = {}
    for plan in plans:
        plan_subs = active_subscriptions.filter(plan=plan)
        plan_revenue[plan.id] = {
            'plan': plan,
            'count': plan_subs.count(),
            'mrr': plan_subs.count() * plan.price
        }
    
    # Payment history
    payments = PayFastPayment.objects.filter(
        status='complete'
    ).select_related('user', 'plan').order_by('-completed_at')[:50]
    
    context = {
        'active_subscriptions': active_subscriptions,
        'plan_revenue': plan_revenue.values(),
        'payments': payments,
    }
    
    return render(request, 'core/admin/subscriptions.html', context)

@require_admin
def admin_api_test(request):
    """API Testing Dashboard"""
    
    # Define all available endpoints
    endpoints = [
        {
            'name': 'Exam Boards',
            'url': '/api/exam-boards/',
            'method': 'GET',
            'description': 'List all exam boards (IEB, CAPS, Cambridge, etc.) - PUBLIC ACCESS',
            'filters': ['search (name_full, abbreviation, region)'],
            'example_params': '?search=IEB'
        },
        {
            'name': 'Subjects',
            'url': '/api/subjects/',
            'method': 'GET',
            'description': 'List all subjects - PUBLIC ACCESS',
            'filters': ['search (name)'],
            'example_params': '?search=Mathematics'
        },
        {
            'name': 'Grades',
            'url': '/api/grades/',
            'method': 'GET',
            'description': 'List all grades - PUBLIC ACCESS',
            'filters': ['ordering (number)'],
            'example_params': '?ordering=number'
        },
        {
            'name': 'Past Papers',
            'url': '/api/past-papers/',
            'method': 'GET',
            'description': 'List all government exam papers with PDFs - PUBLIC ACCESS',
            'filters': [
                'exam_board (text)',
                'subject (ID)',
                'grade (ID)',
                'year (number)',
                'search (title, chapter, section)'
            ],
            'example_params': '?exam_board=1&year=2023&subject=1'
        },
        {
            'name': 'Formatted Papers',
            'url': '/api/formatted-papers/',
            'method': 'GET',
            'description': 'List AI-formatted papers with questions and memos in JSON - REQUIRES AUTHENTICATION',
            'filters': [
                'exam_board (text)',
                'subject (ID)',
                'grade (ID)',
                'year (number)',
                'processing_status (pending, processing, completed, failed)',
                'is_published (true, false)',
                'search (title)'
            ],
            'example_params': '?is_published=true&year=2023'
        },
        {
            'name': 'Quizzes',
            'url': '/api/quizzes/',
            'method': 'GET',
            'description': 'List quizzes with Google Forms links - PUBLIC for free quizzes, AUTH for premium',
            'filters': [
                'exam_board (text)',
                'subject (ID)',
                'grade (ID)',
                'is_premium (true, false)',
                'search (title, topic)'
            ],
            'example_params': '?is_premium=false&subject=1'
        },
        {
            'name': 'Assignments',
            'url': '/api/assignments/',
            'method': 'GET',
            'description': 'List all assignments - REQUIRES AUTHENTICATION',
            'filters': [
                'subject (ID)',
                'grade (ID)',
                'assignment_type (text)',
                'search (topic, content)'
            ],
            'example_params': '?subject=1&grade=2'
        },
        {
            'name': 'Get Auth Token',
            'url': '/api/auth/token/',
            'method': 'POST',
            'description': 'Get authentication token for API access (send username and password)',
            'filters': [],
            'example_params': 'POST body: {"username": "your_username", "password": "your_password"}'
        },
    ]
    
    # Get subjects and grades for filter dropdowns
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    
    context = {
        'endpoints': endpoints,
        'subjects': subjects,
        'grades': grades,
    }
    
    return render(request, 'core/admin/api_test.html', context)

@require_admin
def admin_features(request):
    """Feature Management dashboard"""
    
    from .models import SubscriptionPlan
    
    # Get counts for each feature type
    exam_boards_count = ExamBoard.objects.count()
    subjects_count = Subject.objects.count()
    grades_count = Grade.objects.count()
    plans_count = SubscriptionPlan.objects.count()
    
    context = {
        'exam_boards_count': exam_boards_count,
        'subjects_count': subjects_count,
        'grades_count': grades_count,
        'plans_count': plans_count,
    }
    
    return render(request, 'core/admin/features.html', context)

@require_admin
def admin_exam_boards(request):
    """Exam Boards CRUD interface"""
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create':
            ExamBoard.objects.create(
                name_full=request.POST.get('name_full'),
                abbreviation=request.POST.get('abbreviation'),
                region=request.POST.get('region', '')
            )
            messages.success(request, 'Exam board created successfully.')
        
        elif action == 'update':
            board_id = request.POST.get('board_id')
            board = get_object_or_404(ExamBoard, id=board_id)
            board.name_full = request.POST.get('name_full')
            board.abbreviation = request.POST.get('abbreviation')
            board.region = request.POST.get('region', '')
            board.save()
            messages.success(request, 'Exam board updated successfully.')
        
        elif action == 'delete':
            board_id = request.POST.get('board_id')
            board = get_object_or_404(ExamBoard, id=board_id)
            board.delete()
            messages.success(request, 'Exam board deleted successfully.')
        
        return redirect('admin_exam_boards')
    
    exam_boards = ExamBoard.objects.all().order_by('abbreviation')
    
    context = {
        'exam_boards': exam_boards,
    }
    
    return render(request, 'core/admin/exam_boards.html', context)

@require_admin
def admin_subjects(request):
    """Subjects CRUD interface"""
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create':
            Subject.objects.create(name=request.POST.get('name'))
            messages.success(request, 'Subject created successfully.')
        
        elif action == 'update':
            subject_id = request.POST.get('subject_id')
            subject = get_object_or_404(Subject, id=subject_id)
            subject.name = request.POST.get('name')
            subject.save()
            messages.success(request, 'Subject updated successfully.')
        
        elif action == 'delete':
            subject_id = request.POST.get('subject_id')
            subject = get_object_or_404(Subject, id=subject_id)
            subject.delete()
            messages.success(request, 'Subject deleted successfully.')
        
        return redirect('admin_subjects')
    
    subjects = Subject.objects.all().order_by('name')
    
    context = {
        'subjects': subjects,
    }
    
    return render(request, 'core/admin/subjects.html', context)

@require_admin
def admin_grades(request):
    """Grades CRUD interface"""
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create':
            Grade.objects.create(number=request.POST.get('number'))
            messages.success(request, 'Grade created successfully.')
        
        elif action == 'update':
            grade_id = request.POST.get('grade_id')
            grade = get_object_or_404(Grade, id=grade_id)
            grade.number = request.POST.get('number')
            grade.save()
            messages.success(request, 'Grade updated successfully.')
        
        elif action == 'delete':
            grade_id = request.POST.get('grade_id')
            grade = get_object_or_404(Grade, id=grade_id)
            grade.delete()
            messages.success(request, 'Grade deleted successfully.')
        
        return redirect('admin_grades')
    
    grades = Grade.objects.all().order_by('number')
    
    context = {
        'grades': grades,
    }
    
    return render(request, 'core/admin/grades.html', context)

@require_admin
def admin_subscription_plans(request):
    """Subscription Plans management interface"""
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update':
            plan_id = request.POST.get('plan_id')
            plan = get_object_or_404(SubscriptionPlan, id=plan_id)
            plan.price = request.POST.get('price')
            plan.max_subjects = request.POST.get('max_subjects')
            plan.lesson_plan_quota = request.POST.get('lesson_plan_quota')
            plan.ai_model = request.POST.get('ai_model', '')
            plan.save()
            messages.success(request, f'{plan.name} plan updated successfully.')
        
        return redirect('admin_subscription_plans')
    
    plans = SubscriptionPlan.objects.all().order_by('price')
    
    context = {
        'plans': plans,
    }
    
    return render(request, 'core/admin/subscription_plans.html', context)

@require_admin
def admin_communications(request):
    """Communications dashboard"""
    
    from .models import Announcement, EmailBlast
    
    # Get counts
    active_announcements_count = Announcement.objects.filter(is_active=True).count()
    total_announcements_count = Announcement.objects.count()
    sent_emails_count = EmailBlast.objects.filter(status='sent').count()
    draft_emails_count = EmailBlast.objects.filter(status='draft').count()
    
    context = {
        'active_announcements_count': active_announcements_count,
        'total_announcements_count': total_announcements_count,
        'sent_emails_count': sent_emails_count,
        'draft_emails_count': draft_emails_count,
    }
    
    return render(request, 'core/admin/communications.html', context)

@require_admin
def admin_announcements(request):
    """Announcements CRUD interface"""
    
    from .models import Announcement
    from django.utils import timezone
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create':
            announcement = Announcement.objects.create(
                title=request.POST.get('title'),
                message=request.POST.get('message'),
                target_audience=request.POST.get('target_audience'),
                priority=request.POST.get('priority'),
                display_type=request.POST.get('display_type'),
                created_by=request.user,
                is_active=True
            )
            
            # Set start time if provided
            starts_at = request.POST.get('starts_at')
            if starts_at:
                announcement.starts_at = starts_at
            
            # Set expiry if provided
            expires_at = request.POST.get('expires_at')
            if expires_at:
                announcement.expires_at = expires_at
            
            announcement.save()
            
            messages.success(request, 'Announcement created successfully.')
        
        elif action == 'update':
            announcement_id = request.POST.get('announcement_id')
            announcement = get_object_or_404(Announcement, id=announcement_id)
            announcement.title = request.POST.get('title')
            announcement.message = request.POST.get('message')
            announcement.target_audience = request.POST.get('target_audience')
            announcement.priority = request.POST.get('priority')
            announcement.display_type = request.POST.get('display_type')
            
            # Only update schedule if provided (preserve existing if empty)
            starts_at = request.POST.get('starts_at')
            if starts_at:
                announcement.starts_at = starts_at
            
            expires_at = request.POST.get('expires_at')
            if expires_at:
                announcement.expires_at = expires_at
            
            announcement.save()
            messages.success(request, 'Announcement updated successfully.')
        
        elif action == 'toggle':
            announcement_id = request.POST.get('announcement_id')
            announcement = get_object_or_404(Announcement, id=announcement_id)
            announcement.is_active = not announcement.is_active
            announcement.save()
            status = 'activated' if announcement.is_active else 'deactivated'
            messages.success(request, f'Announcement {status}.')
        
        elif action == 'delete':
            announcement_id = request.POST.get('announcement_id')
            announcement = get_object_or_404(Announcement, id=announcement_id)
            announcement.delete()
            messages.success(request, 'Announcement deleted successfully.')
        
        return redirect('admin_announcements')
    
    announcements = Announcement.objects.all().order_by('-created_at')
    
    context = {
        'announcements': announcements,
    }
    
    return render(request, 'core/admin/announcements.html', context)

@login_required
def dismiss_announcement(request, announcement_id):
    """Dismiss an announcement for the current user"""
    from .models import Announcement
    
    if request.method == 'POST':
        announcement = get_object_or_404(Announcement, id=announcement_id)
        announcement.dismissed_by.add(request.user)
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'}, status=400)

@require_admin
def admin_email_blasts(request):
    """Email blast management interface"""
    
    from .models import EmailBlast
    
    email_blasts = EmailBlast.objects.all().order_by('-created_at')
    
    context = {
        'email_blasts': email_blasts,
    }
    
    return render(request, 'core/admin/email_blasts.html', context)

@require_admin
def send_email_blast(request):
    """Send or schedule an email blast"""
    
    from .models import EmailBlast
    from django.core.mail import send_mail
    from django.conf import settings
    from django.utils import timezone
    
    if request.method == 'POST':
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        target_audience = request.POST.get('target_audience')
        
        # Create email blast record
        email_blast = EmailBlast.objects.create(
            subject=subject,
            message=message,
            target_audience=target_audience,
            created_by=request.user,
            status='sending'
        )
        
        # Get recipient list
        recipients = []
        if target_audience == 'all':
            recipients = User.objects.filter(is_active=True).values_list('email', flat=True)
        elif target_audience == 'teachers':
            recipients = User.objects.filter(is_active=True, is_staff=False).values_list('email', flat=True)
        elif target_audience == 'content_managers':
            recipients = User.objects.filter(is_active=True, groups__name='content_manager').values_list('email', flat=True)
        
        email_blast.recipient_count = len(recipients)
        email_blast.save()
        
        # Send emails
        sent_count = 0
        failed_count = 0
        
        for recipient_email in recipients:
            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[recipient_email],
                    fail_silently=False,
                )
                sent_count += 1
            except Exception as e:
                failed_count += 1
        
        # Update email blast status
        email_blast.sent_count = sent_count
        email_blast.failed_count = failed_count
        email_blast.status = 'sent' if failed_count == 0 else 'failed'
        email_blast.sent_at = timezone.now()
        email_blast.save()
        
        if failed_count == 0:
            messages.success(request, f'Email sent to {sent_count} recipients successfully.')
        else:
            messages.warning(request, f'Email sent to {sent_count} recipients. {failed_count} failed.')
        
        return redirect('admin_email_blasts')
    
    return render(request, 'core/admin/send_email.html')

# ===== CONTENT MANAGER VIEWS =====

@require_content_manager
def content_dashboard(request):
    """Content manager dashboard with analytics"""
    
    from .models import PastPaper, Quiz
    from django.db.models import Count
    
    # Analytics
    total_papers = PastPaper.objects.count()
    total_quizzes = Quiz.objects.count()
    premium_quizzes = Quiz.objects.filter(is_premium=True).count()
    free_quizzes = Quiz.objects.filter(is_premium=False).count()
    
    # Recent uploads
    recent_papers = PastPaper.objects.all().order_by('-uploaded_at')[:10]
    recent_quizzes = Quiz.objects.all().order_by('-created_at')[:10]
    
    context = {
        'total_papers': total_papers,
        'total_quizzes': total_quizzes,
        'premium_quizzes': premium_quizzes,
        'free_quizzes': free_quizzes,
        'recent_papers': recent_papers,
        'recent_quizzes': recent_quizzes,
    }
    
    return render(request, 'core/content/dashboard.html', context)

@require_content_manager
def content_papers(request):
    """Past paper management view"""
    
    from .models import PastPaper, ExamBoard, Subject, Grade
    
    # Get search and filter parameters
    search_query = request.GET.get('search', '')
    board_filter = request.GET.get('board', '')
    subject_filter = request.GET.get('subject', '')
    grade_filter = request.GET.get('grade', '')
    
    # Filter papers
    papers = PastPaper.objects.all()
    
    if search_query:
        papers = papers.filter(title__icontains=search_query)
    if board_filter:
        papers = papers.filter(exam_board=board_filter)
    if subject_filter:
        papers = papers.filter(subject_id=subject_filter)
    if grade_filter:
        papers = papers.filter(grade_id=grade_filter)
    
    papers = papers.order_by('-uploaded_at')
    
    # Get filters for dropdowns
    boards = ExamBoard.objects.all()
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    
    context = {
        'papers': papers,
        'boards': boards,
        'subjects': subjects,
        'grades': grades,
        'search_query': search_query,
        'board_filter': board_filter,
        'subject_filter': subject_filter,
        'grade_filter': grade_filter,
    }
    
    return render(request, 'core/content/papers.html', context)

@require_content_manager
def content_upload_paper(request):
    """Upload new past paper"""
    
    from .models import PastPaper, ExamBoard, Subject, Grade
    
    if request.method == 'POST':
        title = request.POST.get('title')
        exam_board = request.POST.get('exam_board')
        grade_id = request.POST.get('grade')
        subject_id = request.POST.get('subject')
        paper_type = request.POST.get('paper_type', 'paper1')
        paper_code = request.POST.get('paper_code', '')
        year = request.POST.get('year')
        chapter = request.POST.get('chapter', '')
        section = request.POST.get('section', '')
        notes = request.POST.get('notes', '')
        file = request.FILES.get('file')
        
        # Validation
        if not all([title, exam_board, grade_id, subject_id, year, file]):
            messages.error(request, 'Please fill in all required fields and upload a file.')
            return redirect('content_upload_paper')
        
        # Create past paper
        paper = PastPaper.objects.create(
            title=title,
            exam_board=exam_board,
            grade_id=grade_id,
            subject_id=subject_id,
            paper_type=paper_type,
            paper_code=paper_code if paper_code else f"{title}_{year}",
            year=int(year),
            chapter=chapter,
            section=section,
            notes=notes,
            file=file,
            uploaded_by=request.user
        )
        
        messages.success(request, f'Past paper "{title}" uploaded successfully!')
        return redirect('content_papers')
    
    # GET request - show form
    boards = ExamBoard.objects.all()
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    
    context = {
        'boards': boards,
        'subjects': subjects,
        'grades': grades,
    }
    
    return render(request, 'core/content/upload_paper.html', context)

@require_content_manager
def content_quizzes(request):
    """Quiz management view"""
    
    from .models import Quiz, Subject, Grade
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')  # free or premium
    subject_filter = request.GET.get('subject', '')
    grade_filter = request.GET.get('grade', '')
    
    # Filter quizzes
    quizzes = Quiz.objects.all()
    
    if status_filter == 'free':
        quizzes = quizzes.filter(is_premium=False)
    elif status_filter == 'premium':
        quizzes = quizzes.filter(is_premium=True)
    if subject_filter:
        quizzes = quizzes.filter(subject_id=subject_filter)
    if grade_filter:
        quizzes = quizzes.filter(grade_id=grade_filter)
    
    quizzes = quizzes.order_by('-created_at')
    
    # Get filters for dropdowns
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    
    context = {
        'quizzes': quizzes,
        'subjects': subjects,
        'grades': grades,
        'status_filter': status_filter,
        'subject_filter': subject_filter,
        'grade_filter': grade_filter,
    }
    
    return render(request, 'core/content/quizzes.html', context)

@require_content_manager
def content_create_quiz(request):
    """Create new quiz"""
    
    from .models import Quiz, Subject, Grade, PastPaper
    
    if request.method == 'POST':
        title = request.POST.get('title')
        subject_id = request.POST.get('subject')
        grade_id = request.POST.get('grade')
        is_premium = request.POST.get('is_premium') == 'on'
        questions_json = request.POST.get('questions_json', '[]')
        
        # Validation
        if not all([title, subject_id, grade_id]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('content_create_quiz')
        
        # Create quiz
        quiz = Quiz.objects.create(
            title=title,
            subject_id=subject_id,
            grade_id=grade_id,
            is_premium=is_premium,
            questions=questions_json,
            created_by=request.user
        )
        
        messages.success(request, f'Quiz "{title}" created successfully!')
        return redirect('content_quizzes')
    
    # GET request - show form
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    papers = PastPaper.objects.all().order_by('-uploaded_at')[:20]  # Recent papers for AI generation
    
    context = {
        'subjects': subjects,
        'grades': grades,
        'papers': papers,
    }
    
    return render(request, 'core/content/create_quiz.html', context)

@require_content_manager  
def content_formatted_papers(request):
    """View and manage AI-formatted papers"""
    from .models import FormattedPaper, Subject, Grade, ExamBoard
    
    # Get filter parameters
    subject_filter = request.GET.get('subject', '')
    grade_filter = request.GET.get('grade', '')
    status_filter = request.GET.get('status', '')  # pending, completed, failed
    
    # Filter formatted papers
    papers = FormattedPaper.objects.select_related('source_paper', 'subject', 'grade', 'created_by')
    
    if subject_filter:
        papers = papers.filter(subject_id=subject_filter)
    if grade_filter:
        papers = papers.filter(grade_id=grade_filter)
    if status_filter:
        papers = papers.filter(processing_status=status_filter)
    
    papers = papers.order_by('-created_at')
    
    # Get filters for dropdowns
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    
    context = {
        'formatted_papers': papers,
        'subjects': subjects,
        'grades': grades,
        'subject_filter': subject_filter,
        'grade_filter': grade_filter,
        'status_filter': status_filter,
    }
    
    return render(request, 'core/content/formatted_papers.html', context)

@require_content_manager
def content_reformat_paper(request, paper_id):
    """AI reformat a past paper - select paper and initiate AI processing"""
    from .models import PastPaper, FormattedPaper
    from .openai_service import extract_questions_from_paper
    from django.conf import settings
    import os
    
    paper = get_object_or_404(PastPaper, id=paper_id)
    
    if request.method == 'POST':
        try:
            # Create FormattedPaper record with pending status
            formatted_paper = FormattedPaper.objects.create(
                source_paper=paper,
                title=f"Formatted: {paper.title}",
                subject=paper.subject,
                grade=paper.grade,
                exam_board=paper.exam_board,
                year=paper.year,
                questions_json={},
                memo_json={},
                processing_status='processing',
                created_by=request.user
            )
            
            # Get the file path
            file_path = paper.file.path
            
            # Call AI service to extract questions
            result = extract_questions_from_paper(
                file_path=file_path,
                subject=paper.subject.name,
                grade=paper.grade.number,
                exam_board=paper.exam_board,
                paper_type=paper.paper_type,
                model='gpt-4'  # Use best model for accuracy
            )
            
            # Update formatted paper with results
            formatted_paper.questions_json = result['questions_json']
            formatted_paper.memo_json = result['memo_json']
            formatted_paper.total_questions = result['total_questions']
            formatted_paper.total_marks = result['total_marks']
            formatted_paper.question_type = result['question_type']
            formatted_paper.ai_model_used = result['ai_model_used']
            formatted_paper.processing_status = 'completed'
            formatted_paper.save()
            
            messages.success(request, f'Successfully extracted {result["total_questions"]} questions from the paper!')
            return redirect('content_review_formatted_paper', paper_id=formatted_paper.id)
            
        except Exception as e:
            # Update status to failed
            if 'formatted_paper' in locals():
                formatted_paper.processing_status = 'failed'
                formatted_paper.error_message = str(e)
                formatted_paper.save()
            
            messages.error(request, f'Failed to process paper: {str(e)}')
            return redirect('content_papers')
    
    # GET request - show confirmation
    context = {
        'paper': paper,
    }
    return render(request, 'core/content/reformat_paper.html', context)

@require_content_manager
def content_review_formatted_paper(request, paper_id):
    """Review and edit AI-extracted questions and memo"""
    from .models import FormattedPaper
    import json
    
    formatted_paper = get_object_or_404(FormattedPaper, id=paper_id)
    
    if request.method == 'POST':
        # Handle save of edited questions and memo
        action = request.POST.get('action')
        
        if action == 'save':
            try:
                # Get updated JSON from form
                questions_json = json.loads(request.POST.get('questions_json', '{}'))
                memo_json = json.loads(request.POST.get('memo_json', '{}'))
                
                # Update formatted paper
                formatted_paper.questions_json = questions_json
                formatted_paper.memo_json = memo_json
                formatted_paper.total_questions = len(questions_json.get('questions', []))
                formatted_paper.reviewed = True
                formatted_paper.save()
                
                messages.success(request, 'Changes saved successfully!')
                return redirect('content_review_formatted_paper', paper_id=paper_id)
                
            except json.JSONDecodeError:
                messages.error(request, 'Invalid JSON format. Please check your edits.')
        
        elif action == 'publish':
            formatted_paper.is_published = True
            formatted_paper.reviewed = True
            formatted_paper.save()
            messages.success(request, 'Formatted paper published successfully!')
            return redirect('content_formatted_papers')
    
    # Format JSON for display in textarea
    questions_json_str = json.dumps(formatted_paper.questions_json, indent=2)
    memo_json_str = json.dumps(formatted_paper.memo_json, indent=2)
    
    context = {
        'formatted_paper': formatted_paper,
        'questions_json_str': questions_json_str,
        'memo_json_str': memo_json_str,
        'source_paper': formatted_paper.source_paper,
    }
    
    return render(request, 'core/content/review_formatted_paper.html', context)

@require_content_manager
def content_bulk_upload(request):
    """Bulk upload of past papers, quizzes, or assignments"""
    from .models import PastPaper, Quiz, GeneratedAssignment
    
    if request.method == 'POST':
        upload_type = request.POST.get('upload_type')
        files = request.FILES.getlist('files')
        
        if not files:
            return JsonResponse({'success': False, 'error': 'No files provided'})
        
        # Validate file sizes and types
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt'}
        
        for file in files:
            if file.size > MAX_FILE_SIZE:
                return JsonResponse({
                    'success': False,
                    'error': f'File {file.name} exceeds 10MB limit'
                })
            
            file_ext = os.path.splitext(file.name)[1].lower()
            if file_ext not in ALLOWED_EXTENSIONS:
                return JsonResponse({
                    'success': False,
                    'error': f'File {file.name} has unsupported format. Only PDF, DOCX, and TXT allowed.'
                })
        
        results = {
            'success': True,
            'uploaded_count': 0,
            'failed_count': 0,
            'details': []
        }
        
        try:
            if upload_type == 'pastpaper':
                # Get shared metadata for past papers
                exam_board_id = request.POST.get('exam_board_id')
                year = request.POST.get('year')
                subject_id = request.POST.get('subject_id')
                grade_id = request.POST.get('grade_id')
                chapter = request.POST.get('chapter', '')
                section = request.POST.get('section', '')
                
                exam_board = get_object_or_404(ExamBoard, id=exam_board_id)
                subject = get_object_or_404(Subject, id=subject_id)
                grade = get_object_or_404(Grade, id=grade_id)
                
                for file in files:
                    try:
                        # Auto-generate title from filename
                        title = os.path.splitext(file.name)[0]
                        
                        # Create past paper (exam_board is CharField, use abbreviation)
                        paper = PastPaper.objects.create(
                            title=title,
                            exam_board=exam_board.abbreviation,
                            year=year,
                            subject=subject,
                            grade=grade,
                            chapter=chapter,
                            section=section,
                            file=file,
                            uploaded_by=request.user
                        )
                        
                        results['uploaded_count'] += 1
                        results['details'].append({
                            'filename': file.name,
                            'success': True
                        })
                        
                    except Exception as e:
                        results['failed_count'] += 1
                        results['details'].append({
                            'filename': file.name,
                            'success': False,
                            'error': str(e)
                        })
            
            elif upload_type == 'quiz':
                # Get shared metadata for quizzes
                exam_board_id = request.POST.get('exam_board_id')
                grade_id = request.POST.get('grade_id')
                subject_id = request.POST.get('subject_id')
                topic = request.POST.get('topic')
                is_premium = request.POST.get('is_premium') == 'true'
                
                exam_board = get_object_or_404(ExamBoard, id=exam_board_id)
                grade = get_object_or_404(Grade, id=grade_id)
                subject = get_object_or_404(Subject, id=subject_id)
                
                for file in files:
                    try:
                        # Auto-generate title from filename
                        title = os.path.splitext(file.name)[0]
                        
                        # Expect files to be text files with Google Forms links
                        # Or create quizzes without links if PDFs
                        google_form_link = ''
                        if file.name.endswith('.txt'):
                            google_form_link = file.read().decode('utf-8').strip()
                        
                        # Create quiz (exam_board is CharField, use abbreviation)
                        quiz = Quiz.objects.create(
                            title=title,
                            exam_board=exam_board.abbreviation,
                            grade=grade,
                            subject=subject,
                            topic=topic,
                            is_premium=is_premium,
                            google_form_link=google_form_link,
                            created_by=request.user
                        )
                        
                        results['uploaded_count'] += 1
                        results['details'].append({
                            'filename': file.name,
                            'success': True
                        })
                        
                    except Exception as e:
                        results['failed_count'] += 1
                        results['details'].append({
                            'filename': file.name,
                            'success': False,
                            'error': str(e)
                        })
            
            elif upload_type == 'assignment':
                # Get shared metadata for assignments
                subject_id = request.POST.get('subject_id')
                grade_id = request.POST.get('grade_id')
                topic = request.POST.get('topic')
                
                subject = get_object_or_404(Subject, id=subject_id)
                grade = get_object_or_404(Grade, id=grade_id)
                
                for file in files:
                    try:
                        # Auto-generate title from filename
                        title = os.path.splitext(file.name)[0]
                        
                        # Create assignment
                        assignment = GeneratedAssignment.objects.create(
                            user=request.user,
                            subject=subject,
                            grade=grade,
                            topic=topic,
                            assignment_type='worksheet',
                            content=f'Uploaded: {title}',
                            file=file
                        )
                        
                        results['uploaded_count'] += 1
                        results['details'].append({
                            'filename': file.name,
                            'success': True
                        })
                        
                    except Exception as e:
                        results['failed_count'] += 1
                        results['details'].append({
                            'filename': file.name,
                            'success': False,
                            'error': str(e)
                        })
            
            else:
                return JsonResponse({'success': False, 'error': 'Invalid upload type'})
        
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
        
        return JsonResponse(results)
    
    # GET request - show form
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    exam_boards = ExamBoard.objects.all()
    
    context = {
        'subjects': subjects,
        'grades': grades,
        'exam_boards': exam_boards,
    }
    
    return render(request, 'core/content/bulk_upload.html', context)


@require_content_manager
def official_papers_bulk_upload(request):
    """Bulk upload official exam papers via folder structure with 2-step flow"""
    from .models import OfficialExamPaper
    from django.db import IntegrityError
    import re
    from datetime import datetime
    from pathlib import PurePosixPath
    
    # Security: Sanitize file paths to prevent directory traversal
    # Max depth is 4 to support optional session subfolder: Subject Name (CODE)/YEAR/[Session]/filename.pdf
    def sanitize_file_path(path, max_depth=4):
        """
        Sanitize and validate file paths to prevent security issues.
        Returns the sanitized path or raises ValueError.
        """
        try:
            safe_path = PurePosixPath(path)
            
            # Check for directory traversal attempts
            if '..' in safe_path.parts:
                raise ValueError("Path contains invalid '..' component")
            
            # Check for absolute paths
            if safe_path.is_absolute():
                raise ValueError("Absolute paths not allowed")
            
            # Check path depth
            if len(safe_path.parts) > max_depth:
                raise ValueError(f"Path depth exceeds maximum of {max_depth} levels")
            
            # Check for dangerous characters
            path_str = str(safe_path)
            dangerous_chars = ['\\', '\x00', '\n', '\r']
            if any(char in path_str for char in dangerous_chars):
                raise ValueError("Path contains invalid characters")
            
            return path_str
        except Exception as e:
            raise ValueError(f"Invalid path: {str(e)}")
    
    # Improved parser that handles multiple board formats
    def parse_filename(filename, file_path=''):
        """
        Parse different exam paper filename formats from various boards.
        Supports Cambridge, Edexcel, CAPS, ZIMSEC, IEB, and generic formats.
        Returns dict with parsed metadata and any warnings.
        """
        filename_lower = filename.lower()
        warnings = []
        
        parsed = {
            'session': 'other',
            'paper_number': '',
            'variant': '',
            'paper_type': 'qp',
            'year': None,
            'subject_name': '',
        }
        
        # === YEAR EXTRACTION ===
        # Try to extract year from filename or path
        year_match = re.search(r'(20[0-2]\d)', filename)
        if year_match:
            parsed['year'] = int(year_match.group(1))
        elif file_path:
            year_match = re.search(r'(20[0-2]\d)', file_path)
            if year_match:
                parsed['year'] = int(year_match.group(1))
        
        # If no year found, try 2-digit year format
        if not parsed['year']:
            year_match = re.search(r'[_\s](\d{2})[_\s.]', filename_lower)
            if year_match:
                year_2digit = int(year_match.group(1))
                # Assume 20xx for years < 50, 19xx otherwise
                parsed['year'] = 2000 + year_2digit if year_2digit < 50 else 1900 + year_2digit
        
        # === SESSION DETECTION ===
        # Cambridge style: _s23, _w23, _m23, _y23
        if re.search(r'_s\d{2}', filename_lower):
            parsed['session'] = 'june'
        elif re.search(r'_w\d{2}', filename_lower):
            parsed['session'] = 'november'
        elif re.search(r'_m\d{2}', filename_lower):
            parsed['session'] = 'may'
        elif re.search(r'_y\d{2}', filename_lower):
            parsed['session'] = 'february'
        # Word-based detection
        elif 'june' in filename_lower:
            parsed['session'] = 'june'
        elif 'november' in filename_lower or 'nov' in filename_lower:
            parsed['session'] = 'november'
        elif 'may' in filename_lower:
            parsed['session'] = 'may'
        elif 'feb' in filename_lower or 'march' in filename_lower:
            parsed['session'] = 'february'
        elif 'oct' in filename_lower or 'october' in filename_lower:
            parsed['session'] = 'october'
        elif 'summer' in filename_lower:
            parsed['session'] = 'summer'
        elif 'winter' in filename_lower:
            parsed['session'] = 'winter'
        else:
            warnings.append("Could not determine session - defaulting to 'other'")
        
        # === PAPER TYPE DETECTION ===
        if '_ms' in filename_lower or 'marking' in filename_lower or 'memo' in filename_lower or 'mark scheme' in filename_lower:
            parsed['paper_type'] = 'ms'
        elif '_qp' in filename_lower or 'question' in filename_lower or '_que_' in filename_lower:
            parsed['paper_type'] = 'qp'
        elif 'examiner' in filename_lower or '_er' in filename_lower or 'exam report' in filename_lower:
            parsed['paper_type'] = 'er'
        elif 'grade' in filename_lower and 'threshold' in filename_lower:
            parsed['paper_type'] = 'gt'
        elif 'insert' in filename_lower or 'resource' in filename_lower:
            parsed['paper_type'] = 'ir'
        elif 'specimen' in filename_lower:
            parsed['paper_type'] = 'specimen'
        
        # === PAPER NUMBER & VARIANT EXTRACTION ===
        # Cambridge style: _21, _42 (paper 2 variant 1, paper 4 variant 2)
        cambridge_match = re.search(r'_([1-9])([1-9])', filename_lower)
        if cambridge_match:
            parsed['paper_number'] = cambridge_match.group(1)
            parsed['variant'] = cambridge_match.group(2)
        else:
            # Edexcel style: Paper 1, Paper 2, etc.
            paper_match = re.search(r'(?:paper|p)[\s_]?(\d+[hlfm]?)', filename_lower)
            if paper_match:
                parsed['paper_number'] = paper_match.group(1).upper()
            
            # CAPS/IEB style: "P1", "P2" 
            if not parsed['paper_number']:
                caps_match = re.search(r'\bp(\d+)\b', filename_lower)
                if caps_match:
                    parsed['paper_number'] = caps_match.group(1)
            
            # Variant detection (separate from paper number)
            variant_match = re.search(r'(?:variant|v)[\s_]?(\d+)', filename_lower)
            if variant_match:
                parsed['variant'] = variant_match.group(1)
        
        # === SUBJECT NAME EXTRACTION (for generic formats) ===
        # Look for common subject names in filename
        subjects = {
            'mathematics': 'Mathematics',
            'math': 'Mathematics',
            'physics': 'Physics',
            'chemistry': 'Chemistry',
            'biology': 'Biology',
            'english': 'English',
            'history': 'History',
            'geography': 'Geography',
            'science': 'Science',
        }
        
        for key, value in subjects.items():
            if key in filename_lower:
                parsed['subject_name'] = value
                break
        
        # Validate critical fields
        if not parsed['paper_number']:
            warnings.append("Could not extract paper number - defaulting to '1'")
            parsed['paper_number'] = '1'
        
        if not parsed['year']:
            warnings.append(f"Could not extract year from filename or path")
        
        return parsed, warnings
    
    if request.method == 'POST':
        action = request.POST.get('action', 'preview')  # 'preview' or 'confirm'
        board_name = request.POST.get('board')
        
        if not board_name:
            return JsonResponse({'success': False, 'error': 'No exam board provided'})
        
        # Get ExamBoard by name (name_full, abbreviation, or common aliases)
        # Common aliases map to database names
        board_aliases = {
            'cambridge': ['Cambridge International', 'CIE', 'CAIE', 'Cambridge'],
            'edexcel': ['Edexcel', 'EDX', 'Pearson Edexcel'],
            'caps': ['Department of Basic Education (CAPS)', 'CAPS', 'DBE'],
            'zimsec': ['Zimbabwe School Examinations Council', 'ZIMSEC'],
            'ieb': ['Independent Examinations Board', 'IEB'],
            'aqa': ['AQA'],
            'ocr': ['OCR'],
        }
        
        try:
            # First try exact match on name_full or abbreviation
            exam_board = ExamBoard.objects.filter(
                Q(name_full__iexact=board_name) | Q(abbreviation__iexact=board_name)
            ).first()
            
            # If not found, try common aliases
            if not exam_board:
                board_name_lower = board_name.lower()
                if board_name_lower in board_aliases:
                    for alias in board_aliases[board_name_lower]:
                        exam_board = ExamBoard.objects.filter(
                            Q(name_full__iexact=alias) | Q(abbreviation__iexact=alias)
                        ).first()
                        if exam_board:
                            break
            
            # Also try partial match on name_full (e.g., "Cambridge" matches "Cambridge International")
            if not exam_board:
                exam_board = ExamBoard.objects.filter(
                    name_full__icontains=board_name
                ).first()
            
            if not exam_board:
                # List available boards to help user
                available_boards = ExamBoard.objects.values_list('name_full', flat=True)
                return JsonResponse({
                    'success': False, 
                    'error': f'Exam board "{board_name}" not found. Available boards: {", ".join(available_boards)}'
                })
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error finding exam board: {str(e)}'})
        
        # === STEP 1: PREVIEW & PARSE ===
        if action == 'preview':
            files = request.FILES.getlist('files')
            file_paths = request.POST.getlist('file_paths')
            
            if not files:
                return JsonResponse({'success': False, 'error': 'No files provided'})
            
            results = {
                'success': True,
                'action': 'preview',
                'total_files': len(files),
                'parseable_count': 0,
                'ready_count': 0,  # New papers to upload
                'existing_count': 0,  # Papers already in database (will skip)
                'warning_count': 0,
                'error_count': 0,
                'failed_count': 0,
                'papers': []
            }
            
            for idx, file in enumerate(files):
                file_path = file_paths[idx] if idx < len(file_paths) else file.name
                paper_result = {
                    'filename': file.name,
                    'file_path': file_path,
                    'status': 'error',
                    'warnings': [],
                    'errors': []
                }
                
                try:
                    # Sanitize file path
                    try:
                        safe_path = sanitize_file_path(file_path)
                        paper_result['safe_path'] = safe_path
                    except ValueError as e:
                        paper_result['errors'].append(f"Path validation failed: {str(e)}")
                        results['failed_count'] += 1
                        results['error_count'] += 1
                        results['papers'].append(paper_result)
                        continue
                    
                    # Parse folder structure: Subject Name (CODE)/YEAR/filename.pdf
                    # Example: Chemistry (0620)/2011/0620_s11_qp_11.pdf
                    path_parts = safe_path.split('/')
                    subject_code = ''
                    subject_name = ''
                    year_from_path = None
                    
                    if len(path_parts) >= 3:
                        # Expected format: "Subject Name (CODE)/YEAR/filename.pdf"
                        subject_folder = path_parts[0]
                        year_folder = path_parts[1]
                        
                        # Extract subject name and code from "Subject Name (CODE)"
                        subject_match = re.match(r'^(.+?)\s*\(([^)]+)\)$', subject_folder)
                        if subject_match:
                            subject_name = subject_match.group(1).strip()
                            subject_code = subject_match.group(2).strip()
                        else:
                            # MANDATORY FORMAT: Reject if format doesn't match
                            paper_result['errors'].append(f"Subject folder must be in format 'Subject Name (CODE)', got: '{subject_folder}'")
                            results['failed_count'] += 1
                            results['error_count'] += 1
                            results['papers'].append(paper_result)
                            continue
                        
                        # Extract year from folder - flexible matching (allows "2023", "2023 June", etc.)
                        year_match = re.search(r'([12]\d{3})', year_folder)
                        if year_match:
                            year_from_path = int(year_match.group(1))
                            # Warn if folder name isn't exactly a year
                            if year_folder != year_match.group(1):
                                paper_result['warnings'].append(
                                    f"Year folder '{year_folder}' contains extra text; using year {year_from_path}"
                                )
                        else:
                            paper_result['errors'].append(
                                f"Year folder must contain a 4-digit year (e.g., '2011', '2023'), got: '{year_folder}'"
                            )
                            results['failed_count'] += 1
                            results['error_count'] += 1
                            results['papers'].append(paper_result)
                            continue
                    
                    elif len(path_parts) < 3:
                        # MANDATORY 3-LEVEL STRUCTURE: Reject if not properly organized
                        paper_result['errors'].append(
                            f"Invalid folder structure. Expected: 'Subject Name (CODE)/YEAR/filename.pdf' "
                            f"(3 levels), but got {len(path_parts)} level(s). "
                            f"Please organize files correctly."
                        )
                        results['failed_count'] += 1
                        results['error_count'] += 1
                        results['papers'].append(paper_result)
                        continue
                    
                    # Parse filename
                    parsed, parse_warnings = parse_filename(file.name, safe_path)
                    paper_result['warnings'].extend(parse_warnings)
                    
                    # Use year from path if available, otherwise use parsed year
                    year = year_from_path or parsed['year'] or datetime.now().year
                    
                    # Validate year
                    current_year = datetime.now().year
                    if year < 1990 or year > current_year + 1:
                        paper_result['warnings'].append(f"Unusual year detected: {year}")
                    
                    # Build paper data
                    # Prioritize subject_name from folder structure, fallback to filename parsing
                    final_subject_name = subject_name or parsed.get('subject_name', '')
                    
                    # Check if this paper already exists in the database
                    existing_paper = OfficialExamPaper.objects.filter(
                        exam_board=exam_board,
                        subject_code=subject_code,
                        year=year,
                        session=parsed['session'],
                        paper_number=parsed['paper_number'],
                        variant=parsed['variant'] or '',
                        paper_type=parsed['paper_type']
                    ).first()
                    
                    if existing_paper:
                        # Paper already exists - mark for skipping
                        paper_result.update({
                            'status': 'exists',
                            'board': exam_board.name_full,
                            'board_id': exam_board.id,
                            'subject_code': subject_code,
                            'subject_name': final_subject_name,
                            'original_filename': file.name,
                            'year': year,
                            'session': parsed['session'],
                            'paper_number': parsed['paper_number'],
                            'variant': parsed['variant'],
                            'paper_type': parsed['paper_type'],
                            'file_size': file.size,
                            'existing_id': existing_paper.id,
                        })
                        results['existing_count'] += 1
                        results['parseable_count'] += 1
                    else:
                        # New paper - ready to upload
                        paper_result.update({
                            'status': 'ready',
                            'board': exam_board.name_full,
                            'board_id': exam_board.id,
                            'subject_code': subject_code,
                            'subject_name': final_subject_name,
                            'original_filename': file.name,
                            'year': year,
                            'session': parsed['session'],
                            'paper_number': parsed['paper_number'],
                            'variant': parsed['variant'],
                            'paper_type': parsed['paper_type'],
                            'file_size': file.size,
                        })
                        results['parseable_count'] += 1
                        results['ready_count'] += 1
                    
                    if paper_result['warnings']:
                        results['warning_count'] += 1
                    
                except Exception as e:
                    paper_result['status'] = 'error'
                    paper_result['errors'].append(f"Parsing error: {str(e)}")
                    results['failed_count'] += 1
                    results['error_count'] += 1
                
                results['papers'].append(paper_result)
            
            return JsonResponse(results)
        
        # === STEP 2: CONFIRM & SAVE ===
        elif action == 'confirm':
            import json
            
            files = request.FILES.getlist('files')
            file_paths = request.POST.getlist('file_paths')
            papers_data_json = request.POST.get('papers_data')
            
            if not files or not papers_data_json:
                return JsonResponse({'success': False, 'error': 'Missing files or paper data'})
            
            try:
                papers_data = json.loads(papers_data_json)
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'Invalid paper data format'})
            
            results = {
                'success': True,
                'action': 'confirm',
                'uploaded_count': 0,
                'success_count': 0,  # Alias for frontend compatibility
                'skipped_count': 0,
                'existing_skipped': 0,  # Papers skipped because they already exist
                'failed_count': 0,
                'details': []
            }
            
            for idx, file in enumerate(files):
                try:
                    # Get corresponding paper data
                    if idx >= len(papers_data):
                        continue
                    
                    paper_data = papers_data[idx]
                    
                    # Skip if parsing failed (status is 'error')
                    if paper_data.get('status') == 'error':
                        results['skipped_count'] += 1
                        results['details'].append({
                            'filename': file.name,
                            'status': 'skipped',
                            'reason': 'Parsing error'
                        })
                        continue
                    
                    # Skip if paper already exists in database
                    if paper_data.get('status') == 'exists':
                        results['skipped_count'] += 1
                        results['existing_skipped'] += 1
                        results['details'].append({
                            'filename': file.name,
                            'status': 'skipped',
                            'reason': 'Already exists in database'
                        })
                        continue
                    
                    # SECURITY: Re-validate file path before saving (don't trust frontend data)
                    file_path = file_paths[idx] if idx < len(file_paths) else file.name
                    try:
                        safe_path = sanitize_file_path(file_path)
                    except ValueError as e:
                        results['failed_count'] += 1
                        results['details'].append({
                            'filename': file.name,
                            'status': 'error',
                            'error': f"Path validation failed: {str(e)}"
                        })
                        continue
                    
                    # Try to create official exam paper - database will reject duplicates
                    try:
                        paper = OfficialExamPaper.objects.create(
                            exam_board=exam_board,
                            subject_code=paper_data['subject_code'],
                            subject_name=paper_data.get('subject_name', ''),
                            year=paper_data['year'],
                            session=paper_data['session'],
                            paper_number=paper_data['paper_number'],
                            variant=paper_data.get('variant', ''),
                            paper_type=paper_data['paper_type'],
                            original_filename=file.name,
                            file=file,  # Django handles secure storage automatically
                            metadata_json={
                                'parsed_data': paper_data,
                                'upload_date': datetime.now().isoformat(),
                                'warnings': paper_data.get('warnings', [])
                            },
                            uploaded_by=request.user
                        )
                        
                        results['uploaded_count'] += 1
                        results['success_count'] += 1  # Alias for frontend
                        results['details'].append({
                            'filename': file.name,
                            'status': 'success',
                            'paper_id': paper.id,
                            'display_name': paper.get_display_name()
                        })
                    
                    except IntegrityError:
                        # Database rejected duplicate - this is expected
                        results['skipped_count'] += 1
                        results['details'].append({
                            'filename': file.name,
                            'status': 'skipped',
                            'reason': 'Duplicate paper already exists'
                        })
                    
                except Exception as e:
                    results['failed_count'] += 1
                    results['details'].append({
                        'filename': file.name,
                        'status': 'error',
                        'error': str(e)
                    })
            
            return JsonResponse(results)
        
        else:
            return JsonResponse({'success': False, 'error': 'Invalid action'})
    
    # GET request - show form
    exam_boards = ExamBoard.objects.all().order_by('name_full')
    context = {
        'exam_boards': exam_boards,
    }
    return render(request, 'core/content/official_papers_upload.html', context)


# ===== STUDENT CONTENT MANAGEMENT VIEWS =====

@require_content_manager
def create_interactive_question(request):
    """Create new interactive question"""
    from .models import InteractiveQuestion
    import json
    
    if request.method == 'POST':
        subject_id = request.POST.get('subject')
        exam_board_id = request.POST.get('exam_board')
        grade_id = request.POST.get('grade')
        topic = request.POST.get('topic')
        question_type = request.POST.get('question_type')
        difficulty = request.POST.get('difficulty')
        question_text = request.POST.get('question_text')
        explanation = request.POST.get('explanation', '')
        points = request.POST.get('points', 1)
        question_image = request.FILES.get('question_image')
        
        # Validation
        if not all([subject_id, exam_board_id, grade_id, topic, question_type, difficulty, question_text]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('create_interactive_question')
        
        # Get correct answer and options based on question type
        correct_answer = ''
        options = None
        matching_pairs = None
        
        if question_type == 'mcq':
            # Get options and correct answer
            option_count = int(request.POST.get('option_count', 4))
            options = []
            for i in range(option_count):
                option_text = request.POST.get(f'option_{i}')
                if option_text:
                    options.append(option_text)
            correct_answer = request.POST.get('correct_answer_mcq', '')
            
        elif question_type == 'true_false':
            correct_answer = request.POST.get('correct_answer_tf', '')
            
        elif question_type == 'fill_blank':
            correct_answer = request.POST.get('correct_answer_fill', '')
            
        elif question_type == 'matching':
            # Get matching pairs
            pair_count = int(request.POST.get('pair_count', 4))
            matching_pairs = []
            for i in range(pair_count):
                left = request.POST.get(f'pair_left_{i}')
                right = request.POST.get(f'pair_right_{i}')
                if left and right:
                    matching_pairs.append({'left': left, 'right': right})
            correct_answer = json.dumps(matching_pairs)
            
        elif question_type == 'essay':
            correct_answer = ''  # No correct answer for essay questions
        
        # Create question
        question = InteractiveQuestion.objects.create(
            subject_id=subject_id,
            exam_board_id=exam_board_id,
            grade_id=grade_id,
            topic=topic,
            question_type=question_type,
            difficulty=difficulty,
            question_text=question_text,
            question_image=question_image,
            options=options,
            correct_answer=correct_answer,
            matching_pairs=matching_pairs,
            explanation=explanation,
            points=int(points),
            created_by=request.user
        )
        
        messages.success(request, f'Question created successfully!')
        return redirect('manage_interactive_questions')
    
    # GET request - show form
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    exam_boards = ExamBoard.objects.all()
    
    context = {
        'subjects': subjects,
        'grades': grades,
        'exam_boards': exam_boards,
    }
    
    return render(request, 'core/content/interactive_question_form.html', context)


@require_content_manager
def manage_interactive_questions(request):
    """List and manage interactive questions"""
    from .models import InteractiveQuestion
    
    # Get filter parameters
    subject_filter = request.GET.get('subject', '')
    grade_filter = request.GET.get('grade', '')
    question_type_filter = request.GET.get('question_type', '')
    difficulty_filter = request.GET.get('difficulty', '')
    search_query = request.GET.get('search', '')
    
    # Filter questions
    questions = InteractiveQuestion.objects.all().select_related('subject', 'grade', 'exam_board')
    
    if subject_filter:
        questions = questions.filter(subject_id=subject_filter)
    if grade_filter:
        questions = questions.filter(grade_id=grade_filter)
    if question_type_filter:
        questions = questions.filter(question_type=question_type_filter)
    if difficulty_filter:
        questions = questions.filter(difficulty=difficulty_filter)
    if search_query:
        questions = questions.filter(
            Q(question_text__icontains=search_query) |
            Q(topic__icontains=search_query)
        )
    
    questions = questions.order_by('-created_at')
    
    # Get filters for dropdowns
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    
    context = {
        'questions': questions,
        'subjects': subjects,
        'grades': grades,
        'subject_filter': subject_filter,
        'grade_filter': grade_filter,
        'question_type_filter': question_type_filter,
        'difficulty_filter': difficulty_filter,
        'search_query': search_query,
    }
    
    return render(request, 'core/content/interactive_questions_list.html', context)


@require_content_manager
def edit_interactive_question(request, question_id):
    """Edit interactive question"""
    from .models import InteractiveQuestion
    import json
    
    question = get_object_or_404(InteractiveQuestion, id=question_id)
    
    if request.method == 'POST':
        question.subject_id = request.POST.get('subject')
        question.exam_board_id = request.POST.get('exam_board')
        question.grade_id = request.POST.get('grade')
        question.topic = request.POST.get('topic')
        question.question_type = request.POST.get('question_type')
        question.difficulty = request.POST.get('difficulty')
        question.question_text = request.POST.get('question_text')
        question.explanation = request.POST.get('explanation', '')
        question.points = int(request.POST.get('points', 1))
        
        if request.FILES.get('question_image'):
            question.question_image = request.FILES.get('question_image')
        
        # Update correct answer and options based on question type
        if question.question_type == 'mcq':
            option_count = int(request.POST.get('option_count', 4))
            options = []
            for i in range(option_count):
                option_text = request.POST.get(f'option_{i}')
                if option_text:
                    options.append(option_text)
            question.options = options
            question.correct_answer = request.POST.get('correct_answer_mcq', '')
            
        elif question.question_type == 'true_false':
            question.correct_answer = request.POST.get('correct_answer_tf', '')
            
        elif question.question_type == 'fill_blank':
            question.correct_answer = request.POST.get('correct_answer_fill', '')
            
        elif question.question_type == 'matching':
            pair_count = int(request.POST.get('pair_count', 4))
            matching_pairs = []
            for i in range(pair_count):
                left = request.POST.get(f'pair_left_{i}')
                right = request.POST.get(f'pair_right_{i}')
                if left and right:
                    matching_pairs.append({'left': left, 'right': right})
            question.matching_pairs = matching_pairs
            question.correct_answer = json.dumps(matching_pairs)
        
        question.save()
        messages.success(request, 'Question updated successfully!')
        return redirect('manage_interactive_questions')
    
    # GET request - show form
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    exam_boards = ExamBoard.objects.all()
    
    context = {
        'question': question,
        'subjects': subjects,
        'grades': grades,
        'exam_boards': exam_boards,
        'editing': True,
    }
    
    return render(request, 'core/content/interactive_question_form.html', context)


@require_content_manager
def delete_interactive_question(request, question_id):
    """Delete interactive question"""
    from .models import InteractiveQuestion
    
    if request.method == 'POST':
        question = get_object_or_404(InteractiveQuestion, id=question_id)
        question.delete()
        messages.success(request, 'Question deleted successfully!')
    
    return redirect('manage_interactive_questions')


@require_content_manager
def create_student_quiz(request):
    """Create new student quiz with multi-step builder"""
    from .models import StudentQuiz, InteractiveQuestion
    import json
    
    if request.method == 'POST':
        # Check which step we're on
        step = request.POST.get('step', '1')
        
        if step == 'final':
            # Final step - create quiz
            title = request.POST.get('title')
            subject_id = request.POST.get('subject')
            exam_board_id = request.POST.get('exam_board')
            grade_id = request.POST.get('grade')
            topic = request.POST.get('topic')
            difficulty = request.POST.get('difficulty')
            length = int(request.POST.get('length', 10))
            is_pro_content = request.POST.get('is_pro_content') == 'on'
            selected_questions = json.loads(request.POST.get('selected_questions', '[]'))
            
            # Validation
            if not all([title, subject_id, exam_board_id, grade_id, topic, difficulty]):
                messages.error(request, 'Please fill in all required fields.')
                return redirect('create_student_quiz')
            
            # Create quiz
            quiz = StudentQuiz.objects.create(
                title=title,
                subject_id=subject_id,
                exam_board_id=exam_board_id,
                grade_id=grade_id,
                topic=topic,
                difficulty=difficulty,
                length=length,
                is_pro_content=is_pro_content,
                created_by=request.user
            )
            
            # Add questions to quiz
            for question_id in selected_questions:
                try:
                    question = InteractiveQuestion.objects.get(id=question_id)
                    quiz.questions.add(question)
                except InteractiveQuestion.DoesNotExist:
                    pass
            
            messages.success(request, f'Quiz "{title}" created successfully with {len(selected_questions)} questions!')
            return redirect('manage_student_quizzes')
    
    # GET request - show multi-step form
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    exam_boards = ExamBoard.objects.all()
    
    context = {
        'subjects': subjects,
        'grades': grades,
        'exam_boards': exam_boards,
    }
    
    return render(request, 'core/content/student_quiz_form.html', context)


@require_content_manager
def manage_student_quizzes(request):
    """List and manage student quizzes"""
    from .models import StudentQuiz
    
    # Get filter parameters
    subject_filter = request.GET.get('subject', '')
    grade_filter = request.GET.get('grade', '')
    status_filter = request.GET.get('status', '')  # free or pro
    search_query = request.GET.get('search', '')
    
    # Filter quizzes
    quizzes = StudentQuiz.objects.all().select_related('subject', 'grade', 'exam_board').prefetch_related('questions')
    
    if subject_filter:
        quizzes = quizzes.filter(subject_id=subject_filter)
    if grade_filter:
        quizzes = quizzes.filter(grade_id=grade_filter)
    if status_filter == 'free':
        quizzes = quizzes.filter(is_pro_content=False)
    elif status_filter == 'pro':
        quizzes = quizzes.filter(is_pro_content=True)
    if search_query:
        quizzes = quizzes.filter(
            Q(title__icontains=search_query) |
            Q(topic__icontains=search_query)
        )
    
    quizzes = quizzes.order_by('-created_at')
    
    # Get filters for dropdowns
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    
    context = {
        'quizzes': quizzes,
        'subjects': subjects,
        'grades': grades,
        'subject_filter': subject_filter,
        'grade_filter': grade_filter,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'core/content/student_quizzes_list.html', context)


@require_content_manager
def delete_student_quiz(request, quiz_id):
    """Delete student quiz"""
    from .models import StudentQuiz
    
    if request.method == 'POST':
        quiz = get_object_or_404(StudentQuiz, id=quiz_id)
        quiz.delete()
        messages.success(request, 'Quiz deleted successfully!')
    
    return redirect('manage_student_quizzes')


@require_content_manager
def create_note(request):
    """Create new study note"""
    from .models import Note
    
    if request.method == 'POST':
        title = request.POST.get('title')
        subject_id = request.POST.get('subject')
        exam_board_id = request.POST.get('exam_board')
        grade_id = request.POST.get('grade')
        topic = request.POST.get('topic')
        
        full_version_file = request.FILES.get('full_version')
        summary_version_file = request.FILES.get('summary_version')
        full_version_text = request.POST.get('full_version_text', '')
        summary_version_text = request.POST.get('summary_version_text', '')
        
        # Validation
        if not all([title, subject_id, exam_board_id, grade_id, topic]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('create_note')
        
        # Create note
        note = Note.objects.create(
            title=title,
            subject_id=subject_id,
            exam_board_id=exam_board_id,
            grade_id=grade_id,
            topic=topic,
            full_version=full_version_file,
            summary_version=summary_version_file,
            full_version_text=full_version_text,
            summary_version_text=summary_version_text,
            created_by=request.user
        )
        
        messages.success(request, f'Note "{title}" created successfully!')
        return redirect('manage_notes')
    
    # GET request - show form
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    exam_boards = ExamBoard.objects.all()
    
    context = {
        'subjects': subjects,
        'grades': grades,
        'exam_boards': exam_boards,
    }
    
    return render(request, 'core/content/note_form.html', context)


@require_content_manager
def manage_notes(request):
    """List and manage study notes"""
    from .models import Note
    
    # Get filter parameters
    subject_filter = request.GET.get('subject', '')
    grade_filter = request.GET.get('grade', '')
    search_query = request.GET.get('search', '')
    
    # Filter notes
    notes = Note.objects.all().select_related('subject', 'grade', 'exam_board')
    
    if subject_filter:
        notes = notes.filter(subject_id=subject_filter)
    if grade_filter:
        notes = notes.filter(grade_id=grade_filter)
    if search_query:
        notes = notes.filter(
            Q(title__icontains=search_query) |
            Q(topic__icontains=search_query)
        )
    
    notes = notes.order_by('-created_at')
    
    # Get filters for dropdowns
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    
    context = {
        'notes': notes,
        'subjects': subjects,
        'grades': grades,
        'subject_filter': subject_filter,
        'grade_filter': grade_filter,
        'search_query': search_query,
    }
    
    return render(request, 'core/content/notes_list.html', context)


@require_content_manager
def delete_note(request, note_id):
    """Delete study note"""
    from .models import Note
    
    if request.method == 'POST':
        note = get_object_or_404(Note, id=note_id)
        note.delete()
        messages.success(request, 'Note deleted successfully!')
    
    return redirect('manage_notes')


@require_content_manager
def create_flashcard(request):
    """Create new flashcard"""
    from .models import Flashcard
    
    if request.method == 'POST':
        subject_id = request.POST.get('subject')
        exam_board_id = request.POST.get('exam_board')
        grade_id = request.POST.get('grade')
        topic = request.POST.get('topic')
        front_text = request.POST.get('front_text')
        back_text = request.POST.get('back_text')
        image_front = request.FILES.get('image_front')
        image_back = request.FILES.get('image_back')
        
        # Validation
        if not all([subject_id, exam_board_id, grade_id, topic, front_text, back_text]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('create_flashcard')
        
        # Create flashcard
        flashcard = Flashcard.objects.create(
            subject_id=subject_id,
            exam_board_id=exam_board_id,
            grade_id=grade_id,
            topic=topic,
            front_text=front_text,
            back_text=back_text,
            image_front=image_front,
            image_back=image_back,
            created_by=request.user
        )
        
        messages.success(request, 'Flashcard created successfully!')
        return redirect('manage_flashcards')
    
    # GET request - show form
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    exam_boards = ExamBoard.objects.all()
    
    context = {
        'subjects': subjects,
        'grades': grades,
        'exam_boards': exam_boards,
    }
    
    return render(request, 'core/content/flashcard_form.html', context)


@require_content_manager
def manage_flashcards(request):
    """List and manage flashcards"""
    from .models import Flashcard
    
    # Get filter parameters
    subject_filter = request.GET.get('subject', '')
    grade_filter = request.GET.get('grade', '')
    topic_filter = request.GET.get('topic', '')
    
    # Filter flashcards
    flashcards = Flashcard.objects.all().select_related('subject', 'grade', 'exam_board')
    
    if subject_filter:
        flashcards = flashcards.filter(subject_id=subject_filter)
    if grade_filter:
        flashcards = flashcards.filter(grade_id=grade_filter)
    if topic_filter:
        flashcards = flashcards.filter(topic__icontains=topic_filter)
    
    flashcards = flashcards.order_by('subject', 'topic', '-created_at')
    
    # Get filters for dropdowns
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    
    context = {
        'flashcards': flashcards,
        'subjects': subjects,
        'grades': grades,
        'subject_filter': subject_filter,
        'grade_filter': grade_filter,
        'topic_filter': topic_filter,
    }
    
    return render(request, 'core/content/flashcards_list.html', context)


@require_content_manager
def delete_flashcard(request, flashcard_id):
    """Delete flashcard"""
    from .models import Flashcard
    
    if request.method == 'POST':
        flashcard = get_object_or_404(Flashcard, id=flashcard_id)
        flashcard.delete()
        messages.success(request, 'Flashcard deleted successfully!')
    
    return redirect('manage_flashcards')


@require_content_manager
def upload_exam_paper(request):
    """Upload new exam paper"""
    from .models import ExamPaper, InteractiveQuestion
    
    if request.method == 'POST':
        title = request.POST.get('title')
        subject_id = request.POST.get('subject')
        exam_board_id = request.POST.get('exam_board')
        grade_id = request.POST.get('grade')
        year = request.POST.get('year')
        paper_file = request.FILES.get('paper_file')
        marking_scheme = request.FILES.get('marking_scheme')
        is_pro_content = request.POST.get('is_pro_content') == 'on'
        interactive_questions = request.POST.getlist('interactive_questions')
        
        # Validation
        if not all([title, subject_id, exam_board_id, grade_id, paper_file]):
            messages.error(request, 'Please fill in all required fields and upload the paper file.')
            return redirect('upload_exam_paper')
        
        # Create exam paper
        exam_paper = ExamPaper.objects.create(
            title=title,
            subject_id=subject_id,
            exam_board_id=exam_board_id,
            grade_id=grade_id,
            year=int(year) if year else None,
            paper_file=paper_file,
            marking_scheme=marking_scheme,
            has_interactive_version=bool(interactive_questions),
            is_pro_content=is_pro_content,
            created_by=request.user
        )
        
        # Link interactive questions if provided
        if interactive_questions:
            for question_id in interactive_questions:
                try:
                    question = InteractiveQuestion.objects.get(id=question_id)
                    exam_paper.interactive_questions.add(question)
                except InteractiveQuestion.DoesNotExist:
                    pass
        
        messages.success(request, f'Exam paper "{title}" uploaded successfully!')
        return redirect('manage_exam_papers')
    
    # GET request - show form
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    exam_boards = ExamBoard.objects.all()
    
    context = {
        'subjects': subjects,
        'grades': grades,
        'exam_boards': exam_boards,
    }
    
    return render(request, 'core/content/exam_paper_form.html', context)


@require_content_manager
def manage_exam_papers(request):
    """List and manage exam papers"""
    from .models import ExamPaper
    
    # Get filter parameters
    subject_filter = request.GET.get('subject', '')
    grade_filter = request.GET.get('grade', '')
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    # Filter exam papers
    papers = ExamPaper.objects.all().select_related('subject', 'grade', 'exam_board')
    
    if subject_filter:
        papers = papers.filter(subject_id=subject_filter)
    if grade_filter:
        papers = papers.filter(grade_id=grade_filter)
    if status_filter == 'free':
        papers = papers.filter(is_pro_content=False)
    elif status_filter == 'pro':
        papers = papers.filter(is_pro_content=True)
    if search_query:
        papers = papers.filter(title__icontains=search_query)
    
    papers = papers.order_by('-year', '-created_at')
    
    # Get filters for dropdowns
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    
    context = {
        'papers': papers,
        'subjects': subjects,
        'grades': grades,
        'subject_filter': subject_filter,
        'grade_filter': grade_filter,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'core/content/exam_papers_list.html', context)


@require_content_manager
def delete_exam_paper(request, paper_id):
    """Delete exam paper"""
    from .models import ExamPaper
    
    if request.method == 'POST':
        paper = get_object_or_404(ExamPaper, id=paper_id)
        paper.delete()
        messages.success(request, 'Exam paper deleted successfully!')
    
    return redirect('manage_exam_papers')


@require_content_manager
def manage_syllabi(request):
    """List and manage syllabi"""
    from .models import Syllabus
    
    subject_filter = request.GET.get('subject', '')
    board_filter = request.GET.get('board', '')
    search_query = request.GET.get('search', '')
    
    syllabi = Syllabus.objects.all().select_related('subject', 'exam_board', 'grade')
    
    if subject_filter:
        syllabi = syllabi.filter(subject_id=subject_filter)
    if board_filter:
        syllabi = syllabi.filter(exam_board_id=board_filter)
    if search_query:
        syllabi = syllabi.filter(title__icontains=search_query)
    
    syllabi = syllabi.order_by('-year', 'exam_board', 'subject')
    
    subjects = Subject.objects.all()
    exam_boards = ExamBoard.objects.all()
    
    context = {
        'syllabi': syllabi,
        'subjects': subjects,
        'exam_boards': exam_boards,
        'subject_filter': subject_filter,
        'board_filter': board_filter,
        'search_query': search_query,
    }
    
    return render(request, 'core/content/syllabi_list.html', context)


@require_content_manager
def create_syllabus(request):
    """Create a new syllabus"""
    from .models import Syllabus
    
    if request.method == 'POST':
        title = request.POST.get('title')
        subject_id = request.POST.get('subject')
        exam_board_id = request.POST.get('exam_board')
        grade_id = request.POST.get('grade')
        year = request.POST.get('year')
        description = request.POST.get('description', '')
        external_url = request.POST.get('external_url', '')
        syllabus_file = request.FILES.get('file')
        
        syllabus = Syllabus.objects.create(
            title=title,
            subject_id=subject_id,
            exam_board_id=exam_board_id,
            grade_id=grade_id if grade_id else None,
            year=int(year) if year else None,
            description=description,
            external_url=external_url,
            file=syllabus_file,
            created_by=request.user
        )
        
        messages.success(request, f'Syllabus "{title}" created successfully!')
        return redirect('manage_syllabi')
    
    subjects = Subject.objects.all()
    grades = Grade.objects.all()
    exam_boards = ExamBoard.objects.all()
    
    context = {
        'subjects': subjects,
        'grades': grades,
        'exam_boards': exam_boards,
    }
    
    return render(request, 'core/content/syllabus_form.html', context)


@require_content_manager
def delete_syllabus(request, syllabus_id):
    """Delete syllabus"""
    from .models import Syllabus
    
    if request.method == 'POST':
        syllabus = get_object_or_404(Syllabus, id=syllabus_id)
        syllabus.delete()
        messages.success(request, 'Syllabus deleted successfully!')
    
    return redirect('manage_syllabi')


@require_content_manager
def get_questions_ajax(request):
    """AJAX endpoint to get filtered questions for quiz builder"""
    from .models import InteractiveQuestion
    import json
    
    subject_id = request.GET.get('subject')
    grade_id = request.GET.get('grade')
    topic = request.GET.get('topic')
    difficulty = request.GET.get('difficulty')
    question_type = request.GET.get('question_type')
    
    questions = InteractiveQuestion.objects.all()
    
    if subject_id:
        questions = questions.filter(subject_id=subject_id)
    if grade_id:
        questions = questions.filter(grade_id=grade_id)
    if topic:
        questions = questions.filter(topic__icontains=topic)
    if difficulty:
        questions = questions.filter(difficulty=difficulty)
    if question_type:
        questions = questions.filter(question_type=question_type)
    
    questions = questions.select_related('subject', 'grade').order_by('-created_at')[:50]
    
    # Serialize questions
    questions_data = []
    for q in questions:
        questions_data.append({
            'id': q.id,
            'question_text': q.question_text[:100],
            'question_type': q.get_question_type_display(),
            'difficulty': q.get_difficulty_display(),
            'topic': q.topic,
            'points': q.points,
        })
    
    return JsonResponse({'questions': questions_data})


# ===== PUBLIC EXAM PAPERS BROWSE VIEWS =====

def public_papers_browse(request):
    """Public page to browse official exam papers - no login required"""
    from .models import OfficialExamPaper, ExamBoard
    
    exam_boards = ExamBoard.objects.all().order_by('name_full')
    
    context = {
        'exam_boards': exam_boards,
    }
    return render(request, 'core/public/papers_browse.html', context)


def public_papers_api(request):
    """AJAX API for getting papers with cascading filters"""
    from .models import OfficialExamPaper, ExamBoard
    from django.core.paginator import Paginator
    
    board_id = request.GET.get('board')
    subject_code = request.GET.get('subject')
    year = request.GET.get('year')
    session = request.GET.get('session')
    paper_type = request.GET.get('paper_type')
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    
    papers = OfficialExamPaper.objects.all().order_by('-year', 'subject_code', 'paper_number')
    
    if board_id:
        papers = papers.filter(exam_board_id=board_id)
    if subject_code:
        papers = papers.filter(subject_code=subject_code)
    if year:
        papers = papers.filter(year=year)
    if session:
        papers = papers.filter(session=session)
    if paper_type:
        papers = papers.filter(paper_type=paper_type)
    
    paginator = Paginator(papers, per_page)
    page_obj = paginator.get_page(page)
    
    papers_data = []
    for paper in page_obj:
        papers_data.append({
            'id': paper.id,
            'subject_code': paper.subject_code,
            'subject_name': paper.subject_name,
            'year': paper.year,
            'session': paper.get_session_display(),
            'paper_number': paper.paper_number,
            'variant': paper.variant,
            'paper_type': paper.get_paper_type_display(),
            'paper_type_code': paper.paper_type,
            'display_name': paper.get_display_name(),
            'file_url': paper.file.url if paper.file else None,
        })
    
    return JsonResponse({
        'success': True,
        'papers': papers_data,
        'total': paginator.count,
        'page': page,
        'pages': paginator.num_pages,
        'has_next': page_obj.has_next(),
        'has_prev': page_obj.has_previous(),
    })


def public_papers_filters(request):
    """AJAX API for getting filter options based on current selection"""
    from .models import OfficialExamPaper
    
    board_id = request.GET.get('board')
    subject_code = request.GET.get('subject')
    filter_type = request.GET.get('filter_type', 'subjects')
    
    papers = OfficialExamPaper.objects.all()
    
    if board_id:
        papers = papers.filter(exam_board_id=board_id)
    if subject_code and filter_type != 'subjects':
        papers = papers.filter(subject_code=subject_code)
    
    if filter_type == 'subjects':
        # Get unique subjects for selected board
        subjects = papers.values('subject_code', 'subject_name').distinct().order_by('subject_name')
        return JsonResponse({
            'success': True,
            'options': [{'code': s['subject_code'], 'name': s['subject_name'] or s['subject_code']} for s in subjects]
        })
    
    elif filter_type == 'years':
        # Get unique years for selected board/subject
        years = papers.values_list('year', flat=True).distinct().order_by('-year')
        return JsonResponse({
            'success': True,
            'options': list(years)
        })
    
    elif filter_type == 'sessions':
        # Get unique sessions for selected filters
        sessions = papers.values_list('session', flat=True).distinct()
        session_choices = dict(OfficialExamPaper.SESSION_CHOICES)
        return JsonResponse({
            'success': True,
            'options': [{'code': s, 'name': session_choices.get(s, s)} for s in sessions]
        })
    
    elif filter_type == 'paper_types':
        # Get unique paper types
        paper_types = papers.values_list('paper_type', flat=True).distinct()
        type_choices = dict(OfficialExamPaper.PAPER_TYPE_CHOICES)
        return JsonResponse({
            'success': True,
            'options': [{'code': t, 'name': type_choices.get(t, t)} for t in paper_types]
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid filter type'})


def public_paper_view(request, paper_id):
    """Individual paper view/download page with ad placeholders"""
    from .models import OfficialExamPaper
    
    paper = get_object_or_404(OfficialExamPaper, id=paper_id)
    
    # Get related papers (same subject, different years)
    related_papers = OfficialExamPaper.objects.filter(
        exam_board=paper.exam_board,
        subject_code=paper.subject_code
    ).exclude(id=paper.id).order_by('-year')[:10]
    
    context = {
        'paper': paper,
        'related_papers': related_papers,
    }
    return render(request, 'core/public/paper_view.html', context)


def public_paper_download(request, paper_id):
    """Download paper file - tracks downloads for analytics"""
    from .models import OfficialExamPaper
    from django.http import FileResponse
    import os
    
    paper = get_object_or_404(OfficialExamPaper, id=paper_id)
    
    if not paper.file:
        raise Http404("Paper file not found")
    
    response = FileResponse(paper.file.open('rb'), as_attachment=True)
    response['Content-Disposition'] = f'attachment; filename="{paper.original_filename}"'
    
    return response


# ============================================================================
# TEACHER ASSESSMENT BUILDER
# ============================================================================

@require_teacher
def create_assessment(request):
    """Google Forms-style assessment builder for teachers"""
    from .models import SubscribedSubject, Grade, TeacherAssessment
    
    category = request.GET.get('category', 'test')
    
    # Category icons for display
    category_icons = {
        'exam': 'fa-graduation-cap',
        'test': 'fa-file-alt',
        'assignment': 'fa-tasks',
        'homework': 'fa-home',
        'classwork': 'fa-book-open',
    }
    
    subjects = SubscribedSubject.objects.filter(user=request.user).select_related('subject')
    grades = Grade.objects.all().order_by('number')
    
    context = {
        'category': category,
        'category_icon': category_icons.get(category, 'fa-file-alt'),
        'subjects': subjects,
        'grades': grades,
    }
    return render(request, 'core/teacher/create_assessment.html', context)


@require_teacher
def save_assessment(request):
    """Save assessment and questions"""
    from .models import TeacherAssessment, TeacherQuestion, TeacherQuestionOption, Subject, Grade
    import json
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    try:
        assessment_data = json.loads(request.POST.get('assessment', '{}'))
        questions_data = json.loads(request.POST.get('questions', '[]'))
        
        # Create assessment
        assessment = TeacherAssessment(
            teacher=request.user,
            title=assessment_data.get('title', 'Untitled'),
            description=assessment_data.get('description', ''),
            category=assessment_data.get('category', 'test'),
            instructions=assessment_data.get('instructions', ''),
            status=assessment_data.get('status', 'draft'),
        )
        
        # Handle optional fields
        if assessment_data.get('subject_id'):
            assessment.subject = Subject.objects.filter(id=assessment_data['subject_id']).first()
        if assessment_data.get('grade_id'):
            assessment.grade = Grade.objects.filter(id=assessment_data['grade_id']).first()
        if assessment_data.get('time_limit'):
            assessment.time_limit = int(assessment_data['time_limit'])
        
        assessment.save()
        
        # Create questions
        total_marks = 0
        for i, q_data in enumerate(questions_data):
            question = TeacherQuestion(
                assessment=assessment,
                question_type=q_data.get('type', 'mcq'),
                question_text=q_data.get('text', ''),
                marks=int(q_data.get('marks', 1)),
                order=i,
                is_required=True,
            )
            
            # Handle correct answer based on type
            if q_data.get('type') in ['short_answer', 'long_answer']:
                question.correct_answer = q_data.get('expected_answer', '')
            elif q_data.get('type') == 'true_false':
                question.correct_answer = q_data.get('correct_answer', 'true')
            elif q_data.get('type') == 'fill_blank':
                question.correct_answer = q_data.get('correct_answer', '')
            
            # Handle explanation
            question.explanation = q_data.get('explanation', '')
            
            # Handle image upload
            image_key = f'question_image_{i}'
            if image_key in request.FILES:
                question.question_image = request.FILES[image_key]
            
            question.save()
            total_marks += question.marks
            
            # Create options for MCQ
            if q_data.get('type') in ['mcq', 'mcq_multi']:
                correct_option = q_data.get('correct_option')
                for j, opt in enumerate(q_data.get('options', [])):
                    if opt.get('text'):
                        TeacherQuestionOption.objects.create(
                            question=question,
                            option_text=opt['text'],
                            is_correct=(j == correct_option) if q_data.get('type') == 'mcq' else opt.get('is_correct', False),
                            order=j
                        )
            
            # Create matching pairs
            elif q_data.get('type') == 'matching':
                for j, pair in enumerate(q_data.get('pairs', [])):
                    if pair.get('left'):
                        TeacherQuestionOption.objects.create(
                            question=question,
                            option_text=pair['left'],
                            match_pair=pair.get('right', ''),
                            order=j
                        )
        
        # Update total marks
        assessment.total_marks = total_marks
        assessment.save()
        
        # Redirect based on category
        category_urls = {
            'exam': 'exams',
            'test': 'tests',
            'assignment': 'assignments',
            'homework': 'homework',
            'classwork': 'classwork',
        }
        redirect_url = reverse(category_urls.get(assessment.category, 'dashboard'))
        
        return JsonResponse({
            'success': True,
            'assessment_id': assessment.id,
            'redirect_url': redirect_url
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})


@require_teacher
def edit_assessment(request, assessment_id):
    """Edit existing assessment"""
    from .models import TeacherAssessment, SubscribedSubject, Grade
    
    assessment = get_object_or_404(TeacherAssessment, id=assessment_id, teacher=request.user)
    subjects = SubscribedSubject.objects.filter(user=request.user).select_related('subject')
    grades = Grade.objects.all().order_by('number')
    
    # Prepare questions data for the editor
    questions_json = []
    for q in assessment.questions.all().prefetch_related('options'):
        q_dict = {
            'id': q.id,
            'type': q.question_type,
            'text': q.question_text,
            'marks': q.marks,
            'explanation': q.explanation,
            'showExplanation': bool(q.explanation),
            'showImageUpload': bool(q.question_image),
            'imagePreview': q.question_image.url if q.question_image else None,
        }
        
        if q.question_type in ['mcq', 'mcq_multi']:
            q_dict['options'] = [{'text': o.option_text, 'is_correct': o.is_correct} for o in q.options.all()]
            correct_idx = next((i for i, o in enumerate(q.options.all()) if o.is_correct), None)
            q_dict['correct_option'] = correct_idx
        elif q.question_type == 'matching':
            q_dict['pairs'] = [{'left': o.option_text, 'right': o.match_pair} for o in q.options.all()]
        elif q.question_type in ['short_answer', 'long_answer']:
            q_dict['expected_answer'] = q.correct_answer
        else:
            q_dict['correct_answer'] = q.correct_answer
            
        questions_json.append(q_dict)
    
    category_icons = {
        'exam': 'fa-graduation-cap',
        'test': 'fa-file-alt',
        'assignment': 'fa-tasks',
        'homework': 'fa-home',
        'classwork': 'fa-book-open',
    }
    
    context = {
        'assessment': assessment,
        'category': assessment.category,
        'category_icon': category_icons.get(assessment.category, 'fa-file-alt'),
        'subjects': subjects,
        'grades': grades,
        'questions_json': json.dumps(questions_json),
        'editing': True,
    }
    return render(request, 'core/teacher/create_assessment.html', context)


@require_teacher
def delete_assessment(request, assessment_id):
    """Delete an assessment"""
    from .models import TeacherAssessment
    
    assessment = get_object_or_404(TeacherAssessment, id=assessment_id, teacher=request.user)
    category = assessment.category
    assessment.delete()
    
    messages.success(request, f'{category.title()} deleted successfully.')
    
    category_urls = {
        'exam': 'exams',
        'test': 'tests',
        'assignment': 'assignments',
        'homework': 'homework',
        'classwork': 'classwork',
    }
    return redirect(category_urls.get(category, 'dashboard'))


@require_teacher
def view_assessment(request, assessment_id):
    """View assessment details and questions"""
    from .models import TeacherAssessment
    
    assessment = get_object_or_404(TeacherAssessment, id=assessment_id, teacher=request.user)
    questions = assessment.questions.all().prefetch_related('options')
    
    category_icons = {
        'exam': 'fa-graduation-cap',
        'test': 'fa-file-alt',
        'assignment': 'fa-tasks',
        'homework': 'fa-home',
        'classwork': 'fa-book-open',
    }
    
    context = {
        'assessment': assessment,
        'questions': questions,
        'category_icon': category_icons.get(assessment.category, 'fa-file-alt'),
    }
    return render(request, 'core/teacher/view_assessment.html', context)


# ============================================================================
# BRILLTECH CORPORATE PAGES
# ============================================================================

def brilltech_landing(request):
    """BrillTech main landing page with hero and service summaries"""
    return render(request, 'core/brilltech/landing.html')


def brilltech_services(request):
    """BrillTech detailed services page with 6 service cards"""
    services = [
        {
            'icon': 'fa-globe',
            'title': 'Website Development',
            'description': 'Custom-built, responsive websites that captivate your audience. From sleek portfolios to complex e-commerce platforms, we craft digital experiences that drive results.',
            'color': 'from-blue-500 to-cyan-400'
        },
        {
            'icon': 'fa-mobile-alt',
            'title': 'Mobile App Development',
            'description': 'Native and cross-platform mobile applications that users love. iOS, Android, or both - we build apps that perform flawlessly and scale effortlessly.',
            'color': 'from-purple-500 to-pink-400'
        },
        {
            'icon': 'fa-headset',
            'title': 'IT Support & Maintenance',
            'description': 'Round-the-clock technical support to keep your systems running smoothly. Proactive monitoring, rapid response, and expert troubleshooting.',
            'color': 'from-green-500 to-emerald-400'
        },
        {
            'icon': 'fa-network-wired',
            'title': 'Network Installation',
            'description': 'Enterprise-grade network infrastructure designed for speed, security, and reliability. From small offices to large campuses, we connect your world.',
            'color': 'from-orange-500 to-amber-400'
        },
        {
            'icon': 'fa-chalkboard-teacher',
            'title': 'Training & Digital Skills',
            'description': 'Empower your team with cutting-edge digital skills. Customized training programs that transform beginners into tech-savvy professionals.',
            'color': 'from-red-500 to-rose-400'
        },
        {
            'icon': 'fa-cloud-upload-alt',
            'title': 'Cloud & Data Backup',
            'description': 'Secure cloud solutions that protect your data and enable seamless collaboration. Automated backups, disaster recovery, and infinite scalability.',
            'color': 'from-indigo-500 to-violet-400'
        },
    ]
    return render(request, 'core/brilltech/services.html', {'services': services})


def brilltech_learning(request):
    """BrillTech learning platform page"""
    return render(request, 'core/brilltech/learning.html')


def brilltech_store(request):
    """BrillTech store page"""
    return render(request, 'core/brilltech/store.html')


def brilltech_dashboard(request):
    """BrillTech dashboard overview page"""
    return render(request, 'core/brilltech/dashboard.html')


# ============================================================================
# PUBLIC SHARE VIEWS FOR STUDENTS
# ============================================================================

def share_content_view(request, token):
    """Public view for shared content - accessible by students via token"""
    from .models import ContentShare
    from django.utils import timezone
    
    share = get_object_or_404(ContentShare, token=token)
    
    if not share.is_valid:
        return render(request, 'core/shared/share_expired.html')
    
    share.view_count += 1
    share.last_accessed = timezone.now()
    share.save()
    
    if share.assessment:
        questions = share.assessment.questions.all().prefetch_related('options')
        
        category_icons = {
            'exam': 'fa-graduation-cap',
            'test': 'fa-file-alt',
            'assignment': 'fa-tasks',
            'homework': 'fa-home',
            'classwork': 'fa-book-open',
        }
        
        context = {
            'assessment': share.assessment,
            'questions': questions,
            'category_icon': category_icons.get(share.assessment.category, 'fa-file-alt'),
            'is_shared_view': True,
            'share': share,
        }
        return render(request, 'core/shared/assessment_view.html', context)
    
    elif share.document:
        context = {
            'document': share.document,
            'is_shared_view': True,
            'share': share,
        }
        return render(request, 'core/shared/document_view.html', context)
    
    return HttpResponse("Content not found", status=404)


@require_teacher
def create_share_link(request):
    """Create a shareable link for an assessment or document"""
    from .models import ContentShare, TeacherAssessment, UploadedDocument
    import json
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        content_type = data.get('type')
        content_id = data.get('id')
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON payload'}, status=400)
    
    if not content_type or not content_id:
        return JsonResponse({'error': 'Missing type or id'}, status=400)
    
    if content_type == 'assessment':
        assessment = get_object_or_404(TeacherAssessment, id=content_id, teacher=request.user)
        share, created = ContentShare.objects.get_or_create(
            teacher=request.user,
            assessment=assessment,
            is_active=True,
            defaults={'document': None}
        )
    elif content_type == 'document':
        document = get_object_or_404(UploadedDocument, id=content_id, uploaded_by=request.user)
        share, created = ContentShare.objects.get_or_create(
            teacher=request.user,
            document=document,
            is_active=True,
            defaults={'assessment': None}
        )
    else:
        return JsonResponse({'error': 'Invalid content type'}, status=400)
    
    share_url = request.build_absolute_uri(f'/share/{share.token}/')
    
    return JsonResponse({
        'token': share.token,
        'url': share_url,
        'created': created
    })


# ============================================================================
# BRILLTECH CORPORATE PAGES - Apps, About, Contact
# ============================================================================

def brilltech_apps(request):
    """BrillTech apps/products showcase page"""
    apps = [
        {
            'name': 'EduTech Portal',
            'tagline': 'AI-Powered Education Platform',
            'description': 'A comprehensive learning management system for teachers and students. Create lessons, generate AI content, track progress, and manage classrooms with ease.',
            'icon': 'fa-graduation-cap',
            'color': 'from-purple-500 to-indigo-600',
            'features': ['AI Lesson Plans', 'Student Portal', 'Quiz Builder', 'Progress Tracking'],
            'demo_link': '/welcome/teacher/',
            'status': 'Live'
        },
        {
            'name': 'ExamPrep Pro',
            'tagline': 'Smart Exam Preparation',
            'description': 'Access thousands of past papers, practice questions, and AI-generated quizzes. Perfect for Cambridge, Edexcel, CAPS, and other major exam boards.',
            'icon': 'fa-file-alt',
            'color': 'from-emerald-500 to-teal-600',
            'features': ['Past Papers Library', 'Interactive Quizzes', 'Flashcards', 'Study Notes'],
            'demo_link': '/welcome/student/',
            'status': 'Live'
        },
        {
            'name': 'SchoolSync',
            'tagline': 'School Management System',
            'description': 'Complete school administration solution. Manage admissions, attendance, fees, timetables, and parent communication all in one place.',
            'icon': 'fa-school',
            'color': 'from-blue-500 to-cyan-600',
            'features': ['Admissions', 'Fee Management', 'Timetables', 'Parent Portal'],
            'demo_link': '#',
            'status': 'Coming Soon'
        },
        {
            'name': 'TutorMatch',
            'tagline': 'Connect with Expert Tutors',
            'description': 'Find qualified tutors for any subject. Book sessions, track progress, and manage payments seamlessly. Perfect for students seeking personalized learning.',
            'icon': 'fa-users',
            'color': 'from-orange-500 to-amber-600',
            'features': ['Tutor Discovery', 'Online Sessions', 'Progress Reports', 'Secure Payments'],
            'demo_link': '#',
            'status': 'Coming Soon'
        },
        {
            'name': 'ContentForge',
            'tagline': 'AI Content Creation Studio',
            'description': 'Generate educational content at scale. Create worksheets, quizzes, lesson plans, and assessments using advanced AI technology.',
            'icon': 'fa-magic',
            'color': 'from-pink-500 to-rose-600',
            'features': ['AI Generation', 'Template Library', 'Bulk Export', 'Multi-format Support'],
            'demo_link': '#',
            'status': 'Beta'
        },
        {
            'name': 'ClassroomLive',
            'tagline': 'Virtual Classroom Solution',
            'description': 'Host live classes, webinars, and interactive sessions. Features whiteboard, screen sharing, breakout rooms, and recording capabilities.',
            'icon': 'fa-video',
            'color': 'from-red-500 to-pink-600',
            'features': ['Live Streaming', 'Interactive Whiteboard', 'Breakout Rooms', 'Recording'],
            'demo_link': '#',
            'status': 'Coming Soon'
        },
    ]
    return render(request, 'core/brilltech/apps.html', {'apps': apps})


def brilltech_about(request):
    """BrillTech about us page"""
    team = [
        {
            'name': 'Alex Johnson',
            'role': 'CEO & Founder',
            'bio': 'Passionate about leveraging technology to transform education. 15+ years in EdTech.',
            'image': 'https://randomuser.me/api/portraits/men/32.jpg',
        },
        {
            'name': 'Sarah Chen',
            'role': 'CTO',
            'bio': 'Full-stack developer with expertise in AI/ML. Building the future of learning.',
            'image': 'https://randomuser.me/api/portraits/women/44.jpg',
        },
        {
            'name': 'Michael Okonkwo',
            'role': 'Head of Product',
            'bio': 'Former teacher turned product leader. Ensuring every feature serves real needs.',
            'image': 'https://randomuser.me/api/portraits/men/52.jpg',
        },
        {
            'name': 'Emma Williams',
            'role': 'Lead Designer',
            'bio': 'Creating beautiful, intuitive interfaces that make learning enjoyable.',
            'image': 'https://randomuser.me/api/portraits/women/68.jpg',
        },
    ]
    
    milestones = [
        {'year': '2020', 'title': 'BrillTech Founded', 'description': 'Started with a vision to democratize quality education through technology.'},
        {'year': '2021', 'title': 'EduTech Portal Launch', 'description': 'Released our flagship AI-powered education platform to teachers across Africa.'},
        {'year': '2022', 'title': '10,000 Users', 'description': 'Reached our first major milestone of 10,000 active educators on the platform.'},
        {'year': '2023', 'title': 'Student Portal Launch', 'description': 'Expanded with a dedicated student learning portal and mobile app.'},
        {'year': '2024', 'title': 'AI Integration', 'description': 'Integrated GPT-4 for intelligent content generation and personalized learning.'},
        {'year': '2025', 'title': 'Pan-African Expansion', 'description': 'Expanding operations across 15 African countries with localized content.'},
    ]
    
    stats = [
        {'number': '50,000+', 'label': 'Active Users'},
        {'number': '1M+', 'label': 'Lessons Created'},
        {'number': '15', 'label': 'Countries'},
        {'number': '99.9%', 'label': 'Uptime'},
    ]
    
    return render(request, 'core/brilltech/about.html', {
        'team': team,
        'milestones': milestones,
        'stats': stats
    })


def brilltech_contact(request):
    """BrillTech contact page with working form"""
    from .models import ContactSubmission
    from django.core.mail import send_mail
    from django.conf import settings
    import os
    
    success_message = None
    error_message = None
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        company = request.POST.get('company', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        
        if not name or not email or not message:
            error_message = 'Please fill in all required fields (Name, Email, Message).'
        else:
            try:
                submission = ContactSubmission.objects.create(
                    name=name,
                    email=email,
                    phone=phone,
                    company=company,
                    subject=subject or 'Website Contact',
                    message=message
                )
                
                try:
                    email_host_user = os.environ.get('EMAIL_HOST_USER')
                    if email_host_user:
                        send_mail(
                            subject=f'[BrillTech Contact] {subject or "New Inquiry"} from {name}',
                            message=f"""New contact form submission from BrillTech website:

Name: {name}
Email: {email}
Phone: {phone or 'Not provided'}
Company: {company or 'Not provided'}

Message:
{message}

---
View all submissions at: /brilltech/admin/
""",
                            from_email=email_host_user,
                            recipient_list=[email_host_user],
                            fail_silently=True,
                        )
                except Exception as e:
                    pass
                
                success_message = 'Thank you for your message! We will get back to you within 24 hours.'
                
            except Exception as e:
                error_message = 'There was an error submitting your message. Please try again.'
    
    contact_info = {
        'email': 'info@brilltech.com',
        'phone': '+27 11 123 4567',
        'whatsapp': '+27 82 123 4567',
        'address': 'Johannesburg, South Africa',
        'hours': 'Monday - Friday: 8:00 AM - 5:00 PM SAST'
    }
    
    return render(request, 'core/brilltech/contact.html', {
        'success_message': success_message,
        'error_message': error_message,
        'contact_info': contact_info
    })


# ============================================================================
# BRILLTECH ADMIN PORTAL (Separate from EduTech Admin)
# ============================================================================

def brilltech_admin_required(view_func):
    """Decorator to check if user is logged in to BrillTech admin"""
    def wrapper(request, *args, **kwargs):
        if not request.session.get('brilltech_admin_id'):
            return redirect('brilltech_admin_login')
        return view_func(request, *args, **kwargs)
    return wrapper


def brilltech_admin_login(request):
    """BrillTech admin login page"""
    from .models import BrillTechAdmin
    from django.utils import timezone
    
    error = None
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        try:
            admin = BrillTechAdmin.objects.get(username=username, is_active=True)
            if admin.check_password(password):
                request.session['brilltech_admin_id'] = admin.id
                request.session['brilltech_admin_username'] = admin.username
                admin.last_login = timezone.now()
                admin.save()
                return redirect('brilltech_admin_dashboard')
            else:
                error = 'Invalid username or password'
        except BrillTechAdmin.DoesNotExist:
            error = 'Invalid username or password'
    
    return render(request, 'core/brilltech/admin/login.html', {'error': error})


def brilltech_admin_logout(request):
    """Logout from BrillTech admin"""
    request.session.pop('brilltech_admin_id', None)
    request.session.pop('brilltech_admin_username', None)
    return redirect('brilltech_admin_login')


@brilltech_admin_required
def brilltech_admin_dashboard(request):
    """BrillTech admin dashboard with stats"""
    from .models import ContactSubmission
    
    total_submissions = ContactSubmission.objects.count()
    new_submissions = ContactSubmission.objects.filter(status='new').count()
    read_submissions = ContactSubmission.objects.filter(status='read').count()
    replied_submissions = ContactSubmission.objects.filter(status='replied').count()
    
    recent_submissions = ContactSubmission.objects.all()[:5]
    
    return render(request, 'core/brilltech/admin/dashboard.html', {
        'total_submissions': total_submissions,
        'new_submissions': new_submissions,
        'read_submissions': read_submissions,
        'replied_submissions': replied_submissions,
        'recent_submissions': recent_submissions,
    })


@brilltech_admin_required
def brilltech_admin_submissions(request):
    """View all contact submissions"""
    from .models import ContactSubmission
    
    status_filter = request.GET.get('status', '')
    submissions = ContactSubmission.objects.all()
    
    if status_filter:
        submissions = submissions.filter(status=status_filter)
    
    return render(request, 'core/brilltech/admin/submissions.html', {
        'submissions': submissions,
        'status_filter': status_filter,
    })


@brilltech_admin_required
def brilltech_admin_submission_detail(request, submission_id):
    """View single submission detail"""
    from .models import ContactSubmission
    from django.utils import timezone
    
    submission = get_object_or_404(ContactSubmission, id=submission_id)
    
    if not submission.is_read:
        submission.is_read = True
        submission.read_at = timezone.now()
        if submission.status == 'new':
            submission.status = 'read'
        submission.save()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'mark_replied':
            submission.status = 'replied'
            submission.replied_at = timezone.now()
            submission.save()
        elif action == 'archive':
            submission.status = 'archived'
            submission.save()
        elif action == 'save_notes':
            submission.admin_notes = request.POST.get('notes', '')
            submission.save()
        return redirect('brilltech_admin_submission_detail', submission_id=submission_id)
    
    return render(request, 'core/brilltech/admin/submission_detail.html', {
        'submission': submission,
    })


@brilltech_admin_required
def brilltech_admin_change_password(request):
    """Change BrillTech admin password"""
    from .models import BrillTechAdmin
    
    success = False
    error = None
    
    admin_id = request.session.get('brilltech_admin_id')
    admin = get_object_or_404(BrillTechAdmin, id=admin_id)
    
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        if not admin.check_password(current_password):
            error = 'Current password is incorrect'
        elif len(new_password) < 6:
            error = 'New password must be at least 6 characters'
        elif new_password != confirm_password:
            error = 'New passwords do not match'
        else:
            admin.set_password(new_password)
            admin.save()
            success = True
    
    return render(request, 'core/brilltech/admin/change_password.html', {
        'success': success,
        'error': error,
        'admin': admin,
    })


# ============================================
# CONTENT MANAGER - Topic/Subtopic/Concept/VideoLesson Management
# ============================================

@require_content_manager
def manage_topics(request):
    """List all topics with filters by subject"""
    from .models import Topic, Subject
    
    topics = Topic.objects.select_related('subject').all()
    subjects = Subject.objects.all().order_by('name')
    
    # Filter by subject
    subject_id = request.GET.get('subject')
    if subject_id:
        topics = topics.filter(subject_id=subject_id)
    
    # Filter by active status
    status = request.GET.get('status')
    if status == 'active':
        topics = topics.filter(is_active=True)
    elif status == 'inactive':
        topics = topics.filter(is_active=False)
    
    # Search by name
    search = request.GET.get('search', '').strip()
    if search:
        topics = topics.filter(Q(name__icontains=search) | Q(description__icontains=search))
    
    topics = topics.order_by('subject__name', 'order', 'name')
    
    return render(request, 'core/content/topics_list.html', {
        'topics': topics,
        'subjects': subjects,
        'selected_subject': subject_id,
        'selected_status': status,
        'search': search,
    })


@require_content_manager
def add_topic(request):
    """Add a new topic"""
    from .models import Topic, Subject
    
    subjects = Subject.objects.all().order_by('name')
    
    if request.method == 'POST':
        subject_id = request.POST.get('subject')
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        order = request.POST.get('order', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        if not subject_id or not name:
            messages.error(request, 'Subject and name are required.')
            return render(request, 'core/content/topic_form.html', {
                'subjects': subjects,
                'form_data': request.POST,
            })
        
        try:
            subject = Subject.objects.get(id=subject_id)
            Topic.objects.create(
                subject=subject,
                name=name,
                description=description,
                order=int(order) if order else 0,
                is_active=is_active,
            )
            messages.success(request, f'Topic "{name}" created successfully.')
            return redirect('manage_topics')
        except Subject.DoesNotExist:
            messages.error(request, 'Invalid subject selected.')
        except IntegrityError:
            messages.error(request, 'A topic with this name already exists for this subject.')
        except Exception as e:
            messages.error(request, f'Error creating topic: {str(e)}')
    
    return render(request, 'core/content/topic_form.html', {
        'subjects': subjects,
    })


@require_content_manager
def edit_topic(request, topic_id):
    """Edit an existing topic"""
    from .models import Topic, Subject
    
    topic = get_object_or_404(Topic, id=topic_id)
    subjects = Subject.objects.all().order_by('name')
    
    if request.method == 'POST':
        subject_id = request.POST.get('subject')
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        order = request.POST.get('order', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        if not subject_id or not name:
            messages.error(request, 'Subject and name are required.')
            return render(request, 'core/content/topic_form.html', {
                'subjects': subjects,
                'topic': topic,
                'is_edit': True,
            })
        
        try:
            subject = Subject.objects.get(id=subject_id)
            topic.subject = subject
            topic.name = name
            topic.description = description
            topic.order = int(order) if order else 0
            topic.is_active = is_active
            topic.save()
            messages.success(request, f'Topic "{name}" updated successfully.')
            return redirect('manage_topics')
        except Subject.DoesNotExist:
            messages.error(request, 'Invalid subject selected.')
        except IntegrityError:
            messages.error(request, 'A topic with this name already exists for this subject.')
        except Exception as e:
            messages.error(request, f'Error updating topic: {str(e)}')
    
    return render(request, 'core/content/topic_form.html', {
        'subjects': subjects,
        'topic': topic,
        'is_edit': True,
    })


@require_content_manager
def delete_topic(request, topic_id):
    """Delete a topic"""
    from .models import Topic
    
    topic = get_object_or_404(Topic, id=topic_id)
    
    if request.method == 'POST':
        name = topic.name
        topic.delete()
        messages.success(request, f'Topic "{name}" deleted successfully.')
    
    return redirect('manage_topics')


@require_content_manager
def manage_subtopics(request):
    """List all subtopics with filters"""
    from .models import Subtopic, Topic, Subject
    
    subtopics = Subtopic.objects.select_related('topic', 'topic__subject').all()
    subjects = Subject.objects.all().order_by('name')
    topics = Topic.objects.select_related('subject').all().order_by('subject__name', 'name')
    
    # Filter by subject
    subject_id = request.GET.get('subject')
    if subject_id:
        subtopics = subtopics.filter(topic__subject_id=subject_id)
        topics = topics.filter(subject_id=subject_id)
    
    # Filter by topic
    topic_id = request.GET.get('topic')
    if topic_id:
        subtopics = subtopics.filter(topic_id=topic_id)
    
    # Filter by active status
    status = request.GET.get('status')
    if status == 'active':
        subtopics = subtopics.filter(is_active=True)
    elif status == 'inactive':
        subtopics = subtopics.filter(is_active=False)
    
    # Search by name
    search = request.GET.get('search', '').strip()
    if search:
        subtopics = subtopics.filter(Q(name__icontains=search) | Q(description__icontains=search))
    
    subtopics = subtopics.order_by('topic__subject__name', 'topic__name', 'order', 'name')
    
    return render(request, 'core/content/subtopics_list.html', {
        'subtopics': subtopics,
        'subjects': subjects,
        'topics': topics,
        'selected_subject': subject_id,
        'selected_topic': topic_id,
        'selected_status': status,
        'search': search,
    })


@require_content_manager
def add_subtopic(request):
    """Add a new subtopic"""
    from .models import Subtopic, Topic, Subject
    
    subjects = Subject.objects.all().order_by('name')
    topics = Topic.objects.select_related('subject').all().order_by('subject__name', 'name')
    
    if request.method == 'POST':
        topic_id = request.POST.get('topic')
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        order = request.POST.get('order', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        if not topic_id or not name:
            messages.error(request, 'Topic and name are required.')
            return render(request, 'core/content/subtopic_form.html', {
                'subjects': subjects,
                'topics': topics,
                'form_data': request.POST,
            })
        
        try:
            topic = Topic.objects.get(id=topic_id)
            Subtopic.objects.create(
                topic=topic,
                name=name,
                description=description,
                order=int(order) if order else 0,
                is_active=is_active,
            )
            messages.success(request, f'Subtopic "{name}" created successfully.')
            return redirect('manage_subtopics')
        except Topic.DoesNotExist:
            messages.error(request, 'Invalid topic selected.')
        except IntegrityError:
            messages.error(request, 'A subtopic with this name already exists for this topic.')
        except Exception as e:
            messages.error(request, f'Error creating subtopic: {str(e)}')
    
    return render(request, 'core/content/subtopic_form.html', {
        'subjects': subjects,
        'topics': topics,
    })


@require_content_manager
def edit_subtopic(request, subtopic_id):
    """Edit an existing subtopic"""
    from .models import Subtopic, Topic, Subject
    
    subtopic = get_object_or_404(Subtopic, id=subtopic_id)
    subjects = Subject.objects.all().order_by('name')
    topics = Topic.objects.select_related('subject').all().order_by('subject__name', 'name')
    
    if request.method == 'POST':
        topic_id = request.POST.get('topic')
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        order = request.POST.get('order', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        if not topic_id or not name:
            messages.error(request, 'Topic and name are required.')
            return render(request, 'core/content/subtopic_form.html', {
                'subjects': subjects,
                'topics': topics,
                'subtopic': subtopic,
                'is_edit': True,
            })
        
        try:
            topic = Topic.objects.get(id=topic_id)
            subtopic.topic = topic
            subtopic.name = name
            subtopic.description = description
            subtopic.order = int(order) if order else 0
            subtopic.is_active = is_active
            subtopic.save()
            messages.success(request, f'Subtopic "{name}" updated successfully.')
            return redirect('manage_subtopics')
        except Topic.DoesNotExist:
            messages.error(request, 'Invalid topic selected.')
        except IntegrityError:
            messages.error(request, 'A subtopic with this name already exists for this topic.')
        except Exception as e:
            messages.error(request, f'Error updating subtopic: {str(e)}')
    
    return render(request, 'core/content/subtopic_form.html', {
        'subjects': subjects,
        'topics': topics,
        'subtopic': subtopic,
        'is_edit': True,
    })


@require_content_manager
def delete_subtopic(request, subtopic_id):
    """Delete a subtopic"""
    from .models import Subtopic
    
    subtopic = get_object_or_404(Subtopic, id=subtopic_id)
    
    if request.method == 'POST':
        name = subtopic.name
        subtopic.delete()
        messages.success(request, f'Subtopic "{name}" deleted successfully.')
    
    return redirect('manage_subtopics')


@require_content_manager
def manage_concepts(request):
    """List all concepts with filters"""
    from .models import Concept, Subtopic, Topic, Subject
    
    concepts = Concept.objects.select_related('subtopic', 'subtopic__topic', 'subtopic__topic__subject').all()
    subjects = Subject.objects.all().order_by('name')
    topics = Topic.objects.select_related('subject').all().order_by('subject__name', 'name')
    subtopics = Subtopic.objects.select_related('topic', 'topic__subject').all().order_by('topic__subject__name', 'topic__name', 'name')
    
    # Filter by subject
    subject_id = request.GET.get('subject')
    if subject_id:
        concepts = concepts.filter(subtopic__topic__subject_id=subject_id)
        topics = topics.filter(subject_id=subject_id)
        subtopics = subtopics.filter(topic__subject_id=subject_id)
    
    # Filter by topic
    topic_id = request.GET.get('topic')
    if topic_id:
        concepts = concepts.filter(subtopic__topic_id=topic_id)
        subtopics = subtopics.filter(topic_id=topic_id)
    
    # Filter by subtopic
    subtopic_id = request.GET.get('subtopic')
    if subtopic_id:
        concepts = concepts.filter(subtopic_id=subtopic_id)
    
    # Filter by active status
    status = request.GET.get('status')
    if status == 'active':
        concepts = concepts.filter(is_active=True)
    elif status == 'inactive':
        concepts = concepts.filter(is_active=False)
    
    # Search by name
    search = request.GET.get('search', '').strip()
    if search:
        concepts = concepts.filter(Q(name__icontains=search) | Q(description__icontains=search))
    
    concepts = concepts.order_by('subtopic__topic__subject__name', 'subtopic__topic__name', 'subtopic__name', 'order', 'name')
    
    return render(request, 'core/content/concepts_list.html', {
        'concepts': concepts,
        'subjects': subjects,
        'topics': topics,
        'subtopics': subtopics,
        'selected_subject': subject_id,
        'selected_topic': topic_id,
        'selected_subtopic': subtopic_id,
        'selected_status': status,
        'search': search,
    })


@require_content_manager
def add_concept(request):
    """Add a new concept"""
    from .models import Concept, Subtopic, Topic, Subject
    
    subjects = Subject.objects.all().order_by('name')
    topics = Topic.objects.select_related('subject').all().order_by('subject__name', 'name')
    subtopics = Subtopic.objects.select_related('topic', 'topic__subject').all().order_by('topic__subject__name', 'topic__name', 'name')
    
    if request.method == 'POST':
        subtopic_id = request.POST.get('subtopic')
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        order = request.POST.get('order', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        if not subtopic_id or not name:
            messages.error(request, 'Subtopic and name are required.')
            return render(request, 'core/content/concept_form.html', {
                'subjects': subjects,
                'topics': topics,
                'subtopics': subtopics,
                'form_data': request.POST,
            })
        
        try:
            subtopic = Subtopic.objects.get(id=subtopic_id)
            Concept.objects.create(
                subtopic=subtopic,
                name=name,
                description=description,
                order=int(order) if order else 0,
                is_active=is_active,
            )
            messages.success(request, f'Concept "{name}" created successfully.')
            return redirect('manage_concepts')
        except Subtopic.DoesNotExist:
            messages.error(request, 'Invalid subtopic selected.')
        except IntegrityError:
            messages.error(request, 'A concept with this name already exists for this subtopic.')
        except Exception as e:
            messages.error(request, f'Error creating concept: {str(e)}')
    
    return render(request, 'core/content/concept_form.html', {
        'subjects': subjects,
        'topics': topics,
        'subtopics': subtopics,
    })


@require_content_manager
def edit_concept(request, concept_id):
    """Edit an existing concept"""
    from .models import Concept, Subtopic, Topic, Subject
    
    concept = get_object_or_404(Concept, id=concept_id)
    subjects = Subject.objects.all().order_by('name')
    topics = Topic.objects.select_related('subject').all().order_by('subject__name', 'name')
    subtopics = Subtopic.objects.select_related('topic', 'topic__subject').all().order_by('topic__subject__name', 'topic__name', 'name')
    
    if request.method == 'POST':
        subtopic_id = request.POST.get('subtopic')
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        order = request.POST.get('order', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        if not subtopic_id or not name:
            messages.error(request, 'Subtopic and name are required.')
            return render(request, 'core/content/concept_form.html', {
                'subjects': subjects,
                'topics': topics,
                'subtopics': subtopics,
                'concept': concept,
                'is_edit': True,
            })
        
        try:
            subtopic = Subtopic.objects.get(id=subtopic_id)
            concept.subtopic = subtopic
            concept.name = name
            concept.description = description
            concept.order = int(order) if order else 0
            concept.is_active = is_active
            concept.save()
            messages.success(request, f'Concept "{name}" updated successfully.')
            return redirect('manage_concepts')
        except Subtopic.DoesNotExist:
            messages.error(request, 'Invalid subtopic selected.')
        except IntegrityError:
            messages.error(request, 'A concept with this name already exists for this subtopic.')
        except Exception as e:
            messages.error(request, f'Error updating concept: {str(e)}')
    
    return render(request, 'core/content/concept_form.html', {
        'subjects': subjects,
        'topics': topics,
        'subtopics': subtopics,
        'concept': concept,
        'is_edit': True,
    })


@require_content_manager
def delete_concept(request, concept_id):
    """Delete a concept"""
    from .models import Concept
    
    concept = get_object_or_404(Concept, id=concept_id)
    
    if request.method == 'POST':
        name = concept.name
        concept.delete()
        messages.success(request, f'Concept "{name}" deleted successfully.')
    
    return redirect('manage_concepts')


@require_content_manager
def manage_video_lessons(request):
    """List all video lessons with filters"""
    from .models import VideoLesson, Subject, Topic, Subtopic, Concept
    
    videos = VideoLesson.objects.select_related('subject', 'topic', 'subtopic', 'concept', 'created_by').all()
    subjects = Subject.objects.all().order_by('name')
    topics = Topic.objects.select_related('subject').all().order_by('subject__name', 'name')
    subtopics = Subtopic.objects.select_related('topic', 'topic__subject').all().order_by('topic__subject__name', 'topic__name', 'name')
    concepts = Concept.objects.select_related('subtopic', 'subtopic__topic', 'subtopic__topic__subject').all()
    
    # Filter by subject
    subject_id = request.GET.get('subject')
    if subject_id:
        videos = videos.filter(subject_id=subject_id)
        topics = topics.filter(subject_id=subject_id)
        subtopics = subtopics.filter(topic__subject_id=subject_id)
        concepts = concepts.filter(subtopic__topic__subject_id=subject_id)
    
    # Filter by topic
    topic_id = request.GET.get('topic')
    if topic_id:
        videos = videos.filter(topic_id=topic_id)
        subtopics = subtopics.filter(topic_id=topic_id)
        concepts = concepts.filter(subtopic__topic_id=topic_id)
    
    # Filter by subtopic
    subtopic_id = request.GET.get('subtopic')
    if subtopic_id:
        videos = videos.filter(subtopic_id=subtopic_id)
        concepts = concepts.filter(subtopic_id=subtopic_id)
    
    # Filter by concept
    concept_id = request.GET.get('concept')
    if concept_id:
        videos = videos.filter(concept_id=concept_id)
    
    # Filter by active status
    status = request.GET.get('status')
    if status == 'active':
        videos = videos.filter(is_active=True)
    elif status == 'inactive':
        videos = videos.filter(is_active=False)
    
    # Filter by featured
    featured = request.GET.get('featured')
    if featured == 'yes':
        videos = videos.filter(is_featured=True)
    elif featured == 'no':
        videos = videos.filter(is_featured=False)
    
    # Search by title/description/tags
    search = request.GET.get('search', '').strip()
    if search:
        videos = videos.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search) |
            Q(tags__icontains=search)
        )
    
    videos = videos.order_by('-created_at')
    
    return render(request, 'core/content/video_lessons_list.html', {
        'videos': videos,
        'subjects': subjects,
        'topics': topics,
        'subtopics': subtopics,
        'concepts': concepts,
        'selected_subject': subject_id,
        'selected_topic': topic_id,
        'selected_subtopic': subtopic_id,
        'selected_concept': concept_id,
        'selected_status': status,
        'selected_featured': featured,
        'search': search,
    })


@require_content_manager
def add_video_lesson(request):
    """Add a new video lesson"""
    from .models import VideoLesson, Subject, Topic, Subtopic, Concept
    import json
    
    subjects = Subject.objects.all().order_by('name')
    topics = Topic.objects.select_related('subject').filter(is_active=True).order_by('subject__name', 'order', 'name')
    subtopics = Subtopic.objects.select_related('topic', 'topic__subject').filter(is_active=True).order_by('topic__subject__name', 'topic__name', 'order', 'name')
    concepts = Concept.objects.select_related('subtopic', 'subtopic__topic', 'subtopic__topic__subject').all()
    
    # Build JSON for Alpine.js dynamic filtering
    topics_json = json.dumps([{'id': t.id, 'name': t.name, 'subject_id': t.subject_id} for t in topics])
    subtopics_json = json.dumps([{'id': s.id, 'name': s.name, 'topic_id': s.topic_id} for s in subtopics])
    concepts_json = json.dumps([{'id': c.id, 'name': c.name, 'subtopic_id': c.subtopic_id} for c in concepts])
    
    if request.method == 'POST':
        subject_id = request.POST.get('subject')
        topic_id = request.POST.get('topic') or None
        subtopic_id = request.POST.get('subtopic') or None
        concept_id = request.POST.get('concept') or None
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        youtube_url = request.POST.get('youtube_url', '').strip()
        duration_minutes = request.POST.get('duration_minutes', 0)
        thumbnail_url = request.POST.get('thumbnail_url', '').strip()
        tags = request.POST.get('tags', '').strip()
        order = request.POST.get('order', 0)
        is_active = request.POST.get('is_active') == 'on'
        is_featured = request.POST.get('is_featured') == 'on'
        
        if not subject_id or not title or not youtube_url:
            messages.error(request, 'Subject, title, and YouTube URL are required.')
            return render(request, 'core/content/video_lesson_form.html', {
                'subjects': subjects,
                'topics': topics,
                'subtopics': subtopics,
                'concepts': concepts,
                'topics_json': topics_json,
                'subtopics_json': subtopics_json,
                'concepts_json': concepts_json,
                'form_data': request.POST,
            })
        
        try:
            subject = Subject.objects.get(id=subject_id)
            topic = Topic.objects.get(id=topic_id) if topic_id else None
            subtopic = Subtopic.objects.get(id=subtopic_id) if subtopic_id else None
            concept = Concept.objects.get(id=concept_id) if concept_id else None
            
            VideoLesson.objects.create(
                subject=subject,
                topic=topic,
                subtopic=subtopic,
                concept=concept,
                title=title,
                description=description,
                youtube_url=youtube_url,
                duration_minutes=int(duration_minutes) if duration_minutes else 0,
                thumbnail_url=thumbnail_url,
                tags=tags,
                order=int(order) if order else 0,
                is_active=is_active,
                is_featured=is_featured,
                created_by=request.user,
            )
            messages.success(request, f'Video lesson "{title}" created successfully.')
            return redirect('manage_video_lessons')
        except Subject.DoesNotExist:
            messages.error(request, 'Invalid subject selected.')
        except (Topic.DoesNotExist, Subtopic.DoesNotExist, Concept.DoesNotExist) as e:
            messages.error(request, f'Invalid hierarchy selection: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error creating video lesson: {str(e)}')
    
    return render(request, 'core/content/video_lesson_form.html', {
        'subjects': subjects,
        'topics': topics,
        'subtopics': subtopics,
        'concepts': concepts,
        'topics_json': topics_json,
        'subtopics_json': subtopics_json,
        'concepts_json': concepts_json,
    })


@require_content_manager
def edit_video_lesson(request, video_id):
    """Edit an existing video lesson"""
    from .models import VideoLesson, Subject, Topic, Subtopic, Concept
    import json
    
    video = get_object_or_404(VideoLesson, id=video_id)
    subjects = Subject.objects.all().order_by('name')
    topics = Topic.objects.select_related('subject').filter(is_active=True).order_by('subject__name', 'order', 'name')
    subtopics = Subtopic.objects.select_related('topic', 'topic__subject').filter(is_active=True).order_by('topic__subject__name', 'topic__name', 'order', 'name')
    concepts = Concept.objects.select_related('subtopic', 'subtopic__topic', 'subtopic__topic__subject').all()
    
    # Build JSON for Alpine.js dynamic filtering
    topics_json = json.dumps([{'id': t.id, 'name': t.name, 'subject_id': t.subject_id} for t in topics])
    subtopics_json = json.dumps([{'id': s.id, 'name': s.name, 'topic_id': s.topic_id} for s in subtopics])
    concepts_json = json.dumps([{'id': c.id, 'name': c.name, 'subtopic_id': c.subtopic_id} for c in concepts])
    
    if request.method == 'POST':
        subject_id = request.POST.get('subject')
        topic_id = request.POST.get('topic') or None
        subtopic_id = request.POST.get('subtopic') or None
        concept_id = request.POST.get('concept') or None
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        youtube_url = request.POST.get('youtube_url', '').strip()
        duration_minutes = request.POST.get('duration_minutes', 0)
        thumbnail_url = request.POST.get('thumbnail_url', '').strip()
        tags = request.POST.get('tags', '').strip()
        order = request.POST.get('order', 0)
        is_active = request.POST.get('is_active') == 'on'
        is_featured = request.POST.get('is_featured') == 'on'
        
        if not subject_id or not title or not youtube_url:
            messages.error(request, 'Subject, title, and YouTube URL are required.')
            return render(request, 'core/content/video_lesson_form.html', {
                'subjects': subjects,
                'topics': topics,
                'subtopics': subtopics,
                'concepts': concepts,
                'topics_json': topics_json,
                'subtopics_json': subtopics_json,
                'concepts_json': concepts_json,
                'video_lesson': video,
            })
        
        try:
            subject = Subject.objects.get(id=subject_id)
            topic = Topic.objects.get(id=topic_id) if topic_id else None
            subtopic = Subtopic.objects.get(id=subtopic_id) if subtopic_id else None
            concept = Concept.objects.get(id=concept_id) if concept_id else None
            
            video.subject = subject
            video.topic = topic
            video.subtopic = subtopic
            video.concept = concept
            video.title = title
            video.description = description
            video.youtube_url = youtube_url
            video.duration_minutes = int(duration_minutes) if duration_minutes else 0
            video.thumbnail_url = thumbnail_url
            video.tags = tags
            video.order = int(order) if order else 0
            video.is_active = is_active
            video.is_featured = is_featured
            video.save()
            messages.success(request, f'Video lesson "{title}" updated successfully.')
            return redirect('manage_video_lessons')
        except Subject.DoesNotExist:
            messages.error(request, 'Invalid subject selected.')
        except (Topic.DoesNotExist, Subtopic.DoesNotExist, Concept.DoesNotExist) as e:
            messages.error(request, f'Invalid hierarchy selection: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error updating video lesson: {str(e)}')
    
    return render(request, 'core/content/video_lesson_form.html', {
        'subjects': subjects,
        'topics': topics,
        'subtopics': subtopics,
        'concepts': concepts,
        'topics_json': topics_json,
        'subtopics_json': subtopics_json,
        'concepts_json': concepts_json,
        'video_lesson': video,
    })


@require_content_manager
def delete_video_lesson(request, video_id):
    """Delete a video lesson"""
    from .models import VideoLesson
    
    video = get_object_or_404(VideoLesson, id=video_id)
    
    if request.method == 'POST':
        title = video.title
        video.delete()
        messages.success(request, f'Video lesson "{title}" deleted successfully.')
    
    return redirect('manage_video_lessons')