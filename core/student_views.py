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
    StudentExamBoard, StudentSubject, StudentQuiz,
    InteractiveQuestion, StudentQuizAttempt, StudentQuizQuota,
    StudentProgress, Note, Flashcard, ExamPaper
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
    """Enhanced student dashboard with stats and activity"""
    student_profile = request.user.student_profile
    
    # Get student's exam boards and subjects
    student_boards = StudentExamBoard.objects.filter(student=student_profile).select_related('exam_board')
    student_subjects = StudentSubject.objects.filter(student=student_profile).select_related('subject', 'exam_board')
    
    # Calculate statistics
    total_quizzes = StudentQuizAttempt.objects.filter(
        student=student_profile,
        completed_at__isnull=False
    ).count()
    
    # Calculate average score across all quiz attempts
    completed_attempts = StudentQuizAttempt.objects.filter(
        student=student_profile,
        completed_at__isnull=False
    )
    avg_score = 0
    if completed_attempts.exists():
        total_percentage = sum(a.percentage for a in completed_attempts if a.percentage)
        avg_score = total_percentage / completed_attempts.count()
    
    # Count notes viewed
    notes_viewed_count = StudentProgress.objects.filter(
        student=student_profile,
        notes_viewed=True
    ).count()
    
    # Count active subjects
    active_subjects = student_subjects.count()
    
    # Get recent quiz attempts (last 5)
    recent_attempts = StudentQuizAttempt.objects.filter(
        student=student_profile,
        completed_at__isnull=False
    ).select_related('quiz', 'quiz__subject').order_by('-completed_at')[:5]
    
    # Get progress by subject for chart
    subject_progress = []
    for student_subject in student_subjects:
        progress_records = StudentProgress.objects.filter(
            student=student_profile,
            subject=student_subject.subject
        )
        
        if progress_records.exists():
            avg_subject_score = sum(p.average_score for p in progress_records) / progress_records.count()
            subject_progress.append({
                'subject': student_subject.subject.name,
                'score': round(float(avg_subject_score), 1)
            })
    
    context = {
        'student_profile': student_profile,
        'student_boards': student_boards,
        'student_subjects': student_subjects,
        'total_quizzes': total_quizzes,
        'avg_score': round(avg_score, 1),
        'notes_viewed_count': notes_viewed_count,
        'active_subjects': active_subjects,
        'recent_attempts': recent_attempts,
        'subject_progress': subject_progress,
    }
    
    return render(request, 'core/student/dashboard.html', context)


@student_login_required
def student_quizzes_list(request):
    """Browse available quizzes filtered by student's selected subjects"""
    student_profile = request.user.student_profile
    
    # Get student's selected subjects
    student_subjects = StudentSubject.objects.filter(student=student_profile).select_related('subject', 'exam_board')
    subject_ids = student_subjects.values_list('subject_id', flat=True)
    exam_board_ids = student_subjects.values_list('exam_board_id', flat=True)
    
    # Get quizzes matching student's subjects and exam boards
    quizzes = StudentQuiz.objects.filter(
        subject_id__in=subject_ids,
        exam_board_id__in=exam_board_ids,
        grade=student_profile.grade
    ).select_related('subject', 'exam_board', 'grade').prefetch_related('questions')
    
    # Apply filters
    subject_filter = request.GET.get('subject')
    difficulty_filter = request.GET.get('difficulty')
    length_filter = request.GET.get('length')
    
    if subject_filter:
        quizzes = quizzes.filter(subject_id=subject_filter)
    if difficulty_filter:
        quizzes = quizzes.filter(difficulty=difficulty_filter)
    if length_filter:
        quizzes = quizzes.filter(length=length_filter)
    
    # Get attempt counts for each quiz
    quiz_attempts = {}
    for quiz in quizzes:
        attempt_count = StudentQuizAttempt.objects.filter(
            student=student_profile,
            quiz=quiz
        ).count()
        quiz_attempts[quiz.id] = attempt_count
    
    context = {
        'student_profile': student_profile,
        'quizzes': quizzes,
        'quiz_attempts': quiz_attempts,
        'student_subjects': student_subjects,
        'selected_subject': subject_filter,
        'selected_difficulty': difficulty_filter,
        'selected_length': length_filter,
    }
    
    return render(request, 'core/student/quizzes/list.html', context)


