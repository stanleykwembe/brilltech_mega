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
import json
import uuid
import os
import mimetypes
import secrets
from datetime import timedelta
from .models import Subject, Grade, ExamBoard, UserProfile, UploadedDocument, GeneratedAssignment, UsageQuota, ClassGroup, AssignmentShare, PasswordResetToken
from .openai_service import generate_lesson_plan, generate_homework, generate_questions
from .subscription_utils import require_premium, get_user_subscription

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
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid credentials. Please check your username/email and password.')
    return render(request, 'core/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard_view(request):
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
    if request.method == 'POST':
        if 'upload_file' in request.POST:
            # Handle file upload
            from core.models import SubscribedSubject
            title = request.POST.get('title')
            subject_id = request.POST.get('subject')
            grade_id = request.POST.get('grade')
            board_id = request.POST.get('board')
            uploaded_file = request.FILES.get('file')
            
            if all([title, subject_id, grade_id, board_id, uploaded_file]):
                # Validate subject is subscribed
                if not SubscribedSubject.objects.filter(user=request.user, subject_id=subject_id).exists():
                    messages.error(request, 'You can only upload lesson plans for your subscribed subjects.')
                    return redirect('lesson_plans')
                
                document = UploadedDocument(
                    uploaded_by=request.user,
                    title=title,
                    subject_id=subject_id,
                    grade_id=grade_id,
                    board_id=board_id,
                    type='lesson_plan',
                    file=uploaded_file
                )
                document.save()
                messages.success(request, 'Lesson plan uploaded successfully!')
            else:
                messages.error(request, 'Please fill all required fields.')
        
        elif 'generate_ai' in request.POST:
            # Handle AI generation
            try:
                from core.models import SubscribedSubject
                subject_id = request.POST.get('subject')
                
                # Validate subject is subscribed
                if not SubscribedSubject.objects.filter(user=request.user, subject_id=subject_id).exists():
                    messages.error(request, 'You can only generate lesson plans for your subscribed subjects.')
                    return redirect('lesson_plans')
                
                # Check quota before generation
                profile = UserProfile.objects.get(user=request.user)
                quota = UsageQuota.objects.get_or_create(user=request.user)[0]
                
                # Check if user can use AI features
                if not profile.can_use_ai():
                    messages.error(request, 'AI features are not available on your plan. Upgrade to Growth or Premium to use AI generation.')
                    return redirect('lesson_plans')
                
                # Get lesson plan limit for this tier
                lesson_plan_limit = profile.get_lesson_plan_limit_per_subject()
                
                # Get current usage for this subject
                subject_key = str(subject_id)
                current_usage = quota.lesson_plans_used.get(subject_key, 0)
                
                # Check if limit is reached (0 means unlimited)
                if lesson_plan_limit > 0 and current_usage >= lesson_plan_limit:
                    messages.error(request, 
                        f'You have reached your monthly limit of {lesson_plan_limit} lesson plan(s) for this subject. '
                        f'Upgrade your plan to generate more lesson plans.')
                    return redirect('lesson_plans')
                
                subject = Subject.objects.get(id=subject_id)
                grade = Grade.objects.get(id=request.POST.get('grade'))
                board = ExamBoard.objects.get(id=request.POST.get('board'))
                topic = request.POST.get('topic')
                duration = request.POST.get('duration', '60 minutes')
                
                ai_content = generate_lesson_plan(
                    subject.name, f"Grade {grade.number}", 
                    board.abbreviation, topic, duration
                )
                
                # Create document with AI content persisted in database
                document = UploadedDocument(
                    uploaded_by=request.user,
                    title=f"AI Generated: {topic}",
                    subject=subject,
                    grade=grade,
                    board=board,
                    type='lesson_plan',
                    ai_content=ai_content  # Store directly in database
                )
                document.save()
                
                # Update quota usage per subject
                if subject_key not in quota.lesson_plans_used:
                    quota.lesson_plans_used[subject_key] = 0
                quota.lesson_plans_used[subject_key] += 1
                quota.save()
                
                remaining = lesson_plan_limit - (current_usage + 1) if lesson_plan_limit > 0 else 'unlimited'
                messages.success(request, f'Lesson plan generated successfully! Remaining: {remaining}')
            except Exception as e:
                messages.error(request, f'Failed to generate lesson plan: {str(e)}')
    
    # Get user's subscribed subjects
    from core.models import SubscribedSubject
    user_subject_ids = SubscribedSubject.objects.filter(user=request.user).values_list('subject_id', flat=True)
    
    # Filter documents by subscribed subjects only
    documents = UploadedDocument.objects.filter(
        uploaded_by=request.user, 
        type='lesson_plan',
        subject_id__in=user_subject_ids
    ).order_by('-created_at')
    
    # Only show subscribed subjects in the dropdown
    available_subjects = Subject.objects.filter(id__in=user_subject_ids)
    
    # Get quota information for display
    profile = UserProfile.objects.get_or_create(user=request.user)[0]
    quota = UsageQuota.objects.get_or_create(user=request.user)[0]
    lesson_plan_limit = profile.get_lesson_plan_limit_per_subject()
    can_use_ai = profile.can_use_ai()
    
    # Calculate usage per subject
    quota_info = {}
    for subject_id in user_subject_ids:
        subject_key = str(subject_id)
        used = quota.lesson_plans_used.get(subject_key, 0)
        quota_info[subject_id] = {
            'used': used,
            'limit': lesson_plan_limit,
            'remaining': lesson_plan_limit - used if lesson_plan_limit > 0 else 'unlimited'
        }
    
    context = {
        'documents': documents,
        'subjects': available_subjects,
        'grades': Grade.objects.all(),
        'exam_boards': ExamBoard.objects.all(),
        'can_use_ai': can_use_ai,
        'lesson_plan_limit': lesson_plan_limit,
        'quota_info': quota_info,
        'user_profile': profile,
    }
    return render(request, 'core/lesson_plans.html', context)

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
    
    context = {
        'assignments': assignments,
        'uploaded_assignments': uploaded_assignments,
        'documents': uploaded_assignments,  # For backward compatibility with template
        'shared_assignments': shared_assignments,
        'subjects': available_subjects,
        'grades': Grade.objects.all(),
        'exam_boards': ExamBoard.objects.all(),
        'teacher_classes': teacher_classes,
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
    from core.models import SubscribedSubject
    user_subject_ids = SubscribedSubject.objects.filter(user=request.user).values_list('subject_id', flat=True)
    
    # Filter documents by subscribed subjects
    documents = UploadedDocument.objects.filter(
        uploaded_by=request.user,
        subject_id__in=user_subject_ids
    ).order_by('-created_at')
    
    # Only show subscribed subjects in the dropdown
    available_subjects = Subject.objects.filter(id__in=user_subject_ids)
    
    context = {
        'documents': documents,
        'subjects': available_subjects,
        'grades': Grade.objects.all(),
        'exam_boards': ExamBoard.objects.all(),
    }
    return render(request, 'core/documents.html', context)

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
            subject = Subject.objects.get(id=request.POST.get('subject'))
            grade = Grade.objects.get(id=request.POST.get('grade'))
            board = ExamBoard.objects.get(id=request.POST.get('board'))
            topic = request.POST.get('topic')
            question_type = request.POST.get('question_type')
            num_questions = int(request.POST.get('num_questions', 5))
            due_date = request.POST.get('due_date')
            
            ai_content = generate_homework(
                subject.name, f"Grade {grade.number}", 
                board.abbreviation, topic, question_type, num_questions
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
            subject = Subject.objects.get(id=request.POST.get('subject'))
            grade = Grade.objects.get(id=request.POST.get('grade'))
            board = ExamBoard.objects.get(id=request.POST.get('board'))
            topic = request.POST.get('topic')
            question_type = request.POST.get('question_type')
            difficulty = request.POST.get('difficulty', 'medium')
            
            ai_content = generate_questions(
                subject.name, f"Grade {grade.number}", 
                board.abbreviation, topic, question_type, difficulty
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
                max_subjects = profile.get_max_subjects()
                
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
        'max_subjects': profile.get_max_subjects(),
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
                        due_date=due_date
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
                        due_date=due_date
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
    from .models import SubscriptionPlan, UserSubscription, PayFastPayment
    from django.db.models import Q
    
    try:
        user_subscription = UserSubscription.objects.select_related('plan', 'selected_subject').get(user=request.user)
    except UserSubscription.DoesNotExist:
        free_plan = SubscriptionPlan.objects.get(plan_type='free')
        from django.utils import timezone
        from datetime import timedelta
        user_subscription = UserSubscription.objects.create(
            user=request.user,
            plan=free_plan,
            status='active',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=365)
        )
    
    available_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    
    payment_history = PayFastPayment.objects.filter(user=request.user).order_by('-created_at')[:10]
    
    subjects = Subject.objects.all().order_by('name')
    
    context = {
        'subscription': user_subscription,
        'available_plans': available_plans,
        'payment_history': payment_history,
        'subjects': subjects,
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
    messages.success(request, 'Payment received! Your subscription is being activated.')
    return redirect('subscription_dashboard')

def payment_cancelled(request):
    """Redirect after cancelled payment"""
    messages.warning(request, 'Payment was cancelled. You can try again anytime.')
    return redirect('subscription_dashboard')