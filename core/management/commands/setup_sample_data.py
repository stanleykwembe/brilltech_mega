from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Subject, Grade, ExamBoard, UserProfile, UploadedDocument, GeneratedAssignment, UsageQuota
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Create sample data for development'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample data...')

        # Create subjects
        subjects_data = ['Mathematics', 'English', 'Science', 'History', 'Geography', 'Physics', 'Chemistry', 'Biology']
        subjects = []
        for subject_name in subjects_data:
            subject, created = Subject.objects.get_or_create(name=subject_name)
            subjects.append(subject)
            if created:
                self.stdout.write(f'Created subject: {subject_name}')

        # Create grades
        grades = []
        for i in range(1, 13):  # Grades 1-12
            grade, created = Grade.objects.get_or_create(number=i)
            grades.append(grade)
            if created:
                self.stdout.write(f'Created grade: {i}')

        # Create exam boards
        exam_boards_data = [
            ('Cambridge International', 'CIE'),
            ('Edexcel', 'EDX'),
            ('AQA', 'AQA'),
            ('OCR', 'OCR'),
        ]
        exam_boards = []
        for full_name, abbrev in exam_boards_data:
            board, created = ExamBoard.objects.get_or_create(
                name_full=full_name,
                abbreviation=abbrev
            )
            exam_boards.append(board)
            if created:
                self.stdout.write(f'Created exam board: {full_name}')

        # Create demo user
        demo_user, created = User.objects.get_or_create(
            username='demo_teacher',
            defaults={
                'email': 'demo@edutech.com',
                'first_name': 'Demo',
                'last_name': 'Teacher'
            }
        )
        if created:
            demo_user.set_password('demo123')
            demo_user.save()
            self.stdout.write('Created demo user: demo_teacher (password: demo123)')

        # Create user profile
        profile, created = UserProfile.objects.get_or_create(
            user=demo_user,
            defaults={
                'role': 'teacher',
                'subscription': 'free'
            }
        )

        # Create usage quota
        quota, created = UsageQuota.objects.get_or_create(
            user=demo_user,
            defaults={
                'lesson_plans_used': {},
                'assignments_used': {}
            }
        )

        # Create sample uploaded documents
        sample_docs = [
            {
                'title': 'Introduction to Algebra',
                'subject': subjects[0],  # Mathematics
                'grade': grades[7],      # Grade 8
                'board': exam_boards[0], # Cambridge
                'type': 'lesson_plan',
                'file_url': 'https://example.com/algebra-intro.pdf',
                'tags': 'algebra, introduction, basics'
            },
            {
                'title': 'Quadratic Equations Practice',
                'subject': subjects[0],  # Mathematics
                'grade': grades[8],      # Grade 9
                'board': exam_boards[0], # Cambridge
                'type': 'homework',
                'file_url': 'https://example.com/quadratic-practice.pdf',
                'tags': 'quadratic, practice, equations'
            },
            {
                'title': 'Shakespeare Analysis',
                'subject': subjects[1],  # English
                'grade': grades[9],      # Grade 10
                'board': exam_boards[1], # Edexcel
                'type': 'lesson_plan',
                'file_url': 'https://example.com/shakespeare.pdf',
                'tags': 'literature, shakespeare, analysis'
            }
        ]

        for doc_data in sample_docs:
            doc, created = UploadedDocument.objects.get_or_create(
                title=doc_data['title'],
                uploaded_by=demo_user,
                defaults=doc_data
            )
            if created:
                self.stdout.write(f'Created document: {doc_data["title"]}')

        # Create sample generated assignments
        sample_assignments = [
            {
                'title': 'Algebra Problem Set 1',
                'subject': subjects[0],  # Mathematics
                'grade': grades[7],      # Grade 8
                'board': exam_boards[0], # Cambridge
                'question_type': 'Structured',
                'due_date': datetime.now() + timedelta(days=7),
                'shared_link': f'https://edutech.com/assignment/algebra-set-1-{demo_user.id}',
                'content': {
                    'questions': [
                        {
                            'question': 'Solve for x: 2x + 5 = 15',
                            'answer': 'x = 5',
                            'difficulty': 'easy'
                        }
                    ]
                }
            },
            {
                'title': 'Chemistry Lab Report Guidelines',
                'subject': subjects[6],  # Chemistry
                'grade': grades[10],     # Grade 11
                'board': exam_boards[0], # Cambridge
                'question_type': 'Free Response',
                'due_date': datetime.now() + timedelta(days=14),
                'shared_link': f'https://edutech.com/assignment/chem-lab-{demo_user.id}',
                'content': {
                    'questions': [
                        {
                            'question': 'Describe the proper procedure for conducting a titration experiment',
                            'answer': 'Include safety measures, equipment setup, and step-by-step procedure',
                            'difficulty': 'medium'
                        }
                    ]
                }
            }
        ]

        for assignment_data in sample_assignments:
            assignment, created = GeneratedAssignment.objects.get_or_create(
                title=assignment_data['title'],
                teacher=demo_user,
                defaults=assignment_data
            )
            if created:
                self.stdout.write(f'Created assignment: {assignment_data["title"]}')

        self.stdout.write(self.style.SUCCESS('Sample data created successfully!'))
        self.stdout.write('You can now log in with:')
        self.stdout.write('Username: demo_teacher')
        self.stdout.write('Password: demo123')