@student_login_required
def student_quiz_start(request, quiz_id):
    """Start quiz with preferences form"""
    student_profile = request.user.student_profile
    
    try:
        quiz = StudentQuiz.objects.get(id=quiz_id)
    except StudentQuiz.DoesNotExist:
        messages.error(request, 'Quiz not found.')
        return redirect('student_quizzes_list')
    
    # Check if student has this subject
    has_subject = StudentSubject.objects.filter(
        student=student_profile,
        subject=quiz.subject,
        exam_board=quiz.exam_board
    ).exists()
    
    if not has_subject:
        messages.error(request, 'You do not have access to this quiz. Please select this subject first.')
        return redirect('student_quizzes_list')
    
    # Check quota for free users
    is_pro = student_profile.subscription == 'pro'
    
    if not is_pro and quiz.is_pro_content:
        messages.warning(request, 'This is PRO content. Upgrade your subscription to access it.')
        return redirect('student_quizzes_list')
    
    # Get or create quota tracker
    quota, created = StudentQuizQuota.objects.get_or_create(
        student=student_profile,
        subject=quiz.subject,
        topic=quiz.topic
    )
    
    # Check if student can attempt this quiz
    can_attempt = quota.can_attempt_quiz(quiz, is_pro)
    
    if not can_attempt:
        messages.warning(request, f'You have reached your free quiz limit for {quiz.topic}. Upgrade to PRO for unlimited access or retry your previous quizzes.')
        return redirect('student_quizzes_list')
    
    # Get previous attempts
    previous_attempts = StudentQuizAttempt.objects.filter(
        student=student_profile,
        quiz=quiz
    ).order_by('-started_at')[:5]
    
    context = {
        'student_profile': student_profile,
        'quiz': quiz,
        'previous_attempts': previous_attempts,
        'is_pro': is_pro,
        'quota': quota,
    }
    
    return render(request, 'core/student/quizzes/start.html', context)


@student_login_required
def student_quiz_take(request, quiz_id):
    """Interactive quiz interface"""
    student_profile = request.user.student_profile
    
    try:
        quiz = StudentQuiz.objects.get(id=quiz_id)
    except StudentQuiz.DoesNotExist:
        messages.error(request, 'Quiz not found.')
        return redirect('student_quizzes_list')
    
    # Get quiz preferences from POST
    is_timed = request.POST.get('is_timed') == 'on'
    time_limit = int(request.POST.get('time_limit', 30)) if is_timed else None
    show_instant_feedback = request.POST.get('show_instant_feedback') == 'on'
    
    # Create quiz attempt
    attempt = StudentQuizAttempt.objects.create(
        student=student_profile,
        quiz=quiz,
        is_timed=is_timed,
        time_limit_minutes=time_limit,
        show_instant_feedback=show_instant_feedback
    )
    
    # Get all questions for this quiz
    questions = list(quiz.questions.all().order_by('?'))  # Randomize order
    
    # Store questions in session for this attempt
    request.session[f'quiz_attempt_{attempt.id}_questions'] = [q.id for q in questions]
    
    context = {
        'student_profile': student_profile,
        'quiz': quiz,
        'attempt': attempt,
        'questions': questions,
        'total_questions': len(questions),
    }
    
    return render(request, 'core/student/quizzes/take.html', context)


