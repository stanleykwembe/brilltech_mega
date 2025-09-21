from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from .models import Subject, Grade, ExamBoard, UserProfile, UploadedDocument, GeneratedAssignment, UsageQuota

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
    assignments = GeneratedAssignment.objects.filter(teacher=request.user).order_by('-created_at')
    
    context = {
        'assignments': assignments,
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