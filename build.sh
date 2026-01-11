#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Create demo accounts
python manage.py shell << EOF
from django.contrib.auth.models import User
from core.models import UserProfile, StudentProfile

# Admin accounts
for i, name in enumerate(['admin1', 'admin2'], 1):
    if not User.objects.filter(username=name).exists():
        u = User.objects.create_user(name, f'{name}@demo.com', 'Demo123!', is_staff=True)
        UserProfile.objects.get_or_create(user=u, defaults={'role': 'admin'})
        print(f'Created admin: {name}')

# Content Manager accounts
for i, name in enumerate(['content1', 'content2'], 1):
    if not User.objects.filter(username=name).exists():
        u = User.objects.create_user(name, f'{name}@demo.com', 'Demo123!')
        UserProfile.objects.get_or_create(user=u, defaults={'role': 'content_manager'})
        print(f'Created content manager: {name}')

# Student accounts
for i, name in enumerate(['student1', 'student2'], 1):
    if not User.objects.filter(username=name).exists():
        u = User.objects.create_user(name, f'{name}@demo.com', 'Demo123!')
        StudentProfile.objects.get_or_create(user=u)
        print(f'Created student: {name}')

print('Demo accounts ready!')
EOF