@student_login_required
def student_quiz_submit(request):
    """Process quiz answers and calculate score"""
    if request.method != 'POST':
        return redirect('student_quizzes_list')
    
    student_profile = request.user.student_profile
    attempt_id = request.POST.get('attempt_id')
    
    try:
        attempt = StudentQuizAttempt.objects.get(id=attempt_id, student=student_profile)
    except StudentQuizAttempt.DoesNotExist:
        messages.error(request, 'Quiz attempt not found.')
        return redirect('student_quizzes_list')
    
    # Check if already completed
    if attempt.completed_at:
        messages.info(request, 'This quiz has already been submitted.')
        return redirect('student_quiz_results', attempt_id=attempt.id)
    
    # Get questions from session
    question_ids = request.session.get(f'quiz_attempt_{attempt.id}_questions', [])
    questions = InteractiveQuestion.objects.filter(id__in=question_ids)
    
    # Process answers
    answers = {}
    score = 0
    total_points = 0
    
    for question in questions:
        question_key = f'question_{question.id}'
        student_answer = request.POST.get(question_key, '')
        
        total_points += question.points
        
        # Check if answer is correct based on question type
        is_correct = False
        
        if question.question_type == 'mcq':
            is_correct = student_answer == question.correct_answer
        elif question.question_type == 'true_false':
            is_correct = student_answer.lower() == question.correct_answer.lower()
        elif question.question_type == 'fill_blank':
            is_correct = student_answer.strip().lower() == question.correct_answer.strip().lower()
        elif question.question_type == 'matching':
            # For matching, student answer should be JSON
            import json
            try:
                student_pairs = json.loads(student_answer)
                correct_pairs = question.matching_pairs
                is_correct = student_pairs == correct_pairs
            except:
                is_correct = False
        elif question.question_type == 'essay':
            # Essays require manual grading
            is_correct = None
        
        if is_correct:
            score += question.points
        
        answers[str(question.id)] = {
            'answer': student_answer,
            'is_correct': is_correct,
            'points_earned': question.points if is_correct else 0
        }
    
    # Calculate percentage
    percentage = (score / total_points * 100) if total_points > 0 else 0
    
    # Save results
    attempt.answers = answers
    attempt.score = score
    attempt.percentage = round(percentage, 2)
    attempt.completed_at = timezone.now()
    attempt.save()
    
    # Update quota
    quota, created = StudentQuizQuota.objects.get_or_create(
        student=student_profile,
        subject=attempt.quiz.subject,
        topic=attempt.quiz.topic
    )
    
    if attempt.quiz not in quota.quizzes_completed.all():
        quota.quizzes_completed.add(attempt.quiz)
    quota.attempt_count += 1
    quota.save()
    
    # Update progress
    progress, created = StudentProgress.objects.get_or_create(
        student=student_profile,
        subject=attempt.quiz.subject,
        topic=attempt.quiz.topic
    )
    
    progress.quizzes_attempted += 1
    if percentage >= 70:  # Pass threshold
        progress.quizzes_passed += 1
    
    # Update average score
    all_attempts = StudentQuizAttempt.objects.filter(
        student=student_profile,
        quiz__subject=attempt.quiz.subject,
        quiz__topic=attempt.quiz.topic,
        completed_at__isnull=False
    )
    
    total_percentage = sum(a.percentage for a in all_attempts if a.percentage)
    progress.average_score = total_percentage / all_attempts.count() if all_attempts.count() > 0 else 0
    progress.save()
    
    # Clean up session
    if f'quiz_attempt_{attempt.id}_questions' in request.session:
        del request.session[f'quiz_attempt_{attempt.id}_questions']
    
    messages.success(request, f'Quiz submitted! You scored {percentage:.1f}%')
    return redirect('student_quiz_results', attempt_id=attempt.id)


