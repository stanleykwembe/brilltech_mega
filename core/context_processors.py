"""Context processors for making data available in all templates"""

def announcements(request):
    """Add active announcements to all template contexts"""
    from .models import Announcement
    from django.utils import timezone
    
    if request.user.is_authenticated:
        # Get announcements that are visible to this user
        active_announcements = []
        all_announcements = Announcement.objects.filter(
            is_active=True
        ).exclude(
            expires_at__lt=timezone.now()
        )
        
        for announcement in all_announcements:
            if announcement.is_visible_to(request.user):
                active_announcements.append(announcement)
        
        return {'active_announcements': active_announcements}
    
    return {'active_announcements': []}
