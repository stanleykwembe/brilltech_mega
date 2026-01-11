from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom adapter to handle student vs teacher social signups"""
    
    def save_user(self, request, sociallogin, form=None):
        """Save the user and create appropriate profile"""
        user = super().save_user(request, sociallogin, form)
        
        # Get and immediately clear the session flag to prevent leakage
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
        
        # Clear any remaining session flag (already cleared in save_user for new users)
        request.session.pop('social_login_type', None)
        
        if hasattr(user, 'student_profile'):
            if not user.student_profile.onboarding_completed:
                return reverse('student_onboarding')
            return reverse('student_dashboard')
        
        if user.is_superuser or user.is_staff:
            return reverse('admin_dashboard')
        
        if hasattr(user, 'userprofile') and user.userprofile.role == 'content_manager':
            return reverse('content_dashboard')
        
        return reverse('dashboard')