@student_login_required
def student_quiz_results(request, attempt_id):
    """Show quiz results with correct answers and explanations"""
    student_profile = request.user.student_profile
    
    try:
        attempt = StudentQuizAttempt.objects.get(id=attempt_id, student=student_profile)
    except StudentQuizAttempt.DoesNotExist:
        messages.error(request, 'Quiz attempt not found.')
        return redirect('student_quizzes_list')
    
    # Get questions with student answers
    question_results = []
    
    for question_id, answer_data in attempt.answers.items():
        try:
            question = InteractiveQuestion.objects.get(id=int(question_id))
            question_results.append({
                'question': question,
                'student_answer': answer_data['answer'],
                'is_correct': answer_data['is_correct'],
                'points_earned': answer_data['points_earned']
            })
        except InteractiveQuestion.DoesNotExist:
            continue
    
    context = {
        'student_profile': student_profile,
        'attempt': attempt,
        'quiz': attempt.quiz,
        'question_results': question_results,
    }
    
    return render(request, 'core/student/quizzes/results.html', context)


@student_login_required
def student_quiz_history(request):
    """View all past quiz attempts"""
    student_profile = request.user.student_profile
    
    # Get all completed attempts
    attempts = StudentQuizAttempt.objects.filter(
        student=student_profile,
        completed_at__isnull=False
    ).select_related('quiz', 'quiz__subject').order_by('-completed_at')
    
    # Apply filters
    subject_filter = request.GET.get('subject')
    if subject_filter:
        attempts = attempts.filter(quiz__subject_id=subject_filter)
    
    # Get student subjects for filter
    student_subjects = StudentSubject.objects.filter(
        student=student_profile
    ).select_related('subject').values('subject_id', 'subject__name').distinct()
    
    context = {
        'student_profile': student_profile,
        'attempts': attempts,
        'student_subjects': student_subjects,
        'selected_subject': subject_filter,
    }
    
    return render(request, 'core/student/quizzes/history.html', context)


@student_login_required
def student_notes(request):
    """Browse all notes for student's subjects"""
    student_profile = request.user.student_profile
    
    # Get student's selected subjects
    student_subjects = StudentSubject.objects.filter(student=student_profile).select_related('subject', 'exam_board')
    subject_ids = student_subjects.values_list('subject_id', flat=True)
    exam_board_ids = student_subjects.values_list('exam_board_id', flat=True)
    
    # Get notes matching student's subjects and exam boards
    notes = Note.objects.filter(
        subject_id__in=subject_ids,
        exam_board_id__in=exam_board_ids,
        grade=student_profile.grade
    ).select_related('subject', 'exam_board', 'grade')
    
    # Apply filters
    subject_filter = request.GET.get('subject')
    topic_filter = request.GET.get('topic')
    
    if subject_filter:
        notes = notes.filter(subject_id=subject_filter)
    if topic_filter:
        notes = notes.filter(topic__icontains=topic_filter)
    
    # Get unique topics for filter
    topics = Note.objects.filter(
        subject_id__in=subject_ids,
        exam_board_id__in=exam_board_ids,
        grade=student_profile.grade
    ).values_list('topic', flat=True).distinct()
    
    context = {
        'student_profile': student_profile,
        'notes': notes,
        'student_subjects': student_subjects,
        'topics': topics,
        'selected_subject': subject_filter,
        'selected_topic': topic_filter,
    }
    
    return render(request, 'core/student/notes/list.html', context)


@student_login_required
def student_note_view(request, note_id):
    """View individual note with full and summary versions"""
    student_profile = request.user.student_profile
    
    try:
        note = Note.objects.select_related('subject', 'exam_board', 'grade').get(id=note_id)
    except Note.DoesNotExist:
        messages.error(request, 'Note not found.')
        return redirect('student_notes')
    
    # Check if student has access to this note's subject
    has_access = StudentSubject.objects.filter(
        student=student_profile,
        subject=note.subject,
        exam_board=note.exam_board
    ).exists()
    
    if not has_access:
        messages.error(request, 'You do not have access to this note.')
        return redirect('student_notes')
    
    # Update progress - mark note as viewed
    progress, created = StudentProgress.objects.get_or_create(
        student=student_profile,
        subject=note.subject,
        topic=note.topic
    )
    progress.notes_viewed = True
    progress.save()
    
    context = {
        'student_profile': student_profile,
        'note': note,
    }
    
    return render(request, 'core/student/notes/view.html', context)


