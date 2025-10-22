from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile, SubscriptionPlan
import random
import string

class Command(BaseCommand):
    help = 'Generate teacher codes and update subscription plans with new pricing'

    def handle(self, *args, **kwargs):
        self.stdout.write('Setting up subscription system...\n')
        
        # Generate teacher codes for existing users
        self.stdout.write('Generating teacher codes for existing users...')
        profiles_updated = 0
        for profile in UserProfile.objects.filter(teacher_code__isnull=True):
            # Generate a unique 6-character code
            while True:
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                if not UserProfile.objects.filter(teacher_code=code).exists():
                    profile.teacher_code = code
                    profile.save()
                    profiles_updated += 1
                    break
        
        self.stdout.write(self.style.SUCCESS(f'✓ Generated teacher codes for {profiles_updated} users'))
        
        # Update subscription plans with new pricing
        self.stdout.write('\nUpdating subscription plans...')
        
        # Free Plan
        free_plan, created = SubscriptionPlan.objects.update_or_create(
            plan_type='free',
            defaults={
                'name': 'Free',
                'price': 0.00,
                'billing_period': 'monthly',
                'can_upload_documents': True,
                'can_use_ai': False,
                'can_access_library': True,
                'allowed_subjects_count': 1,
                'monthly_ai_generations': 0,
                'description': '1 subject, 2 lesson plans/month, 10 library quizzes. No AI features.',
                'is_active': True,
            }
        )
        self.stdout.write(f"  {'Created' if created else 'Updated'} Free plan (R0)")
        
        # Starter Plan
        starter_plan, created = SubscriptionPlan.objects.update_or_create(
            plan_type='starter',
            defaults={
                'name': 'Starter',
                'price': 50.00,
                'billing_period': 'monthly',
                'can_upload_documents': True,
                'can_use_ai': False,
                'can_access_library': True,
                'allowed_subjects_count': 1,
                'monthly_ai_generations': 0,
                'description': '1 subject, 10 lesson plans/month, all library quizzes. No AI features.',
                'is_active': True,
            }
        )
        self.stdout.write(f"  {'Created' if created else 'Updated'} Starter plan (R50)")
        
        # Growth Plan
        growth_plan, created = SubscriptionPlan.objects.update_or_create(
            plan_type='growth',
            defaults={
                'name': 'Growth',
                'price': 100.00,
                'billing_period': 'monthly',
                'can_upload_documents': True,
                'can_use_ai': True,
                'can_access_library': True,
                'allowed_subjects_count': 2,
                'monthly_ai_generations': 40,  # 20 per subject
                'description': '2 subjects, 20 lesson plans per subject/month, all library quizzes, basic AI (GPT-3.5).',
                'is_active': True,
            }
        )
        self.stdout.write(f"  {'Created' if created else 'Updated'} Growth plan (R100)")
        
        # Premium Plan
        premium_plan, created = SubscriptionPlan.objects.update_or_create(
            plan_type='premium',
            defaults={
                'name': 'Premium',
                'price': 250.00,
                'billing_period': 'monthly',
                'can_upload_documents': True,
                'can_use_ai': True,
                'can_access_library': True,
                'allowed_subjects_count': 3,
                'monthly_ai_generations': 0,  # 0 = unlimited
                'description': '3 subjects, unlimited lesson plans, all library quizzes, advanced AI (GPT-4).',
                'is_active': True,
            }
        )
        self.stdout.write(self.style.SUCCESS(f"  {'Created' if created else 'Updated'} Premium plan (R250)"))
        
        self.stdout.write(self.style.SUCCESS('\n✓ Subscription system setup complete!'))
        self.stdout.write('\nNext steps:')
        self.stdout.write('  1. Users can now select their subjects during signup')
        self.stdout.write('  2. Quotas are enforced per subject based on subscription tier')
        self.stdout.write('  3. Teacher codes are ready for Google Forms integration')
