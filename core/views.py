from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
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
from .models import Subject, Grade, ExamBoard, UserProfile, UploadedDocument, GeneratedAssignment, UsageQuota, ClassGroup, AssignmentShare
from .openai_service import generate_lesson_plan, generate_homework, generate_questions

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(request, 'Please verify your email address before signing in.')
                return render(request, 'core/login.html')
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
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
            title = request.POST.get('title')
            subject_id = request.POST.get('subject')
            grade_id = request.POST.get('grade')
            board_id = request.POST.get('board')
            uploaded_file = request.FILES.get('file')
            
            if all([title, subject_id, grade_id, board_id, uploaded_file]):
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
                subject = Subject.objects.get(id=request.POST.get('subject'))
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
                
                # Update quota usage
                quota, created = UsageQuota.objects.get_or_create(user=request.user)
                if 'lesson_plans' not in quota.lesson_plans_used:
                    quota.lesson_plans_used['lesson_plans'] = 0
                quota.lesson_plans_used['lesson_plans'] += 1
                quota.save()
                
                messages.success(request, 'Lesson plan generated successfully!')
            except Exception as e:
                messages.error(request, f'Failed to generate lesson plan: {str(e)}')
    
    documents = UploadedDocument.objects.filter(
        uploaded_by=request.user, 
        type='lesson_plan'
    ).order_by('-created_at')
    
    context = {
        'documents': documents,
        'subjects': Subject.objects.all(),
        'grades': Grade.objects.all(),
        'exam_boards': ExamBoard.objects.all(),
    }
    return render(request, 'core/lesson_plans.html', context)

@login_required
def assignments_view(request):
    if request.method == 'POST' and 'upload_file' in request.POST:
        # Handle file upload for assignments
        title = request.POST.get('title')
        subject_id = request.POST.get('subject')
        grade_id = request.POST.get('grade')
        board_id = request.POST.get('board')
        uploaded_file = request.FILES.get('file')
        
        if all([title, subject_id, grade_id, board_id, uploaded_file]):
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
    
    assignments = GeneratedAssignment.objects.filter(teacher=request.user).order_by('-created_at')
    uploaded_assignments = UploadedDocument.objects.filter(
        uploaded_by=request.user,
        type='homework'
    ).order_by('-created_at')
    
    # Get shared assignments for the shared assignments tab
    shared_assignments = AssignmentShare.objects.filter(
        teacher=request.user
    ).select_related(
        'class_group', 'generated_assignment', 'uploaded_document'
    ).order_by('-shared_at')
    
    context = {
        'assignments': assignments,
        'uploaded_assignments': uploaded_assignments,
        'documents': uploaded_assignments,  # For backward compatibility with template
        'shared_assignments': shared_assignments,
        'subjects': Subject.objects.all(),
        'grades': Grade.objects.all(),
        'exam_boards': ExamBoard.objects.all(),
    }
    return render(request, 'core/assignments.html', context)

@login_required
def questions_view(request):
    context = {
        'subjects': Subject.objects.all(),
        'grades': Grade.objects.all(),
        'exam_boards': ExamBoard.objects.all(),
    }
    return render(request, 'core/questions.html', context)

@login_required
def documents_view(request):
    documents = UploadedDocument.objects.filter(uploaded_by=request.user).order_by('-created_at')
    
    context = {
        'documents': documents,
        'subjects': Subject.objects.all(),
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
    """Teacher signup with email verification"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        # Validation
        if not all([username, email, password, password_confirm, first_name, last_name]):
            messages.error(request, 'All fields are required.')
            return render(request, 'core/signup.html')
        
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'core/signup.html')
        
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'core/signup.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'core/signup.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return render(request, 'core/signup.html')
        
        try:
            # Create user (inactive until email verified)
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=False  # Deactivate until email verification
            )
            
            # Create profile with verification token
            verification_token = secrets.token_urlsafe(50)
            profile = UserProfile.objects.create(
                user=user,
                role='teacher',
                verification_token=verification_token,
                verification_token_created=timezone.now()
            )
            
            # Send verification email
            verification_url = request.build_absolute_uri(
                reverse('verify_email', kwargs={'token': verification_token})
            )
            
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
            
            messages.success(request, f'Account created! Please check your email ({email}) and click the verification link to activate your account.')
            return redirect('login')
            
        except Exception as e:
            messages.error(request, f'Error creating account: {str(e)}')
            return render(request, 'core/signup.html')
    
    return render(request, 'core/signup.html')

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
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
        else:
            return HttpResponse('File not found.', status=404)
            
    except AssignmentShare.DoesNotExist:
        return HttpResponse('Share not found.', status=404)