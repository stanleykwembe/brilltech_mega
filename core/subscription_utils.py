from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from .models import UserSubscription, SubscriptionPlan

def get_user_subscription(user):
    """Get or create user subscription"""
    try:
        return UserSubscription.objects.select_related('plan').get(user=user)
    except UserSubscription.DoesNotExist:
        from django.utils import timezone
        from datetime import timedelta
        free_plan = SubscriptionPlan.objects.get(plan_type='free')
        return UserSubscription.objects.create(
            user=user,
            plan=free_plan,
            status='active',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=365)
        )

def user_has_feature(user, feature):
    """Check if user's subscription has a specific feature"""
    subscription = get_user_subscription(user)
    
    if not subscription.is_active:
        return False
    
    feature_map = {
        'upload_documents': subscription.plan.can_upload_documents,
        'use_ai': subscription.plan.can_use_ai,
        'access_library': subscription.plan.can_access_library,
    }
    
    return feature_map.get(feature, False)

def require_subscription_feature(feature, redirect_to='subscription_dashboard'):
    """
    Decorator to require a specific subscription feature
    
    Usage:
        @require_subscription_feature('use_ai')
        def my_ai_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not user_has_feature(request.user, feature):
                subscription = get_user_subscription(request.user)
                messages.error(
                    request,
                    f'This feature requires an upgraded subscription. '
                    f'Your current plan: {subscription.plan.name}'
                )
                return redirect(redirect_to)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def require_premium(view_func):
    """Shortcut decorator to require Premium subscription"""
    return require_subscription_feature('use_ai')(view_func)
