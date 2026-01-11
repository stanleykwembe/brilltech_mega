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
from django.db.models import Q, Sum
from .models import (
    StudentProfile, Grade, ExamBoard, Subject, 
    StudentExamBoard, StudentSubject, StudentQuiz,
    InteractiveQuestion, StudentQuizAttempt, StudentQuizQuota,
    StudentProgress, Note, Flashcard, ExamPaper,
    VideoLesson, Topic, Subtopic, Concept, StudentTopicProgress
)


def mark_structured_question_with_ai(question_text, model_answer, marking_guide, student_answer, max_marks):
    """Use AI to mark structured/essay questions and provide feedback"""
    import os
    try:
        from openai import OpenAI
        
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return {'marks': 0, 'feedback': 'AI marking unavailable - no API key configured'}
        
        client = OpenAI(api_key=api_key)
        
        prompt = f"""You are an experienced exam marker. Mark the following student answer and provide constructive feedback.

QUESTION:
{question_text}

MODEL ANSWER:
{model_answer}

MARKING CRITERIA:
{marking_guide if marking_guide else 'Use your judgment based on the model answer.'}

STUDENT ANSWER:
{student_answer}

MAXIMUM MARKS: {max_marks}

Please provide:
1. A mark out of {max_marks} (be fair but rigorous)
2. Brief constructive feedback (2-3 sentences max)

Respond in this exact JSON format:
{{"marks": <number>, "feedback": "<feedback text>"}}"""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert exam marker. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.3
        )
        
        import json
        result_text = response.choices[0].message.content.strip()
        
        # Try to parse JSON response
        try:
            result = json.loads(result_text)
            marks = min(max(0, int(result.get('marks', 0))), max_marks)
            feedback = result.get('feedback', 'No feedback provided.')
            return {'marks': marks, 'feedback': feedback}
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract marks from text
            return {'marks': 0, 'feedback': 'AI marking encountered an error. Please review manually.'}
            
    except Exception as e:
        return {'marks': 0, 'feedback': f'AI marking unavailable: {str(e)[:50]}'}


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
    # Set session flag for social login - this tells the adapter to create StudentProfile
    request.session['social_login_type'] = 'student'
    
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
    # Set session flag for social login - this tells the adapter to create StudentProfile
    request.session['social_login_type'] = 'student'
    
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
    from .models import StudentTopicProgress
    
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
    
    # Count notes viewed from StudentTopicProgress
    notes_viewed_count = StudentTopicProgress.objects.filter(
        student=student_profile
    ).aggregate(total=Sum('notes_read_count'))['total'] or 0
    
    # Count videos watched from StudentTopicProgress
    videos_watched_count = StudentTopicProgress.objects.filter(
        student=student_profile
    ).aggregate(total=Sum('videos_watched_count'))['total'] or 0
    
    # Count active subjects
    active_subjects = student_subjects.count()
    
    # Get recent quiz attempts (last 5)
    recent_attempts = StudentQuizAttempt.objects.filter(
        student=student_profile,
        completed_at__isnull=False
    ).select_related('quiz', 'quiz__subject').order_by('-completed_at')[:5]
    
    # Get progress by subject for chart and subject cards
    subject_progress = []
    subjects_with_progress = []
    for student_subject in student_subjects:
        topic_progress = StudentTopicProgress.objects.filter(
            student=student_profile,
            subject=student_subject.subject
        )
        
        # Calculate subject completion percentage
        total_completion = 0
        if topic_progress.exists():
            total_completion = sum(tp.get_completion_percentage() for tp in topic_progress) / topic_progress.count()
        
        # Calculate average quiz score for subject
        subject_attempts = StudentQuizAttempt.objects.filter(
            student=student_profile,
            quiz__subject=student_subject.subject,
            completed_at__isnull=False
        )
        avg_subject_score = 0
        if subject_attempts.exists():
            avg_subject_score = sum(a.percentage for a in subject_attempts if a.percentage) / subject_attempts.count()
        
        subject_data = {
            'student_subject': student_subject,
            'subject': student_subject.subject,
            'exam_board': student_subject.exam_board,
            'completion_percentage': round(total_completion),
            'avg_score': round(avg_subject_score, 1),
            'topics_count': Topic.objects.filter(
                subject=student_subject.subject
            ).count()
        }
        subjects_with_progress.append(subject_data)
        
        if avg_subject_score > 0:
            subject_progress.append({
                'subject': student_subject.subject.name,
                'score': round(float(avg_subject_score), 1)
            })
    
    context = {
        'student_profile': student_profile,
        'student_boards': student_boards,
        'student_subjects': student_subjects,
        'subjects_with_progress': subjects_with_progress,
        'total_quizzes': total_quizzes,
        'avg_score': round(avg_score, 1),
        'notes_viewed_count': notes_viewed_count,
        'videos_watched_count': videos_watched_count,
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
    topic_filter = request.GET.get('topic')
    difficulty_filter = request.GET.get('difficulty')
    length_filter = request.GET.get('length')
    
    if subject_filter:
        quizzes = quizzes.filter(subject_id=subject_filter)
    if topic_filter:
        quizzes = quizzes.filter(topic__icontains=topic_filter)
    if difficulty_filter:
        quizzes = quizzes.filter(difficulty=difficulty_filter)
    if length_filter:
        quizzes = quizzes.filter(length=length_filter)
    
    # Get unique topics for the filter dropdown
    all_topics = StudentQuiz.objects.filter(
        subject_id__in=subject_ids,
        exam_board_id__in=exam_board_ids,
        grade=student_profile.grade
    ).values_list('topic', flat=True).distinct().order_by('topic')
    
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
        'all_topics': all_topics,
        'selected_subject': subject_filter,
        'selected_topic': topic_filter,
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
        points_earned = 0
        ai_feedback = ''
        
        if question.question_type == 'mcq':
            # Use correct_option_index if available, otherwise fall back to correct_answer
            if question.correct_option_index is not None:
                try:
                    is_correct = int(student_answer) == question.correct_option_index
                except (ValueError, TypeError):
                    is_correct = student_answer == str(question.correct_option_index)
            else:
                is_correct = student_answer == question.correct_answer
            points_earned = question.points if is_correct else 0
        elif question.question_type == 'true_false':
            is_correct = student_answer.lower() == question.correct_answer.lower()
            points_earned = question.points if is_correct else 0
        elif question.question_type == 'fill_blank':
            is_correct = student_answer.strip().lower() == question.correct_answer.strip().lower()
            points_earned = question.points if is_correct else 0
        elif question.question_type == 'matching':
            # For matching, student answer should be JSON
            import json
            try:
                student_pairs = json.loads(student_answer)
                correct_pairs = question.matching_pairs
                is_correct = student_pairs == correct_pairs
            except:
                is_correct = False
            points_earned = question.points if is_correct else 0
        elif question.question_type in ['structured', 'essay']:
            # Structured/essay questions - use AI marking if model answer available
            if question.model_answer and student_answer.strip():
                ai_result = mark_structured_question_with_ai(
                    question_text=question.question_text,
                    model_answer=question.model_answer,
                    marking_guide=question.marking_guide,
                    student_answer=student_answer,
                    max_marks=question.max_marks
                )
                points_earned = ai_result.get('marks', 0)
                ai_feedback = ai_result.get('feedback', '')
                is_correct = points_earned >= (question.max_marks * 0.7)  # 70% threshold
            else:
                # No model answer - mark as pending
                is_correct = None
                points_earned = 0
        
        if is_correct:
            score += points_earned
        elif points_earned > 0:
            score += points_earned  # Partial marks for structured
        
        answers[str(question.id)] = {
            'answer': student_answer,
            'is_correct': is_correct,
            'points_earned': points_earned,
            'ai_feedback': ai_feedback,
            'max_marks': question.max_marks if question.question_type in ['structured', 'essay'] else question.points
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
    
    # Also update StudentTopicProgress (for pathway progress tracking)
    try:
        topic_obj = Topic.objects.filter(
            subject=attempt.quiz.subject,
            name__iexact=attempt.quiz.topic
        ).first()
        
        if topic_obj:
            topic_progress, created = StudentTopicProgress.objects.get_or_create(
                student=student_profile,
                subject=attempt.quiz.subject,
                topic=topic_obj
            )
            
            # Determine difficulty and update appropriate counter
            difficulty = getattr(attempt.quiz, 'difficulty', 'medium')
            if difficulty == 'easy':
                topic_progress.quizzes_easy_completed += 1
                if percentage >= 70:
                    topic_progress.quizzes_easy_passed += 1
            elif difficulty == 'hard':
                topic_progress.quizzes_hard_completed += 1
                if percentage >= 70:
                    topic_progress.quizzes_hard_passed += 1
            else:
                topic_progress.quizzes_medium_completed += 1
                if percentage >= 70:
                    topic_progress.quizzes_medium_passed += 1
            
            topic_progress.average_quiz_score = progress.average_score
            topic_progress.save()
    except Exception as e:
        pass  # Don't fail the quiz submission if topic progress update fails
    
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
        notes = notes.filter(topic__name__icontains=topic_filter)
    
    # Get unique topics for filter (topic is a ForeignKey, get names)
    topic_ids = Note.objects.filter(
        subject_id__in=subject_ids,
        exam_board_id__in=exam_board_ids,
        grade=student_profile.grade,
        topic__isnull=False
    ).values_list('topic_id', flat=True).distinct()
    topics = Topic.objects.filter(id__in=topic_ids).values_list('name', flat=True).order_by('name')
    
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
    # Get topic name (note.topic is a ForeignKey, StudentProgress.topic is CharField)
    topic_name = note.topic.name if note.topic else (note.topic_text or 'General')
    progress, created = StudentProgress.objects.get_or_create(
        student=student_profile,
        subject=note.subject,
        topic=topic_name
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
        flashcards = flashcards.filter(topic__name__icontains=topic_filter)
    
    # Get unique topics for filter dropdown
    topic_ids = Flashcard.objects.filter(
        subject_id__in=subject_ids,
        exam_board_id__in=exam_board_ids,
        grade=student_profile.grade,
        topic__isnull=False
    ).values_list('topic_id', flat=True).distinct()
    all_topics = Topic.objects.filter(id__in=topic_ids).values_list('name', flat=True).order_by('name')
    
    # Group flashcards by subject and topic
    flashcard_groups = {}
    for flashcard in flashcards:
        subject_name = flashcard.subject.name
        if subject_name not in flashcard_groups:
            flashcard_groups[subject_name] = {}
        
        # Get topic info - use Topic FK if available, else legacy text
        if flashcard.topic:
            topic_name = flashcard.topic.name
            topic_id = flashcard.topic.id
        else:
            topic_name = flashcard.topic_text or 'General'
            topic_id = None
        
        topic_key = (topic_name, topic_id)
        if topic_key not in flashcard_groups[subject_name]:
            flashcard_groups[subject_name][topic_key] = []
        
        flashcard_groups[subject_name][topic_key].append(flashcard)
    
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
        'all_topics': all_topics,
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
    
    # Get topic filter from query params (support both topic_id and legacy topic name)
    topic_id = request.GET.get('topic_id')
    topic_filter = request.GET.get('topic')
    timed_mode = request.GET.get('timed', 'false') == 'true'
    topic_obj = None
    topic_display_name = None
    
    # Get flashcards for this subject
    flashcards = Flashcard.objects.filter(
        subject=subject,
        exam_board=student_subject.exam_board,
        grade=student_profile.grade
    )
    
    # Filter by topic - support both FK and legacy text field
    if topic_id:
        topic_obj = Topic.objects.filter(id=topic_id).first()
        if topic_obj:
            flashcards = flashcards.filter(topic=topic_obj)
            topic_display_name = topic_obj.name
    elif topic_filter:
        # Legacy text filter for backwards compatibility
        flashcards = flashcards.filter(topic_text=topic_filter)
        topic_display_name = topic_filter
    
    flashcards = list(flashcards.order_by('?'))  # Randomize
    
    if not flashcards:
        return redirect('student_flashcards')
    
    # Handle AJAX request for marking flashcard as reviewed
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from .models import StudentTopicProgress
        
        flashcard_id = request.POST.get('flashcard_id')
        
        # Get the flashcard to find its topic
        flashcard = Flashcard.objects.filter(id=flashcard_id).first()
        if flashcard and flashcard.topic:
            # Update StudentTopicProgress
            progress, created = StudentTopicProgress.objects.get_or_create(
                student=student_profile,
                subject=subject,
                topic=flashcard.topic
            )
            progress.flashcards_reviewed += 1
            progress.save()
            
            return JsonResponse({'success': True, 'flashcards_reviewed': progress.flashcards_reviewed})
        
        return JsonResponse({'success': False, 'error': 'Flashcard not found'})
    
    context = {
        'student_profile': student_profile,
        'subject': subject,
        'flashcards': flashcards,
        'topic_filter': topic_display_name,
        'topic_id': topic_id,
        'total_cards': len(flashcards),
        'timed_mode': timed_mode,
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
    
    # Get pricing from admin-configurable model
    pricing = {}
    try:
        from .models import StudentSubscriptionPricing
        for tier in StudentSubscriptionPricing.objects.all():
            pricing[tier.tier_type] = {
                'price': tier.price,
                'min_subjects': tier.min_subjects,
                'max_subjects': tier.max_subjects,
                'description': tier.description,
            }
    except Exception:
        # Default pricing if not configured
        pricing = {
            'per_subject': {'price': 100, 'min_subjects': 1, 'max_subjects': 3, 'description': 'Pay per subject'},
            'bundle_medium': {'price': 200, 'min_subjects': 4, 'max_subjects': 5, 'description': '4-5 subjects bundle'},
            'bundle_all': {'price': 300, 'min_subjects': None, 'max_subjects': None, 'description': 'All subjects access'},
            'tutor_addon': {'price': 500, 'min_subjects': None, 'max_subjects': None, 'description': 'Tutor support add-on'},
        }
    
    # Get current student subscription if any
    from .models import StudentSubscription
    active_subscription = StudentSubscription.objects.filter(
        student=student_profile, 
        status='active'
    ).first()
    
    context = {
        'student_profile': student_profile,
        'is_pro': is_pro,
        'current_board_count': current_board_count,
        'board_limit': student_profile.get_exam_board_limit(),
        'pricing': pricing,
        'active_subscription': active_subscription,
    }
    
    return render(request, 'core/student/subscription.html', context)


@student_login_required
def student_upgrade_to_pro(request, plan_type=None):
    """Initiate PayFast payment for Pro subscription"""
    from .payfast_service import PayFastService
    from .models import StudentSubscriptionPricing
    import logging
    
    logger = logging.getLogger(__name__)
    student_profile = request.user.student_profile
    
    # Check if already Pro
    if student_profile.subscription == 'pro':
        messages.info(request, 'You are already a Pro member!')
        return redirect('student_subscription')
    
    # Get pricing configuration
    pricing_config = StudentSubscriptionPricing.get_current()
    
    # Determine price and plan details based on plan_type
    valid_plans = {
        'per_subject': {
            'price': float(pricing_config.per_subject_price),
            'name': 'EduTech Per-Subject Plan',
            'description': f'Monthly subscription for up to {pricing_config.per_subject_max} subjects',
        },
        'multi_subject': {
            'price': float(pricing_config.multi_subject_price),
            'name': 'EduTech Multi-Subject Bundle',
            'description': f'Monthly subscription for {pricing_config.multi_subject_min}-{pricing_config.multi_subject_max} subjects',
        },
        'all_access': {
            'price': float(pricing_config.all_access_price),
            'name': 'EduTech All Access Plan',
            'description': 'Monthly subscription with unlimited access to all subjects',
        },
        'tutor_addon': {
            'price': float(pricing_config.tutor_addon_price),
            'name': 'EduTech Tutor Support Add-on',
            'description': 'Monthly tutor email support add-on',
        },
    }
    
    # Default to per_subject if no plan specified or invalid plan
    if plan_type not in valid_plans:
        plan_type = 'per_subject'
    
    plan = valid_plans[plan_type]
    amount = f"{plan['price']:.2f}"
    
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
        
        'amount': amount,
        'item_name': plan['name'],
        'item_description': plan['description'],
        
        'custom_str1': str(request.user.id),
        'custom_str2': plan_type,
        
        'subscription_type': '1',
        'recurring_amount': amount,
        'frequency': '3',
        'cycles': '0',
    }
    
    # Remove empty fields before signature generation
    clean_data = {k: v for k, v in payment_data.items() if str(v).strip()}
    
    # Generate signature
    clean_data['signature'] = PayFastService.generate_signature(clean_data)
    
    logger.info(f'Generated PayFast payment for user {request.user.username}, plan: {plan_type}, amount: R{amount}')
    
    context = {
        'student_profile': student_profile,
        'payment_data': clean_data,
        'payfast_url': PayFastService.get_payfast_url(),
        'plan_type': plan_type,
        'plan_name': plan['name'],
        'plan_price': plan['price'],
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
    
    # Create or update StudentSubscription record for tracking
    from .models import StudentSubscription
    from datetime import timedelta
    from django.utils import timezone
    
    payment_id = post_data.get('pf_payment_id', '')
    amount_paid = post_data.get('amount_gross', '100.00')
    plan_type = post_data.get('custom_str2', 'per_subject')
    
    # Validate plan type
    valid_plan_types = ['per_subject', 'multi_subject', 'all_access', 'tutor_addon']
    if plan_type not in valid_plan_types:
        plan_type = 'per_subject'
    
    subscription, created = StudentSubscription.objects.get_or_create(
        student=student_profile,
        defaults={
            'plan': plan_type,
            'status': 'active',
            'amount_paid': float(amount_paid),
            'started_at': timezone.now(),
            'expires_at': timezone.now() + timedelta(days=30),
        }
    )
    
    if not created:
        subscription.plan = plan_type
        subscription.status = 'active'
        subscription.amount_paid = float(amount_paid)
        subscription.started_at = timezone.now()
        subscription.expires_at = timezone.now() + timedelta(days=30)
        subscription.save()
    
    logger.info(f'StudentSubscription {"created" if created else "updated"} for {user.username}, payment_id: {payment_id}')
    
    # Format dates for email
    start_date = subscription.started_at.strftime('%B %d, %Y')
    expiry_date = subscription.expires_at.strftime('%B %d, %Y')
    
    # Send confirmation email with subscription details
    try:
        send_mail(
            subject='Welcome to EduTech Pro! - Your Subscription Details',
            message=f'''Hi {user.first_name or user.username},

Congratulations! Your payment was successful and you are now an EduTech Pro member!

=== SUBSCRIPTION DETAILS ===
Plan: EduTech Pro
Amount Paid: R{amount_paid}
Payment Reference: {payment_id}
Start Date: {start_date}
Valid Until: {expiry_date}
Auto-Renewal: Monthly

=== YOUR PRO BENEFITS ===
- Unlimited quizzes on all topics
- Select up to 5 exam boards (previously 2)
- Access to all study materials
- Early access to new features
- Priority support

=== NEXT STEPS ===
1. Visit your dashboard to explore Pro features
2. Add more exam boards in your settings (up to 5 total)
3. Take unlimited quizzes on any topic

Thank you for upgrading! We're excited to support your learning journey.

Best regards,
EduTech Team

---
Manage your subscription: Log in and go to Settings > Subscription
Questions? Reply to this email or contact support@edutech.com''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
        
        # Also notify parent if provided
        if student_profile.parent_email:
            send_mail(
                subject='Your Child Upgraded to EduTech Pro - Subscription Details',
                message=f'''Hello,

Your child ({user.first_name or user.username}) has upgraded to EduTech Pro subscription.

=== SUBSCRIPTION DETAILS ===
Plan: EduTech Pro
Amount Paid: R{amount_paid}
Payment Reference: {payment_id}
Start Date: {start_date}
Valid Until: {expiry_date}
Auto-Renewal: Monthly

=== BENEFITS INCLUDED ===
- Unlimited quizzes on all topics
- Up to 5 exam boards
- All study materials
- Priority support

If you have any questions about this subscription or need to cancel, please contact us at support@edutech.com.

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


@student_login_required
def student_video_library(request):
    """Browse video lessons with cascading filters"""
    student_profile = request.user.student_profile
    
    # Get all active videos
    videos = VideoLesson.objects.filter(is_active=True).select_related(
        'subject', 'topic', 'subtopic', 'concept'
    )
    
    # Get featured videos
    featured_videos = videos.filter(is_featured=True)[:6]
    
    # Get filter parameters
    subject_filter = request.GET.get('subject')
    topic_filter = request.GET.get('topic')
    subtopic_filter = request.GET.get('subtopic')
    concept_filter = request.GET.get('concept')
    search_query = request.GET.get('search', '').strip()
    
    # Apply filters
    if subject_filter:
        videos = videos.filter(subject_id=subject_filter)
    if topic_filter:
        videos = videos.filter(topic_id=topic_filter)
    if subtopic_filter:
        videos = videos.filter(subtopic_id=subtopic_filter)
    if concept_filter:
        videos = videos.filter(concept_id=concept_filter)
    if search_query:
        videos = videos.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(tags__icontains=search_query)
        )
    
    # Order by featured first, then by order and created date
    videos = videos.order_by('-is_featured', 'order', '-created_at')
    
    # Get all subjects with videos for filtering
    subjects_with_videos = Subject.objects.filter(
        video_lessons__is_active=True
    ).distinct().order_by('name')
    
    # Get topics/subtopics/concepts for selected subject (for cascading dropdowns)
    topics = []
    subtopics = []
    concepts = []
    
    if subject_filter:
        topics = Topic.objects.filter(
            subject_id=subject_filter,
            is_active=True
        ).order_by('order', 'name')
        
        if topic_filter:
            subtopics = Subtopic.objects.filter(
                topic_id=topic_filter,
                is_active=True
            ).order_by('order', 'name')
            
            if subtopic_filter:
                concepts = Concept.objects.filter(
                    subtopic_id=subtopic_filter,
                    is_active=True
                ).order_by('order', 'name')
    
    context = {
        'student_profile': student_profile,
        'videos': videos,
        'featured_videos': featured_videos,
        'subjects': subjects_with_videos,
        'topics': topics,
        'subtopics': subtopics,
        'concepts': concepts,
        'selected_subject': subject_filter,
        'selected_topic': topic_filter,
        'selected_subtopic': subtopic_filter,
        'selected_concept': concept_filter,
        'search_query': search_query,
    }
    
    return render(request, 'core/student/video_library.html', context)


@student_login_required
def student_video_player(request, video_id):
    """Watch individual video lesson"""
    student_profile = request.user.student_profile
    
    try:
        video = VideoLesson.objects.select_related(
            'subject', 'topic', 'subtopic', 'concept'
        ).get(id=video_id, is_active=True)
    except VideoLesson.DoesNotExist:
        messages.error(request, 'Video not found.')
        return redirect('student_video_library')
    
    # Increment view count
    video.view_count += 1
    video.save(update_fields=['view_count'])
    
    # Get related videos from same topic/subtopic
    related_videos = VideoLesson.objects.filter(is_active=True).exclude(id=video.id)
    
    if video.subtopic:
        related_videos = related_videos.filter(subtopic=video.subtopic)
    elif video.topic:
        related_videos = related_videos.filter(topic=video.topic)
    elif video.subject:
        related_videos = related_videos.filter(subject=video.subject)
    
    related_videos = related_videos.select_related(
        'subject', 'topic', 'subtopic', 'concept'
    ).order_by('order', '-created_at')[:8]
    
    # Parse tags
    tags_list = []
    if video.tags:
        tags_list = [tag.strip() for tag in video.tags.split(',') if tag.strip()]
    
    context = {
        'student_profile': student_profile,
        'video': video,
        'related_videos': related_videos,
        'tags_list': tags_list,
        'embed_url': video.get_youtube_embed_url(),
    }
    
    return render(request, 'core/student/video_player.html', context)


def student_video_ajax_filters(request):
    """AJAX endpoint for cascading filter dropdowns"""
    filter_type = request.GET.get('type')
    parent_id = request.GET.get('parent_id')
    
    data = []
    
    if filter_type == 'topics' and parent_id:
        topics = Topic.objects.filter(
            subject_id=parent_id,
            is_active=True
        ).order_by('order', 'name')
        data = [{'id': t.id, 'name': t.name} for t in topics]
    
    elif filter_type == 'subtopics' and parent_id:
        subtopics = Subtopic.objects.filter(
            topic_id=parent_id,
            is_active=True
        ).order_by('order', 'name')
        data = [{'id': s.id, 'name': s.name} for s in subtopics]
    
    elif filter_type == 'concepts' and parent_id:
        concepts = Concept.objects.filter(
            subtopic_id=parent_id,
            is_active=True
        ).order_by('order', 'name')
        data = [{'id': c.id, 'name': c.name} for c in concepts]
    
    return JsonResponse({'items': data})


# ===== STUDENT PATHWAY SYSTEM =====

@student_login_required
def student_subject_pathway(request, subject_id):
    """Subject pathway selection - Study, Revise, or Info"""
    from .models import StudentSubject, Topic, Note, Flashcard, StudentQuiz, ExamPaper, Syllabus, StudentTopicProgress
    
    student_profile = StudentProfile.objects.get(user=request.user)
    
    # Check if student has this subject enrolled
    student_subject = get_object_or_404(
        StudentSubject, 
        student=student_profile, 
        subject_id=subject_id
    )
    subject = student_subject.subject
    exam_board = student_subject.exam_board
    
    # Get progress stats
    topics = Topic.objects.filter(
        subject=subject,
        exam_board=exam_board,
        is_active=True
    ).count()
    
    notes_count = Note.objects.filter(
        subject=subject,
        exam_board=exam_board
    ).count()
    
    flashcards_count = Flashcard.objects.filter(
        subject=subject,
        exam_board=exam_board
    ).count()
    
    quizzes_count = StudentQuiz.objects.filter(
        subject=subject,
        exam_board=exam_board
    ).count()
    
    videos_count = VideoLesson.objects.filter(
        subject=subject,
        is_active=True
    ).count()
    
    # Calculate overall progress
    progress = StudentTopicProgress.objects.filter(
        student=student_profile,
        subject=subject
    )
    avg_progress = 0
    if progress.exists():
        total_completion = sum(p.get_completion_percentage() for p in progress)
        avg_progress = int(total_completion / max(topics, 1))
    
    context = {
        'student_profile': student_profile,
        'subject': subject,
        'exam_board': exam_board,
        'topics_count': topics,
        'notes_count': notes_count,
        'flashcards_count': flashcards_count,
        'quizzes_count': quizzes_count,
        'videos_count': videos_count,
        'overall_progress': avg_progress,
    }
    
    return render(request, 'core/student/pathway/subject_pathway.html', context)


@student_login_required
def student_study_pathway(request, subject_id):
    """Study pathway - New layout with sidebar topics and tabbed content"""
    from django.shortcuts import get_object_or_404
    from .models import StudentSubject, Topic, Subtopic, Note, VideoLesson, Flashcard, StudentQuiz, StudentTopicProgress
    
    student_profile = StudentProfile.objects.get(user=request.user)
    
    student_subject = get_object_or_404(
        StudentSubject, 
        student=student_profile, 
        subject_id=subject_id
    )
    subject = student_subject.subject
    exam_board = student_subject.exam_board
    
    # Get all topics for this subject, filtered by student's grade
    # Topics can be grade-specific or apply to all grades (grade=None)
    student_grade = student_profile.grade
    if student_grade:
        topics = Topic.objects.filter(
            subject=subject,
            is_active=True
        ).filter(
            Q(grade=student_grade) | Q(grade__isnull=True)
        ).order_by('order', 'name')
    else:
        topics = Topic.objects.filter(
            subject=subject,
            is_active=True
        ).order_by('order', 'name')
    
    # Build topics with subtopics and content counts
    topics_with_data = []
    for topic in topics:
        subtopics = Subtopic.objects.filter(topic=topic, is_active=True).order_by('order', 'name')
        progress = StudentTopicProgress.objects.filter(
            student=student_profile,
            subject=subject,
            topic=topic
        ).first()
        
        topics_with_data.append({
            'topic': topic,
            'subtopics': list(subtopics),
            'notes_count': Note.objects.filter(subject=subject, topic=topic).count(),
            'videos_count': VideoLesson.objects.filter(subject=subject, topic=topic, is_active=True).count(),
            'flashcards_count': Flashcard.objects.filter(subject=subject, topic=topic).count(),
            'quizzes_count': StudentQuiz.objects.filter(subject=subject, topic=topic.name).count(),
            'progress': progress.get_completion_percentage() if progress else 0,
        })
    
    context = {
        'student_profile': student_profile,
        'subject': subject,
        'exam_board': exam_board,
        'topics_with_data': topics_with_data,
    }
    
    return render(request, 'core/student/pathway/study_layout.html', context)


@student_login_required
def student_topic_content_ajax(request, subject_id, topic_id):
    """AJAX endpoint to load topic content for the study layout"""
    from django.shortcuts import get_object_or_404
    from .models import StudentSubject, Topic, Subtopic, Note, VideoLesson, Flashcard, StudentQuiz, InteractiveQuestion
    import json
    
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    student_profile = StudentProfile.objects.get(user=request.user)
    
    student_subject = get_object_or_404(
        StudentSubject, 
        student=student_profile, 
        subject_id=subject_id
    )
    subject = student_subject.subject
    topic = get_object_or_404(Topic, id=topic_id, subject=subject, is_active=True)
    
    subtopic_id = request.GET.get('subtopic')
    subtopic = None
    if subtopic_id:
        subtopic = Subtopic.objects.filter(id=subtopic_id, topic=topic).first()
    
    # Get notes
    notes_qs = Note.objects.filter(subject=subject, topic=topic)
    notes = [{
        'id': n.id,
        'title': n.title,
        'description': n.full_version_text[:100] if n.full_version_text else '',
        'has_full': bool(n.full_version),
        'has_summary': bool(n.summary_version),
    } for n in notes_qs[:10]]
    
    # Get videos
    videos_qs = VideoLesson.objects.filter(subject=subject, topic=topic, is_active=True)
    if subtopic:
        videos_qs = videos_qs.filter(subtopic=subtopic)
    videos = [{
        'id': v.id,
        'title': v.title,
        'duration': str(v.duration) if hasattr(v, 'duration') and v.duration else '',
    } for v in videos_qs[:10]]
    
    # Get flashcards
    flashcards_qs = Flashcard.objects.filter(subject=subject, topic=topic)
    flashcards = [{
        'id': f.id,
        'front': f.front_text[:100] if f.front_text else '',
        'back': f.back_text[:100] if f.back_text else '',
    } for f in flashcards_qs[:20]]
    
    # Get quizzes
    quizzes_qs = StudentQuiz.objects.filter(subject=subject, topic=topic.name)
    quizzes = [{
        'id': q.id,
        'title': q.title,
        'difficulty': q.difficulty,
        'questions_count': q.questions.count(),
    } for q in quizzes_qs[:10]]
    
    # Get test questions (structured/essay type for self-assessment)
    test_questions_qs = InteractiveQuestion.objects.filter(
        subject=subject,
        topic=topic,
        question_type__in=['structured', 'essay', 'fill_blank']
    ).order_by('difficulty', '-created_at')
    test_questions = [{
        'id': q.id,
        'question_text': q.question_text,
        'question_type': q.question_type,
        'difficulty': q.difficulty,
        'max_marks': q.max_marks,
        'model_answer': q.model_answer or q.correct_answer,
        'marking_guide': q.marking_guide,
    } for q in test_questions_qs[:20]]
    
    return JsonResponse({
        'notes': notes,
        'videos': videos,
        'flashcards': flashcards,
        'quizzes': quizzes,
        'test_questions': test_questions,
    })


@student_login_required
def student_topic_detail(request, subject_id, topic_id):
    """Topic detail with tabbed content - Notes, Videos, Flashcards, Quizzes"""
    from .models import StudentSubject, Topic, Note, VideoLesson, Flashcard, StudentQuiz, InteractiveQuestion, StudentTopicProgress
    
    student_profile = StudentProfile.objects.get(user=request.user)
    
    student_subject = get_object_or_404(
        StudentSubject, 
        student=student_profile, 
        subject_id=subject_id
    )
    subject = student_subject.subject
    exam_board = student_subject.exam_board
    
    topic = get_object_or_404(Topic, id=topic_id, subject=subject, is_active=True)
    
    # Get content for this topic
    notes = Note.objects.filter(subject=subject, topic=topic).order_by('-created_at')
    videos = VideoLesson.objects.filter(subject=subject, topic=topic, is_active=True).order_by('order', '-created_at')
    flashcards = Flashcard.objects.filter(subject=subject, topic=topic).order_by('-created_at')
    
    # Get quizzes grouped by difficulty
    quizzes_easy = StudentQuiz.objects.filter(
        subject=subject, topic=topic.name, difficulty='easy'
    ).order_by('-created_at')
    quizzes_medium = StudentQuiz.objects.filter(
        subject=subject, topic=topic.name, difficulty='medium'
    ).order_by('-created_at')
    quizzes_hard = StudentQuiz.objects.filter(
        subject=subject, topic=topic.name, difficulty='hard'
    ).order_by('-created_at')
    
    # Get structured questions for this topic
    structured_questions = InteractiveQuestion.objects.filter(
        subject=subject,
        topic=topic,
        question_type='structured'
    ).order_by('difficulty', '-created_at')
    
    active_tab = request.GET.get('tab', 'notes')
    
    # AJAX endpoint for tracking content views
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        content_type = request.POST.get('content_type')  # notes, videos, flashcards
        content_id = request.POST.get('content_id')
        
        progress, created = StudentTopicProgress.objects.get_or_create(
            student=student_profile,
            subject=subject,
            topic=topic
        )
        
        if content_type == 'notes' and content_id:
            progress.notes_viewed += 1
        elif content_type == 'videos' and content_id:
            progress.videos_watched += 1
        elif content_type == 'flashcards' and content_id:
            progress.flashcards_reviewed += 1
        
        progress.save()
        return JsonResponse({
            'success': True, 
            'progress_percentage': progress.get_completion_percentage()
        })
    
    # Get current progress for display
    topic_progress, _ = StudentTopicProgress.objects.get_or_create(
        student=student_profile,
        subject=subject,
        topic=topic
    )
    
    context = {
        'student_profile': student_profile,
        'subject': subject,
        'exam_board': exam_board,
        'topic': topic,
        'notes': notes,
        'videos': videos,
        'flashcards': flashcards,
        'quizzes_easy': quizzes_easy,
        'quizzes_medium': quizzes_medium,
        'quizzes_hard': quizzes_hard,
        'structured_questions': structured_questions,
        'active_tab': active_tab,
        'topic_progress': topic_progress,
    }
    
    return render(request, 'core/student/pathway/topic_detail.html', context)


@student_login_required
def student_info_pathway(request, subject_id):
    """Info pathway - Syllabi, sample papers, exam guidelines"""
    from .models import StudentSubject, Syllabus, OfficialExamPaper, ExamPaper
    
    student_profile = StudentProfile.objects.get(user=request.user)
    
    student_subject = get_object_or_404(
        StudentSubject, 
        student=student_profile, 
        subject_id=subject_id
    )
    subject = student_subject.subject
    exam_board = student_subject.exam_board
    
    # Get syllabi
    syllabi = Syllabus.objects.filter(
        subject=subject,
        exam_board=exam_board,
        is_active=True
    ).order_by('-year')
    
    # Get official exam papers
    official_papers = OfficialExamPaper.objects.filter(
        subject=subject,
        exam_board=exam_board,
        is_public=True
    ).order_by('-year', 'session')[:20]
    
    # Get sample/practice papers
    sample_papers = ExamPaper.objects.filter(
        subject=subject,
        exam_board=exam_board,
        is_pro_content=False
    ).order_by('-year', '-created_at')[:10]
    
    context = {
        'student_profile': student_profile,
        'subject': subject,
        'exam_board': exam_board,
        'syllabi': syllabi,
        'official_papers': official_papers,
        'sample_papers': sample_papers,
    }
    
    return render(request, 'core/student/pathway/info_pathway.html', context)


@student_login_required
def student_revise_pathway(request, subject_id):
    """Revise pathway - Quick flashcard review and practice quizzes"""
    from .models import StudentSubject, Topic, Flashcard, StudentQuiz, StudentTopicProgress
    
    student_profile = StudentProfile.objects.get(user=request.user)
    
    student_subject = get_object_or_404(
        StudentSubject, 
        student=student_profile, 
        subject_id=subject_id
    )
    subject = student_subject.subject
    exam_board = student_subject.exam_board
    
    # Get topics with flashcards
    topics_with_flashcards = Topic.objects.filter(
        subject=subject,
        exam_board=exam_board,
        is_active=True,
        flashcards__isnull=False
    ).distinct().order_by('order', 'name')
    
    # Get quick quiz options (by difficulty)
    easy_quizzes = StudentQuiz.objects.filter(
        subject=subject,
        exam_board=exam_board,
        difficulty='easy'
    ).order_by('?')[:5]
    
    medium_quizzes = StudentQuiz.objects.filter(
        subject=subject,
        exam_board=exam_board,
        difficulty='medium'
    ).order_by('?')[:5]
    
    hard_quizzes = StudentQuiz.objects.filter(
        subject=subject,
        exam_board=exam_board,
        difficulty='hard'
    ).order_by('?')[:5]
    
    # Get flashcard counts by topic
    flashcard_topics = []
    for topic in topics_with_flashcards:
        count = Flashcard.objects.filter(subject=subject, topic=topic).count()
        flashcard_topics.append({
            'topic': topic,
            'count': count
        })
    
    context = {
        'student_profile': student_profile,
        'subject': subject,
        'exam_board': exam_board,
        'flashcard_topics': flashcard_topics,
        'easy_quizzes': easy_quizzes,
        'medium_quizzes': medium_quizzes,
        'hard_quizzes': hard_quizzes,
    }
    
    return render(request, 'core/student/pathway/revise_pathway.html', context)


@student_login_required
def student_progress_dashboard(request):
    """Student progress dashboard with percentages and stats"""
    from .models import StudentSubject, StudentTopicProgress, StudentQuizAttempt
    
    student_profile = StudentProfile.objects.get(user=request.user)
    
    # Get all enrolled subjects with progress
    subjects_data = []
    student_subjects = StudentSubject.objects.filter(
        student=student_profile
    ).select_related('subject', 'exam_board')
    
    for ss in student_subjects:
        topic_progress = StudentTopicProgress.objects.filter(
            student=student_profile,
            subject=ss.subject
        )
        
        topics_total = Topic.objects.filter(
            subject=ss.subject,
            exam_board=ss.exam_board,
            is_active=True
        ).count()
        
        topics_completed = topic_progress.filter(notes_completed=True).count()
        
        avg_quiz_score = 0
        if topic_progress.exists():
            scores = [p.average_quiz_score for p in topic_progress if p.average_quiz_score > 0]
            if scores:
                avg_quiz_score = sum(scores) / len(scores)
        
        overall_progress = 0
        if topic_progress.exists():
            total = sum(p.get_completion_percentage() for p in topic_progress)
            overall_progress = int(total / max(topics_total, 1))
        
        subjects_data.append({
            'subject': ss.subject,
            'exam_board': ss.exam_board,
            'topics_total': topics_total,
            'topics_completed': topics_completed,
            'avg_quiz_score': round(avg_quiz_score, 1),
            'overall_progress': overall_progress,
        })
    
    # Recent quiz attempts
    recent_attempts = StudentQuizAttempt.objects.filter(
        student=student_profile
    ).select_related('quiz', 'quiz__subject').order_by('-started_at')[:10]
    
    context = {
        'student_profile': student_profile,
        'subjects_data': subjects_data,
        'recent_attempts': recent_attempts,
    }
    
    return render(request, 'core/student/pathway/progress_dashboard.html', context)


@student_login_required
def student_settings(request):
    """Student account settings page"""
    from .models import StudentSubscriptionPricing, StudentSubscription, StudentSubject
    
    student_profile = request.user.student_profile
    
    # Get subscription info
    try:
        subscription = StudentSubscription.objects.get(student=student_profile)
    except StudentSubscription.DoesNotExist:
        subscription = None
    
    # Get pricing info
    pricing = StudentSubscriptionPricing.get_current()
    
    # Get student's subjects
    student_subjects = StudentSubject.objects.filter(student=student_profile).select_related('subject', 'exam_board')
    subjects_count = student_subjects.count()
    
    # Calculate current tier price
    if subjects_count <= pricing.per_subject_max:
        current_price = pricing.per_subject_price * subjects_count
        plan_name = f"Per Subject ({subjects_count} subject{'s' if subjects_count != 1 else ''})"
    elif subjects_count <= pricing.multi_subject_max:
        current_price = pricing.multi_subject_price
        plan_name = f"Multi Subject ({subjects_count} subjects)"
    else:
        current_price = pricing.all_access_price
        plan_name = "All Access"
    
    if request.method == 'POST':
        # Handle profile updates
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        
        user = request.user
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('student_settings')
    
    context = {
        'student_profile': student_profile,
        'subscription': subscription,
        'pricing': pricing,
        'student_subjects': student_subjects,
        'subjects_count': subjects_count,
        'current_price': current_price,
        'plan_name': plan_name,
    }
    
    return render(request, 'core/student/settings/settings.html', context)


@student_login_required
def student_change_password(request):
    """Change password view"""
    student_profile = request.user.student_profile
    
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        user = request.user
        
        if not user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return redirect('student_settings')
        
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return redirect('student_settings')
        
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return redirect('student_settings')
        
        user.set_password(new_password)
        user.save()
        
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, user)
        
        messages.success(request, 'Password changed successfully!')
        return redirect('student_settings')
    
    return redirect('student_settings')


@student_login_required
def student_support(request):
    """Student support page - list enquiries"""
    from .models import SupportEnquiry
    
    student_profile = request.user.student_profile
    
    # Get all enquiries for this student
    enquiries = SupportEnquiry.objects.filter(student=student_profile).order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        enquiries = enquiries.filter(status=status_filter)
    
    context = {
        'student_profile': student_profile,
        'enquiries': enquiries,
        'selected_status': status_filter,
    }
    
    return render(request, 'core/student/support/list.html', context)


@student_login_required
def student_support_new(request):
    """Create new support enquiry"""
    from .models import SupportEnquiry, StudentSubject
    
    student_profile = request.user.student_profile
    
    # Get student's subjects for the form
    student_subjects = StudentSubject.objects.filter(student=student_profile).select_related('subject')
    
    if request.method == 'POST':
        enquiry_type = request.POST.get('enquiry_type', 'system')
        subject = request.POST.get('subject', '')
        message = request.POST.get('message', '')
        related_subject_id = request.POST.get('related_subject', '')
        related_topic = request.POST.get('related_topic', '')
        
        if not subject or not message:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('student_support_new')
        
        # Check if tutor support requires subscription
        if enquiry_type == 'tutor':
            try:
                subscription = student_profile.subscription_record
                if not subscription.has_tutor_support:
                    messages.warning(request, 'Tutor support requires the R500 add-on. Your enquiry will be submitted as a system support request.')
                    enquiry_type = 'system'
            except:
                messages.warning(request, 'Tutor support requires a subscription add-on. Your enquiry will be submitted as a system support request.')
                enquiry_type = 'system'
        
        enquiry = SupportEnquiry.objects.create(
            student=student_profile,
            enquiry_type=enquiry_type,
            subject=subject,
            message=message,
            related_topic=related_topic,
        )
        
        if related_subject_id:
            try:
                enquiry.related_subject_id = int(related_subject_id)
                enquiry.save()
            except:
                pass
        
        messages.success(request, 'Your support enquiry has been submitted. We will get back to you soon!')
        return redirect('student_support')
    
    context = {
        'student_profile': student_profile,
        'student_subjects': student_subjects,
    }
    
    return render(request, 'core/student/support/new.html', context)


@student_login_required
def student_support_view(request, enquiry_id):
    """View a support enquiry"""
    from .models import SupportEnquiry
    
    student_profile = request.user.student_profile
    
    try:
        enquiry = SupportEnquiry.objects.get(id=enquiry_id, student=student_profile)
    except SupportEnquiry.DoesNotExist:
        messages.error(request, 'Enquiry not found.')
        return redirect('student_support')
    
    context = {
        'student_profile': student_profile,
        'enquiry': enquiry,
    }
    
    return render(request, 'core/student/support/view.html', context)


@student_login_required
def student_check_answer_api(request):
    """API endpoint to check student answer using AI (GPT-3.5-turbo)"""
    import json
    from django.views.decorators.http import require_POST
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    
    try:
        data = json.loads(request.body)
        student_answer = data.get('student_answer', '').strip()
        model_answer = data.get('model_answer', '').strip()
        question_text = data.get('question_text', '').strip()
        max_marks = data.get('max_marks', 1)
        
        if not student_answer:
            return JsonResponse({'success': False, 'error': 'No answer provided'})
        
        if not model_answer:
            return JsonResponse({'success': False, 'error': 'No model answer available for comparison'})
        
        # Use OpenAI to compare answers
        try:
            from openai import OpenAI
            client = OpenAI()
            
            prompt = f"""You are an educational assessment assistant. Compare the student's answer to the model answer and provide a fair assessment.

Question: {question_text}

Model Answer: {model_answer}

Student Answer: {student_answer}

Maximum Marks: {max_marks}

Instructions:
1. Compare the student's answer to the model answer semantically (meaning, not exact wording)
2. Give partial credit for partially correct answers
3. Be encouraging but honest
4. Provide a percentage score (0-100) and brief feedback

Respond in this exact JSON format:
{{"score": <number 0-100>, "feedback": "<brief constructive feedback, 2-3 sentences>"}}"""
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful educational assistant that compares student answers to model answers. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse the JSON response
            try:
                # Handle potential markdown code blocks
                if result_text.startswith('```'):
                    result_text = result_text.split('```')[1]
                    if result_text.startswith('json'):
                        result_text = result_text[4:]
                result = json.loads(result_text)
                score = int(result.get('score', 0))
                feedback = result.get('feedback', 'Could not parse feedback.')
            except:
                # Fallback if JSON parsing fails
                score = 50
                feedback = "Your answer shows understanding. Compare with the model answer to improve."
            
            return JsonResponse({
                'success': True,
                'score': score,
                'feedback': feedback
            })
            
        except ImportError:
            return JsonResponse({
                'success': False,
                'error': 'AI service not available. Please reveal the answer and self-mark instead.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'AI service error. Please try again or use self-marking.'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid request data'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)


@student_login_required
def student_topic_progress_api(request, subject_id):
    """API endpoint to get student progress for all topics in a subject"""
    import json
    from django.utils import timezone
    
    student_profile = request.user.student_profile
    
    try:
        subject = Subject.objects.get(id=subject_id)
    except Subject.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Subject not found'}, status=404)
    
    # Get all topics for this subject, filtered by student's grade
    student_grade = student_profile.grade
    if student_grade:
        topics = Topic.objects.filter(
            subject=subject, 
            is_active=True
        ).filter(
            Q(grade=student_grade) | Q(grade__isnull=True)
        ).order_by('order', 'name')
    else:
        topics = Topic.objects.filter(subject=subject, is_active=True).order_by('order', 'name')
    
    # Get progress for each topic
    progress_data = {}
    completed_count = 0
    
    for topic in topics:
        try:
            progress = StudentTopicProgress.objects.get(
                student=student_profile,
                subject=subject,
                topic=topic
            )
            completion = progress.get_completion_percentage()
            is_completed = completion >= 75
            if is_completed:
                completed_count += 1
            
            progress_data[topic.id] = {
                'notes_completed': progress.notes_completed,
                'videos_watched': progress.videos_watched_count,
                'videos_total': progress.videos_total,
                'quizzes_completed': progress.quizzes_easy_completed + progress.quizzes_medium_completed + progress.quizzes_hard_completed,
                'average_score': float(progress.average_quiz_score),
                'completion_percentage': completion,
                'is_completed': is_completed,
                'last_activity': progress.last_activity.isoformat() if progress.last_activity else None
            }
        except StudentTopicProgress.DoesNotExist:
            progress_data[topic.id] = {
                'notes_completed': False,
                'videos_watched': 0,
                'videos_total': 0,
                'quizzes_completed': 0,
                'average_score': 0,
                'completion_percentage': 0,
                'is_completed': False,
                'last_activity': None
            }
    
    total_topics = len(topics)
    subject_completion = int((completed_count / total_topics) * 100) if total_topics > 0 else 0
    
    return JsonResponse({
        'success': True,
        'subject_id': subject_id,
        'subject_name': subject.name,
        'total_topics': total_topics,
        'completed_topics': completed_count,
        'subject_completion': subject_completion,
        'topics': progress_data
    })


@student_login_required
def student_mark_topic_complete_api(request):
    """API endpoint to mark a topic as complete"""
    import json
    from django.utils import timezone
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    student_profile = request.user.student_profile
    
    try:
        data = json.loads(request.body)
        topic_id = data.get('topic_id')
        action = data.get('action', 'complete')  # 'complete' or 'uncomplete'
        
        topic = Topic.objects.get(id=topic_id)
        subject = topic.subject
        
        # Get or create progress
        progress, created = StudentTopicProgress.objects.get_or_create(
            student=student_profile,
            subject=subject,
            topic=topic,
            defaults={
                'notes_completed': True if action == 'complete' else False
            }
        )
        
        if action == 'complete':
            progress.notes_completed = True
            progress.last_activity = timezone.now()
        else:
            progress.notes_completed = False
        
        progress.save()
        
        # Recalculate subject completion (filtered by student's grade)
        student_grade = student_profile.grade
        if student_grade:
            all_topics = Topic.objects.filter(
                subject=subject, 
                is_active=True
            ).filter(
                Q(grade=student_grade) | Q(grade__isnull=True)
            )
        else:
            all_topics = Topic.objects.filter(subject=subject, is_active=True)
        
        completed_count = 0
        for t in all_topics:
            try:
                p = StudentTopicProgress.objects.get(student=student_profile, subject=subject, topic=t)
                if p.get_completion_percentage() >= 75:
                    completed_count += 1
            except StudentTopicProgress.DoesNotExist:
                pass
        
        total_topics = all_topics.count()
        subject_completion = int((completed_count / total_topics) * 100) if total_topics > 0 else 0
        
        return JsonResponse({
            'success': True,
            'topic_id': topic_id,
            'is_completed': progress.get_completion_percentage() >= 75,
            'completion_percentage': progress.get_completion_percentage(),
            'subject_completion': subject_completion,
            'completed_topics': completed_count,
            'total_topics': total_topics
        })
        
    except Topic.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Topic not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid request data'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@student_login_required  
def student_track_content_view_api(request):
    """API endpoint to track when student views content (notes, videos)"""
    import json
    from django.utils import timezone
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    student_profile = request.user.student_profile
    
    try:
        data = json.loads(request.body)
        topic_id = data.get('topic_id')
        content_type = data.get('content_type')  # 'notes', 'video', 'flashcard'
        
        topic = Topic.objects.get(id=topic_id)
        subject = topic.subject
        
        # Get or create progress
        progress, created = StudentTopicProgress.objects.get_or_create(
            student=student_profile,
            subject=subject,
            topic=topic
        )
        
        if content_type == 'notes':
            progress.notes_read_count += 1
            if progress.notes_read_count >= 1:
                progress.notes_completed = True
        elif content_type == 'video':
            progress.videos_watched_count += 1
            # Get total videos for this topic
            from .models import VideoLesson
            total_videos = VideoLesson.objects.filter(topic=topic, is_active=True).count()
            progress.videos_total = total_videos
        elif content_type == 'flashcard':
            progress.flashcards_reviewed_count += 1
        
        progress.last_activity = timezone.now()
        progress.save()
        
        return JsonResponse({
            'success': True,
            'topic_id': topic_id,
            'content_type': content_type,
            'completion_percentage': progress.get_completion_percentage()
        })
        
    except Topic.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Topic not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid request data'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
