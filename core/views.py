from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.conf import settings
import json
import uuid
import os
import mimetypes
from .models import Subject, Grade, ExamBoard, UserProfile, UploadedDocument, GeneratedAssignment, UsageQuota
from .openai_service import generate_lesson_plan, generate_homework, generate_questions

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
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
    
    context = {
        'assignments': assignments,
        'uploaded_assignments': uploaded_assignments,
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
def view_document(request, doc_id):
    """View document content (for AI generated content)"""
    document = get_object_or_404(UploadedDocument, id=doc_id, uploaded_by=request.user)
    
    # Get AI content from database
    ai_content = document.ai_content
    
    context = {
        'document': document,
        'ai_content': ai_content
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