@student_login_required
def student_flashcards(request):
    """Browse flashcards by subject/topic"""
    student_profile = request.user.student_profile
    
    # Get student's selected subjects
    student_subjects = StudentSubject.objects.filter(student=student_profile).select_related('subject', 'exam_board')
    subject_ids = student_subjects.values_list('subject_id', flat=True)
    exam_board_ids = student_subjects.values_list('exam_board_id', flat=True)
    
    # Get flashcards matching student's subjects
    flashcards = Flashcard.objects.filter(
        subject_id__in=subject_ids,
        exam_board_id__in=exam_board_ids,
        grade=student_profile.grade
    ).select_related('subject', 'exam_board', 'grade')
    
    # Apply filters
    subject_filter = request.GET.get('subject')
    topic_filter = request.GET.get('topic')
    
    if subject_filter:
        flashcards = flashcards.filter(subject_id=subject_filter)
    if topic_filter:
        flashcards = flashcards.filter(topic__icontains=topic_filter)
    
    # Group flashcards by subject and topic
    flashcard_groups = {}
    for flashcard in flashcards:
        subject_name = flashcard.subject.name
        if subject_name not in flashcard_groups:
            flashcard_groups[subject_name] = {}
        
        topic = flashcard.topic
        if topic not in flashcard_groups[subject_name]:
            flashcard_groups[subject_name][topic] = []
        
        flashcard_groups[subject_name][topic].append(flashcard)
    
    # Get review progress
    progress_data = {}
    for student_subject in student_subjects:
        topics_progress = StudentProgress.objects.filter(
            student=student_profile,
            subject=student_subject.subject
        )
        for progress in topics_progress:
            key = f"{progress.subject.name}_{progress.topic}"
            progress_data[key] = progress.flashcards_reviewed
    
    context = {
        'student_profile': student_profile,
        'flashcard_groups': flashcard_groups,
        'student_subjects': student_subjects,
        'progress_data': progress_data,
        'selected_subject': subject_filter,
        'selected_topic': topic_filter,
    }
    
    return render(request, 'core/student/flashcards/list.html', context)


@student_login_required
def student_flashcard_study(request, subject_id):
    """Interactive flashcard study mode"""
    student_profile = request.user.student_profile
    
    try:
        subject = Subject.objects.get(id=subject_id)
    except Subject.DoesNotExist:
        messages.error(request, 'Subject not found.')
        return redirect('student_flashcards')
    
    # Check if student has this subject
    student_subject = StudentSubject.objects.filter(
        student=student_profile,
        subject=subject
    ).first()
    
    if not student_subject:
        messages.error(request, 'You do not have access to this subject.')
        return redirect('student_flashcards')
    
    # Get topic filter from query params
    topic_filter = request.GET.get('topic')
    
    # Get flashcards for this subject
    flashcards = Flashcard.objects.filter(
        subject=subject,
        exam_board=student_subject.exam_board,
        grade=student_profile.grade
    )
    
    if topic_filter:
        flashcards = flashcards.filter(topic=topic_filter)
    
    flashcards = list(flashcards.order_by('?'))  # Randomize
    
    if not flashcards:
        messages.warning(request, 'No flashcards available for this subject.')
        return redirect('student_flashcards')
    
    # Handle AJAX request for marking flashcard as reviewed
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        topic = request.POST.get('topic')
        
        # Update progress
        progress, created = StudentProgress.objects.get_or_create(
            student=student_profile,
            subject=subject,
            topic=topic
        )
        progress.flashcards_reviewed += 1
        progress.save()
        
        return JsonResponse({'success': True, 'flashcards_reviewed': progress.flashcards_reviewed})
    
    context = {
        'student_profile': student_profile,
        'subject': subject,
        'flashcards': flashcards,
        'topic_filter': topic_filter,
        'total_cards': len(flashcards),
    }
    
    return render(request, 'core/student/flashcards/study.html', context)


