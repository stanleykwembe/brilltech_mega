from django.core.management.base import BaseCommand
from core.models import SubscriptionPlan

class Command(BaseCommand):
    help = 'Creates the 4 subscription plan tiers for the platform'

    def handle(self, *args, **kwargs):
        plans = [
            {
                'name': 'Free',
                'plan_type': 'free',
                'price': 0,
                'billing_period': 'monthly',
                'can_upload_documents': True,
                'can_use_ai': False,
                'can_access_library': False,
                'allowed_subjects_count': 0,
                'monthly_ai_generations': 0,
                'description': 'Basic document uploads and viewing capabilities'
            },
            {
                'name': 'Starter',
                'plan_type': 'starter',
                'price': 50,
                'billing_period': 'monthly',
                'can_upload_documents': True,
                'can_use_ai': False,
                'can_access_library': False,
                'allowed_subjects_count': 0,
                'monthly_ai_generations': 0,
                'description': 'Document management only - perfect for organized teachers who bring their own content'
            },
            {
                'name': 'Growth',
                'plan_type': 'growth',
                'price': 100,
                'billing_period': 'monthly',
                'can_upload_documents': True,
                'can_use_ai': False,
                'can_access_library': True,
                'allowed_subjects_count': 1,
                'monthly_ai_generations': 0,
                'description': 'Access pre-generated worksheets and lesson plans for 1 subject of your choice'
            },
            {
                'name': 'Premium',
                'plan_type': 'premium',
                'price': 250,
                'billing_period': 'monthly',
                'can_upload_documents': True,
                'can_use_ai': True,
                'can_access_library': True,
                'allowed_subjects_count': 0,
                'monthly_ai_generations': 0,
                'description': 'Full AI-powered content generation for all subjects with unlimited generations'
            },
        ]

        created_count = 0
        updated_count = 0

        for plan_data in plans:
            plan, created = SubscriptionPlan.objects.update_or_create(
                plan_type=plan_data['plan_type'],
                defaults=plan_data
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created plan: {plan.name} (R{plan.price}/month)'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'↻ Updated plan: {plan.name} (R{plan.price}/month)'))

        self.stdout.write(self.style.SUCCESS(f'\nTotal: {created_count} created, {updated_count} updated'))
