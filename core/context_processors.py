"""Context processors for making data available in all templates"""

def announcements(request):
    """Add active announcements to all template contexts"""
    from .models import Announcement
    from django.db import models
    from django.utils import timezone
    
    if request.user.is_authenticated:
        # Get announcements that are visible to this user
        now = timezone.now()
        active_announcements = []
        
        # Build query with proper scheduling logic
        query = Announcement.objects.filter(is_active=True)
        
        # Filter by start time (if set)
        query = query.filter(models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now))
        
        # Filter by expiry time (if set)
        query = query.filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gte=now))
        
        # Exclude dismissed announcements
        query = query.exclude(dismissed_by=request.user)
        
        # Order by priority (critical first) then created date
        query = query.order_by(
            models.Case(
                models.When(priority='critical', then=1),
                models.When(priority='warning', then=2),
                models.When(priority='info', then=3),
                default=4,
                output_field=models.IntegerField(),
            ),
            '-created_at'
        )
        
        all_announcements = query
        
        for announcement in all_announcements:
            if announcement.is_visible_to(request.user):
                active_announcements.append(announcement)
        
        return {'active_announcements': active_announcements}
    
    return {'active_announcements': []}