@student_login_required
def student_exam_papers(request):
    """Browse exam papers with filtering"""
    student_profile = request.user.student_profile
    
    # Get student's selected subjects
    student_subjects = StudentSubject.objects.filter(student=student_profile).select_related('subject', 'exam_board')
    subject_ids = student_subjects.values_list('subject_id', flat=True)
    exam_board_ids = student_subjects.values_list('exam_board_id', flat=True)
    
    # Get exam papers matching student's subjects
    exam_papers = ExamPaper.objects.filter(
        subject_id__in=subject_ids,
        exam_board_id__in=exam_board_ids,
        grade=student_profile.grade
    ).select_related('subject', 'exam_board', 'grade')
    
    # Apply filters
    subject_filter = request.GET.get('subject')
    year_filter = request.GET.get('year')
    board_filter = request.GET.get('board')
    
    if subject_filter:
        exam_papers = exam_papers.filter(subject_id=subject_filter)
    if year_filter:
        exam_papers = exam_papers.filter(year=year_filter)
    if board_filter:
        exam_papers = exam_papers.filter(exam_board_id=board_filter)
    
    # Get unique years for filter
    years = ExamPaper.objects.filter(
        subject_id__in=subject_ids,
        exam_board_id__in=exam_board_ids,
        grade=student_profile.grade
    ).values_list('year', flat=True).distinct().order_by('-year')
    
    # Check if user is pro
    is_pro = student_profile.subscription == 'pro'
    
    context = {
        'student_profile': student_profile,
        'exam_papers': exam_papers,
        'student_subjects': student_subjects,
        'years': years,
        'student_boards': StudentExamBoard.objects.filter(student=student_profile).select_related('exam_board'),
        'selected_subject': subject_filter,
        'selected_year': year_filter,
        'selected_board': board_filter,
        'is_pro': is_pro,
    }
    
    return render(request, 'core/student/exam_papers/list.html', context)


@student_login_required
def student_exam_paper_view(request, paper_id):
    """View exam paper with download option"""
    student_profile = request.user.student_profile
    
    try:
        exam_paper = ExamPaper.objects.select_related('subject', 'exam_board', 'grade').get(id=paper_id)
    except ExamPaper.DoesNotExist:
        messages.error(request, 'Exam paper not found.')
        return redirect('student_exam_papers')
    
    # Check if student has access
    has_access = StudentSubject.objects.filter(
        student=student_profile,
        subject=exam_paper.subject,
        exam_board=exam_paper.exam_board
    ).exists()
    
    if not has_access:
        messages.error(request, 'You do not have access to this exam paper.')
        return redirect('student_exam_papers')
    
    # Check if PRO content
    is_pro = student_profile.subscription == 'pro'
    if exam_paper.is_pro_content and not is_pro:
        messages.warning(request, 'This is PRO content. Upgrade to access it.')
        return redirect('student_exam_papers')
    
    context = {
        'student_profile': student_profile,
        'exam_paper': exam_paper,
        'is_pro': is_pro,
    }
    
    return render(request, 'core/student/exam_papers/view.html', context)


@student_login_required
def student_subscription(request):
    """Show subscription details and upgrade/downgrade options"""
    student_profile = request.user.student_profile
    is_pro = student_profile.subscription == 'pro'
    
    # Get current exam board count
    current_board_count = StudentExamBoard.objects.filter(student=student_profile).count()
    
    context = {
        'student_profile': student_profile,
        'is_pro': is_pro,
        'current_board_count': current_board_count,
        'board_limit': student_profile.get_exam_board_limit(),
    }
    
    return render(request, 'core/student/subscription.html', context)


