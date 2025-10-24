from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.db import IntegrityError
from functools import wraps
import secrets
import os
from datetime import timedelta
from .models import (
    StudentProfile, Grade, ExamBoard, Subject, 
    StudentExamBoard, StudentSubject
)


def student_login_required(view_func):
    """Decorator to ensure user is a student and logged in"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to continue.')
            return redirect('student_login')
        
        # Check if user has a student profile
        if not hasattr(request.user, 'student_profile'):
            messages.error(request, 'Access denied. This area is for students only.')
            return redirect('student_login')
        
        # Check if onboarding is completed
        if not request.user.student_profile.onboarding_completed:
            if request.path != reverse('student_onboarding'):
                messages.info(request, 'Please complete your profile setup.')
                return redirect('student_onboarding')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def student_register(request):
    """Student registration view"""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        parent_email = request.POST.get('parent_email', '').strip()
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        # Validation
        if not all([username, email, password, password_confirm]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'core/student/register.html')
        
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'core/student/register.html')
        
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'core/student/register.html')
        
        # Check if username or email already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
            return render(request, 'core/student/register.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return render(request, 'core/student/register.html')
        
        try:
            # Create user (inactive until email verified)
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                is_active=False
            )
            
            # Generate verification token
            verification_token = secrets.token_urlsafe(32)
            
            # Create student profile
            student_profile = StudentProfile.objects.create(
                user=user,
                parent_email=parent_email,
                email_verified=False,
                verification_token=verification_token,
                verification_token_created=timezone.now()
            )
            
            # Send verification email
            verification_path = reverse('student_verify_email', kwargs={'token': verification_token})
            
            replit_domain = os.environ.get('REPLIT_DEV_DOMAIN')
            if replit_domain:
                verification_url = f"https://{replit_domain}{verification_path}"
            else:
                verification_url = request.build_absolute_uri(verification_path)
            
            send_mail(
                subject='Welcome to EduTech - Verify Your Email',
                message=f'''Hi {username},

Welcome to EduTech! We're excited to have you join our learning platform.

Please click the link below to verify your email address and activate your account:

{verification_url}

This link will expire in 24 hours.

If you have any questions, feel free to reach out to our support team.

Best regards,
EduTech Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            
            # Also notify parent if parent email provided
            if parent_email:
                send_mail(
                    subject='Your Child Joined EduTech',
                    message=f'''Hello,

Your child ({username}) has created an account on EduTech, an educational platform designed to help students learn and prepare for exams.

Student email: {email}

You can monitor their progress and we'll keep you updated on their learning journey.

If you have any questions or concerns, please contact us.

Best regards,
EduTech Team''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[parent_email],
                    fail_silently=True,
                )
            
            messages.success(request, 'Registration successful! Please check your email to verify your account.')
            return redirect('student_login')
            
        except IntegrityError as e:
            messages.error(request, 'An error occurred during registration. Please try again.')
            return render(request, 'core/student/register.html')
    
    return render(request, 'core/student/register.html')


def student_login(request):
    """Student login view"""
    if request.method == 'POST':
        username_or_email = request.POST.get('username', '').strip()
        password = request.POST.get('password')
        
        # Determine if input is email or username
        username = username_or_email
        if '@' in username_or_email:
            try:
                user_by_email = User.objects.get(email=username_or_email)
                username = user_by_email.username
            except User.DoesNotExist:
                username = username_or_email
        
        # Check if user exists and has student profile
        try:
            existing_user = User.objects.get(username=username)
            
            # Check if it's a student account
            if not hasattr(existing_user, 'student_profile'):
                messages.error(request, 'Invalid credentials. Are you a teacher? Please use the teacher login page.')
                return render(request, 'core/student/login.html')
            
            # Check if account is verified
            if not existing_user.is_active:
                messages.error(request, 'Please verify your email address before signing in. Check your inbox for the verification link.')
                return render(request, 'core/student/login.html')
                
        except User.DoesNotExist:
            messages.error(request, 'Invalid credentials.')
            return render(request, 'core/student/login.html')
        
        # Authenticate user
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            
            # Redirect to onboarding if not completed
            if not user.student_profile.onboarding_completed:
                return redirect('student_onboarding')
            
            # Otherwise redirect to student dashboard (to be created later)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('student_dashboard')
        else:
            messages.error(request, 'Invalid credentials.')
    
    return render(request, 'core/student/login.html')


def student_logout(request):
    """Student logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('student_login')


