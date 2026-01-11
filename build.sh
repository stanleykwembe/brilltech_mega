#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Create demo accounts and seed data
python manage.py shell << EOF
from django.contrib.auth.models import User
from core.models import UserProfile, StudentProfile, ExamBoard, Subject, Grade

# Admin accounts
for name in ['admin1', 'admin2']:
    u, created = User.objects.get_or_create(username=name, defaults={'email': f'{name}@demo.com'})
    if created:
        u.set_password('Demo123!')
    u.is_superuser = True
    u.is_staff = True
    u.save()
    UserProfile.objects.get_or_create(user=u, defaults={'role': 'admin'})
    print(f'Admin ready: {name}')

# Content Manager accounts
for name in ['content1', 'content2']:
    u, created = User.objects.get_or_create(username=name, defaults={'email': f'{name}@demo.com'})
    if created:
        u.set_password('Demo123!')
        u.save()
    UserProfile.objects.get_or_create(user=u, defaults={'role': 'content_manager'})
    print(f'Content manager ready: {name}')

# Student accounts
for name in ['student1', 'student2']:
    u, created = User.objects.get_or_create(username=name, defaults={'email': f'{name}@demo.com'})
    if created:
        u.set_password('Demo123!')
        u.save()
    StudentProfile.objects.get_or_create(user=u)
    print(f'Student ready: {name}')

# Exam Boards
boards_data = [
    ('Cambridge International Examinations', 'CIE', 'International'),
    ('Edexcel', 'EDEXCEL', 'UK'),
    ('CAPS (Curriculum and Assessment Policy Statement)', 'CAPS', 'South Africa'),
    ('ZIMSEC', 'ZIMSEC', 'Zimbabwe'),
    ('IEB (Independent Examinations Board)', 'IEB', 'South Africa'),
    ('AQA', 'AQA', 'UK'),
]
for name_full, abbrev, region in boards_data:
    board, created = ExamBoard.objects.get_or_create(abbreviation=abbrev, defaults={'name_full': name_full, 'region': region})
    print(f"{'Created' if created else 'Exists'}: {abbrev}")

# Subjects
subjects_data = ['Mathematics', 'English', 'Physics', 'Chemistry', 'Biology', 'Geography', 'History', 'Accounting', 'Business Studies', 'Computer Science']
for subj_name in subjects_data:
    subj, created = Subject.objects.get_or_create(name=subj_name)
    print(f"{'Created' if created else 'Exists'}: {subj_name}")

# Grades (uses 'number' field, not 'name')
for i in range(8, 13):
    grade, created = Grade.objects.get_or_create(number=i)
    print(f"{'Created' if created else 'Exists'}: Grade {i}")

print('All demo data ready!')
EOF