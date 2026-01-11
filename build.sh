#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Create demo accounts
python manage.py shell << EOF
from django.contrib.auth.models import User
from core.models import UserProfile, StudentProfile

# Admin accounts (superuser + staff for full access)
for name in ['admin1', 'admin2']:
    if not User.objects.filter(username=name).exists():
        u = User.objects.create_superuser(name, f'{name}@demo.com', 'Demo123!')
        UserProfile.objects.get_or_create(user=u, defaults={'role': 'admin'})
        print(f'Created admin: {name}')
    else:
        u = User.objects.get(username=name)
        u.is_superuser = True
        u.is_staff = True
        u.save()
        print(f'Updated admin: {name}')

# Content Manager accounts
for name in ['content1', 'content2']:
    if not User.objects.filter(username=name).exists():
        u = User.objects.create_user(name, f'{name}@demo.com', 'Demo123!')
        UserProfile.objects.get_or_create(user=u, defaults={'role': 'content_manager'})
        print(f'Created content manager: {name}')

# Student accounts
for name in ['student1', 'student2']:
    if not User.objects.filter(username=name).exists():
        u = User.objects.create_user(name, f'{name}@demo.com', 'Demo123!')
        StudentProfile.objects.get_or_create(user=u)
        print(f'Created student: {name}')

print('Demo accounts ready!')
EOF