def student_verify_email(request, token):
    """Email verification handler"""
    try:
        student_profile = StudentProfile.objects.get(verification_token=token)
        
        # Check if token is expired (24 hours)
        token_age = timezone.now() - student_profile.verification_token_created
        if token_age > timedelta(hours=24):
            messages.error(request, 'Verification link has expired. Please request a new one.')
            return redirect('student_login')
        
        # Check if already verified
        if student_profile.email_verified:
            messages.info(request, 'Email already verified. Please log in.')
            return redirect('student_login')
        
        # Activate user account
        user = student_profile.user
        user.is_active = True
        user.save()
        
        # Mark email as verified
        student_profile.email_verified = True
        student_profile.verification_token = ''
        student_profile.save()
        
        # Send welcome email
        send_mail(
            subject='Welcome to EduTech - Get Started!',
            message=f'''Hi {user.username},

Your email has been verified successfully! 🎉

You can now log in and start your learning journey. Here's what you can do:

• Complete your profile setup
• Choose your exam boards and subjects
• Access study materials and practice quizzes
• Track your progress

Ready to get started? Log in now: {request.build_absolute_uri(reverse('student_login'))}

Happy learning!

Best regards,
EduTech Team''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
        
        messages.success(request, 'Email verified successfully! You can now log in.')
        return redirect('student_login')
        
    except StudentProfile.DoesNotExist:
        messages.error(request, 'Invalid verification link.')
        return redirect('student_login')


@student_login_required
def student_onboarding(request):
    """Multi-step onboarding process for students"""
    student_profile = request.user.student_profile
    
    if request.method == 'POST':
        # Get form data
        grade_id = request.POST.get('grade')
        selected_boards = request.POST.getlist('exam_boards[]')
        
        # Validate grade
        if not grade_id:
            return JsonResponse({'success': False, 'error': 'Please select your grade level.'})
        
        try:
            grade = Grade.objects.get(id=grade_id)
            student_profile.grade = grade
        except Grade.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid grade selected.'})
        
        # Validate exam boards
        board_limit = student_profile.get_exam_board_limit()
        if len(selected_boards) == 0:
            return JsonResponse({'success': False, 'error': 'Please select at least one exam board.'})
        
        if len(selected_boards) > board_limit:
            return JsonResponse({
                'success': False, 
                'error': f'You can select up to {board_limit} exam boards. Upgrade to Pro for more!'
            })
        
        # Clear existing boards and subjects
        StudentExamBoard.objects.filter(student=student_profile).delete()
        StudentSubject.objects.filter(student=student_profile).delete()
        
        # Save selected exam boards
        for board_id in selected_boards:
            try:
                exam_board = ExamBoard.objects.get(id=board_id)
                StudentExamBoard.objects.create(
                    student=student_profile,
                    exam_board=exam_board
                )
            except ExamBoard.DoesNotExist:
                continue
        
        # Process subjects for each board
        subject_limit = student_profile.get_subject_limit_per_board()
        for board_id in selected_boards:
            subject_ids = request.POST.getlist(f'subjects_board_{board_id}[]')
            
            if len(subject_ids) > subject_limit:
                return JsonResponse({
                    'success': False,
                    'error': f'You can select up to {subject_limit} subjects per exam board.'
                })
            
            for subject_id in subject_ids:
                try:
                    subject = Subject.objects.get(id=subject_id)
                    exam_board = ExamBoard.objects.get(id=board_id)
                    StudentSubject.objects.create(
                        student=student_profile,
                        subject=subject,
                        exam_board=exam_board
                    )
                except (Subject.DoesNotExist, ExamBoard.DoesNotExist):
                    continue
        
        # Mark onboarding as completed
        student_profile.onboarding_completed = True
        student_profile.save()
        
        return JsonResponse({'success': True, 'redirect': reverse('student_dashboard')})
    
    # GET request - show onboarding form
    grades = Grade.objects.all().order_by('number')
    exam_boards = ExamBoard.objects.all().order_by('name_full')
    subjects = Subject.objects.all().order_by('name')
    
    context = {
        'student_profile': student_profile,
        'grades': grades,
        'exam_boards': exam_boards,
        'subjects': subjects,
        'board_limit': student_profile.get_exam_board_limit(),
        'subject_limit': student_profile.get_subject_limit_per_board(),
    }
    
    return render(request, 'core/student/onboarding.html', context)


@student_login_required
def student_dashboard(request):
    """Student dashboard - placeholder for now"""
    student_profile = request.user.student_profile
    
    # Get student's exam boards and subjects
    student_boards = StudentExamBoard.objects.filter(student=student_profile).select_related('exam_board')
    student_subjects = StudentSubject.objects.filter(student=student_profile).select_related('subject', 'exam_board')
    
    context = {
        'student_profile': student_profile,
        'student_boards': student_boards,
        'student_subjects': student_subjects,
    }
    
    return render(request, 'core/student/dashboard.html', context)