@student_login_required
def student_upgrade_to_pro(request):
    """Initiate PayFast payment for Pro subscription"""
    from .payfast_service import PayFastService
    import logging
    
    logger = logging.getLogger(__name__)
    student_profile = request.user.student_profile
    
    # Check if already Pro
    if student_profile.subscription == 'pro':
        messages.info(request, 'You are already a Pro member!')
        return redirect('student_subscription')
    
    # Generate PayFast payment form data for student subscription
    payment_data = {
        'merchant_id': settings.PAYFAST_MERCHANT_ID,
        'merchant_key': settings.PAYFAST_MERCHANT_KEY,
        'return_url': f"{settings.SITE_URL}{reverse('student_payfast_return')}",
        'cancel_url': f"{settings.SITE_URL}{reverse('student_payfast_cancel')}",
        'notify_url': f"{settings.SITE_URL}{reverse('student_payfast_notify')}",
        
        'name_first': request.user.first_name or request.user.username,
        'name_last': request.user.last_name or '',
        'email_address': request.user.email,
        
        'amount': '100.00',
        'item_name': 'EduTech Pro Subscription',
        'item_description': 'Monthly Pro subscription with unlimited quizzes and 5 exam boards',
        
        'custom_str1': str(request.user.id),
        'custom_str2': 'pro_subscription',
        
        'subscription_type': '1',
        'recurring_amount': '100.00',
        'frequency': '3',
        'cycles': '0',
    }
    
    # Remove empty fields before signature generation
    clean_data = {k: v for k, v in payment_data.items() if str(v).strip()}
    
    # Generate signature
    clean_data['signature'] = PayFastService.generate_signature(clean_data)
    
    logger.info(f'Generated PayFast payment for user {request.user.username}')
    
    context = {
        'student_profile': student_profile,
        'payment_data': clean_data,
        'payfast_url': PayFastService.get_payfast_url(),
    }
    
    return render(request, 'core/student/upgrade.html', context)


from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

@csrf_exempt
def student_payfast_notify(request):
    """Handle PayFast IPN (Instant Payment Notification)"""
    from .payfast_service import PayFastService
    import logging
    
    logger = logging.getLogger(__name__)
    
    if request.method != 'POST':
        return HttpResponse('Invalid request method', status=400)
    
    post_data = request.POST.copy()
    logger.info(f'PayFast IPN received: {post_data}')
    
    # Validate signature
    if not PayFastService.validate_itn_signature(post_data):
        logger.error('PayFast IPN signature validation failed')
        return HttpResponse('Invalid signature', status=400)
    
    # Validate merchant ID
    if not PayFastService.validate_merchant_id(post_data):
        logger.error('PayFast IPN merchant ID validation failed')
        return HttpResponse('Invalid merchant ID', status=400)
    
    # Validate payment amount
    if not PayFastService.validate_payment_amount(post_data, 100.00):
        logger.error('PayFast IPN amount validation failed')
        return HttpResponse('Invalid amount', status=400)
    
    # Verify with PayFast servers
    if not PayFastService.verify_payment_with_payfast(post_data):
        logger.error('PayFast server verification failed')
        return HttpResponse('Server verification failed', status=400)
    
    # Check payment status
    payment_status = post_data.get('payment_status', '')
    if payment_status != 'COMPLETE':
        logger.warning(f'PayFast IPN payment not complete: {payment_status}')
        return HttpResponse('Payment not complete', status=200)
    
    # Get user from custom field
    try:
        user_id = int(post_data.get('custom_str1', 0))
        user = User.objects.get(id=user_id)
        student_profile = user.student_profile
    except (ValueError, User.DoesNotExist, AttributeError):
        logger.error(f'PayFast IPN user not found: {post_data.get("custom_str1")}')
        return HttpResponse('User not found', status=400)
    
    # Update subscription to Pro
    old_subscription = student_profile.subscription
    student_profile.subscription = 'pro'
    student_profile.save()
    
    logger.info(f'User {user.username} upgraded to Pro via PayFast')
    
    # Clear quiz quotas (Pro has unlimited)
    StudentQuizQuota.objects.filter(student=student_profile).delete()
    
    # Send confirmation email
    try:
        send_mail(
            subject='Welcome to EduTech Pro! 🎉',
            message=f'''Hi {user.username},

Congratulations! Your payment was successful and you are now an EduTech Pro member!

Here's what you now have access to:

✅ Unlimited quizzes on all topics
✅ Select up to 5 exam boards (previously 2)
✅ Access to all study materials
✅ Early access to new features
✅ Priority support

You can now:
- Take unlimited quizzes on any topic
- Add more exam boards to your profile (up to 5 total)
- Access all Pro-exclusive content

Thank you for upgrading! We're excited to support your learning journey.

Best regards,
EduTech Team

P.S. Your subscription will automatically renew monthly at R100. You can cancel anytime from your subscription page.''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
        
        # Also notify parent if provided
        if student_profile.parent_email:
            send_mail(
                subject='Your Child Upgraded to EduTech Pro',
                message=f'''Hello,

Your child ({user.username}) has upgraded to EduTech Pro subscription.

Subscription: EduTech Pro
Price: R100/month (auto-renewal)

They now have access to:
- Unlimited quizzes
- 5 exam boards
- All study materials
- Priority support

If you have any questions about this subscription, please contact us.

Best regards,
EduTech Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[student_profile.parent_email],
                fail_silently=True,
            )
    except Exception as e:
        logger.error(f'Failed to send Pro upgrade email: {str(e)}')
    
    return HttpResponse('OK', status=200)


