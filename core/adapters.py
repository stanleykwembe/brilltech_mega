from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom adapter to handle student vs teacher social signups"""
    
    def pre_social_login(self, request, sociallogin):
        """Handle existing users logging in with social accounts"""
        super().pre_social_login(request, sociallogin)
        
        if sociallogin.is_existing:
            return
        
        email = sociallogin.account.extra_data.get('email')
        if email:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                existing_user = User.objects.get(email=email)
                sociallogin.connect(request, existing_user)
            except User.DoesNotExist:
                pass
    
    def save_user(self, request, sociallogin, form=None):
        """Save the user and create appropriate profile"""
        user = super().save_user(request, sociallogin, form)
        
        login_type = request.session.pop('social_login_type', 'teacher')
        
        if login_type == 'student':
            from core.models import StudentProfile
            if not hasattr(user, 'student_profile'):
                StudentProfile.objects.create(
                    user=user,
                    email_verified=True,
                    onboarding_completed=False
                )
        else:
            from core.models import UserProfile
            if not hasattr(user, 'userprofile'):
                UserProfile.objects.create(
                    user=user,
                    role='teacher',
                    email_verified=True
                )
        
        return user


class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom adapter to handle redirects after social login"""
    
    def get_login_redirect_url(self, request):
        """Redirect based on user type after login"""
        user = request.user
        
        request.session.pop('social_login_type', None)
        
        if hasattr(user, 'student_profile'):
            profile = user.student_profile
            
            from core.models import StudentSubject, StudentExamBoard
            has_subjects = StudentSubject.objects.filter(student=profile).exists()
            has_exam_boards = StudentExamBoard.objects.filter(student=profile).exists()
            
            if not profile.onboarding_completed:
                if has_subjects or has_exam_boards:
                    profile.onboarding_completed = True
                    profile.save(update_fields=['onboarding_completed'])
                    return reverse('student_dashboard')
                return reverse('student_onboarding')
            
            return reverse('student_dashboard')
        
        if user.is_superuser or user.is_staff:
            return reverse('admin_dashboard')
        
        if hasattr(user, 'userprofile') and user.userprofile.role == 'content_manager':
            return reverse('content_dashboard')
        
        return reverse('teacher_dashboard')
