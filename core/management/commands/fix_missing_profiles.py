from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile, StudentProfile, StudentSubscription


class Command(BaseCommand):
    help = 'Creates missing UserProfiles for admin/staff users and StudentSubscription records for students'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--create-subscriptions',
            action='store_true',
            help='Also create StudentSubscription records for students without one',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        create_subscriptions = options['create_subscriptions']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        self.stdout.write('\n=== Checking User Profiles ===\n')
        
        created_profiles = 0
        created_subscriptions = 0
        
        for user in User.objects.all():
            has_userprofile = UserProfile.objects.filter(user=user).exists()
            has_studentprofile = StudentProfile.objects.filter(user=user).exists()
            
            if user.is_staff or user.is_superuser:
                if not has_userprofile:
                    if not dry_run:
                        UserProfile.objects.create(
                            user=user,
                            role='admin',
                            subscription='premium'
                        )
                    created_profiles += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'{"Would create" if dry_run else "Created"} UserProfile for admin user: {user.username}')
                    )
                else:
                    self.stdout.write(f'Admin user {user.username} already has UserProfile')
            
            if has_studentprofile and create_subscriptions:
                student_profile = StudentProfile.objects.get(user=user)
                has_subscription = StudentSubscription.objects.filter(student=student_profile).exists()
                
                if not has_subscription:
                    if not dry_run:
                        StudentSubscription.objects.create(
                            student=student_profile,
                            plan='free',
                            status='free',
                            subjects_count=0,
                            amount_paid=0
                        )
                    created_subscriptions += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'{"Would create" if dry_run else "Created"} StudentSubscription for: {user.username}')
                    )
                else:
                    self.stdout.write(f'Student {user.username} already has subscription record')
        
        self.stdout.write('\n=== Summary ===')
        if dry_run:
            self.stdout.write(self.style.WARNING(f'Would create {created_profiles} UserProfiles'))
            if create_subscriptions:
                self.stdout.write(self.style.WARNING(f'Would create {created_subscriptions} StudentSubscriptions'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Created {created_profiles} UserProfiles'))
            if create_subscriptions:
                self.stdout.write(self.style.SUCCESS(f'Created {created_subscriptions} StudentSubscriptions'))
        
        self.stdout.write('\nDone!')