@student_login_required
def student_payfast_return(request):
    """Handle user return from PayFast after payment"""
    student_profile = request.user.student_profile
    
    # Check if upgrade was successful
    if student_profile.subscription == 'pro':
        messages.success(request, '🎉 Welcome to Pro! Your upgrade was successful.')
    else:
        messages.info(request, 'Your payment is being processed. You will receive a confirmation email shortly.')
    
    return redirect('student_subscription')


@student_login_required
def student_payfast_cancel(request):
    """Handle payment cancellation"""
    messages.warning(request, 'Payment was cancelled. You can upgrade to Pro anytime!')
    return redirect('student_subscription')


@student_login_required
def student_subscription_cancel(request):
    """Cancel Pro subscription (downgrade to Free)"""
    student_profile = request.user.student_profile
    
    if request.method == 'POST':
        # Check if currently Pro
        if student_profile.subscription != 'pro':
            messages.error(request, 'You are not currently a Pro member.')
            return redirect('student_subscription')
        
        # Downgrade to Free
        student_profile.subscription = 'free'
        student_profile.save()
        
        # Check if they have more than 2 exam boards
        board_count = StudentExamBoard.objects.filter(student=student_profile).count()
        warning_message = ''
        if board_count > 2:
            warning_message = f' You currently have {board_count} exam boards selected. Free accounts are limited to 2 boards. Please update your selections in your onboarding settings.'
        
        # Send confirmation email
        try:
            send_mail(
                subject='EduTech Pro Subscription Cancelled',
                message=f'''Hi {request.user.username},

Your EduTech Pro subscription has been cancelled successfully.

You have been downgraded to the Free plan with the following features:
- 2 exam boards (down from 5)
- 2 different quizzes per topic (down from unlimited)
- All subjects still available

{warning_message}

Your access to Pro features will continue until the end of your current billing period.

We're sad to see you go! If you change your mind, you can upgrade again anytime.

Best regards,
EduTech Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[request.user.email],
                fail_silently=True,
            )
        except Exception as e:
            pass
        
        messages.success(request, f'Your Pro subscription has been cancelled. You are now on the Free plan.{warning_message}')
        return redirect('student_subscription')
    
    # GET request - show confirmation page
    context = {
        'student_profile': student_profile,
    }
    
    return render(request, 'core/student/subscription_cancel_confirm.html', context)
