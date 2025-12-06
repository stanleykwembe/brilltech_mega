from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import (
    ExamBoard, Subject, Grade, Topic, Subtopic, Concept,
    Note, Flashcard, InteractiveQuestion, StudentQuiz,
    UserProfile, StudentProfile, StudentExamBoard, StudentSubject,
    SubscriptionPlan, UserSubscription
)
import json


class Command(BaseCommand):
    help = 'Populate database with dummy data for ZIMSEC Biology testing'

    def handle(self, *args, **options):
        self.stdout.write('Starting dummy data population...\n')
        
        zimsec = self.create_exam_boards()
        biology = self.create_subjects()
        grades = self.create_grades()
        topics = self.create_topics(biology)
        self.create_subscription_plans()
        admin_user = self.create_admin_user()
        teacher_user = self.create_teacher_user(zimsec, biology, grades[0])
        student_user = self.create_student_user(zimsec, biology, grades[0])
        self.create_notes(biology, zimsec, grades[0], topics, admin_user)
        self.create_flashcards(biology, zimsec, grades[0], topics, admin_user)
        questions = self.create_questions(biology, zimsec, grades[0], topics, admin_user)
        self.create_quizzes(biology, zimsec, grades[0], topics, questions, admin_user)
        
        self.stdout.write(self.style.SUCCESS('\nDummy data population complete!'))
        self.stdout.write(self.style.SUCCESS('\nTest Accounts Created:'))
        self.stdout.write(f'  Admin: admin / admin123 (can access all portals)')
        self.stdout.write(f'  Teacher: test_teacher / teacher123')
        self.stdout.write(f'  Student: test_student / student123')

    def create_exam_boards(self):
        self.stdout.write('Creating exam boards...')
        boards_data = [
            ('ZIMSEC', 'Zimbabwe School Examinations Council'),
            ('Cambridge', 'Cambridge Assessment International Education'),
            ('Edexcel', 'Edexcel International'),
            ('AQA', 'Assessment and Qualifications Alliance'),
            ('IEB', 'Independent Examinations Board'),
        ]
        zimsec = None
        for abbr, name in boards_data:
            board, created = ExamBoard.objects.get_or_create(
                abbreviation=abbr,
                defaults={'name_full': name}
            )
            if abbr == 'ZIMSEC':
                zimsec = board
            status = 'created' if created else 'exists'
            self.stdout.write(f'  {abbr}: {status}')
        return zimsec

    def create_subjects(self):
        self.stdout.write('Creating subjects...')
        subjects_data = [
            'Biology',
            'Chemistry',
            'Physics',
            'Mathematics',
            'English',
            'Geography',
            'History',
            'Computer Science',
        ]
        biology = None
        for name in subjects_data:
            subject, created = Subject.objects.get_or_create(name=name)
            if name == 'Biology':
                biology = subject
            status = 'created' if created else 'exists'
            self.stdout.write(f'  {name}: {status}')
        return biology

    def create_grades(self):
        self.stdout.write('Creating grades...')
        grades = []
        for num in range(8, 14):
            grade, created = Grade.objects.get_or_create(number=num)
            grades.append(grade)
            status = 'created' if created else 'exists'
            self.stdout.write(f'  Grade {num}: {status}')
        return grades

    def create_topics(self, biology):
        self.stdout.write('Creating Biology topics and subtopics...')
        topics_data = [
            {
                'name': 'Cell Biology',
                'description': 'Study of cell structure and function',
                'subtopics': ['Cell Structure', 'Cell Membranes', 'Cell Division', 'Transport in Cells']
            },
            {
                'name': 'Human Biology',
                'description': 'Study of the human body systems',
                'subtopics': ['Digestive System', 'Circulatory System', 'Respiratory System', 'Nervous System']
            },
            {
                'name': 'Plant Biology',
                'description': 'Study of plant structure and processes',
                'subtopics': ['Photosynthesis', 'Plant Transport', 'Plant Reproduction', 'Plant Hormones']
            },
            {
                'name': 'Genetics',
                'description': 'Study of heredity and variation',
                'subtopics': ['DNA Structure', 'Inheritance', 'Genetic Variation', 'Evolution']
            },
            {
                'name': 'Ecology',
                'description': 'Study of organisms and their environment',
                'subtopics': ['Food Chains', 'Ecosystems', 'Pollution', 'Conservation']
            },
        ]
        
        topics = []
        for i, data in enumerate(topics_data):
            topic, created = Topic.objects.get_or_create(
                subject=biology,
                name=data['name'],
                defaults={
                    'description': data['description'],
                    'order': i + 1,
                    'is_active': True
                }
            )
            topics.append(topic)
            status = 'created' if created else 'exists'
            self.stdout.write(f'  Topic: {data["name"]}: {status}')
            
            for j, subtopic_name in enumerate(data['subtopics']):
                subtopic, created = Subtopic.objects.get_or_create(
                    topic=topic,
                    name=subtopic_name,
                    defaults={'order': j + 1, 'is_active': True}
                )
                status = 'created' if created else 'exists'
                self.stdout.write(f'    Subtopic: {subtopic_name}: {status}')
        
        return topics

    def create_subscription_plans(self):
        self.stdout.write('Creating subscription plans...')
        
        plans = [
            {'name': 'Free', 'plan_type': 'free', 'price': 0, 'allowed_subjects_count': 1, 'monthly_ai_generations': 0, 'can_use_ai': False},
            {'name': 'Starter', 'plan_type': 'starter', 'price': 50, 'allowed_subjects_count': 1, 'monthly_ai_generations': 10, 'can_use_ai': False},
            {'name': 'Growth', 'plan_type': 'growth', 'price': 100, 'allowed_subjects_count': 2, 'monthly_ai_generations': 20, 'can_use_ai': True},
            {'name': 'Premium', 'plan_type': 'premium', 'price': 250, 'allowed_subjects_count': 3, 'monthly_ai_generations': 999, 'can_use_ai': True},
        ]
        
        for plan_data in plans:
            plan, created = SubscriptionPlan.objects.get_or_create(
                plan_type=plan_data['plan_type'],
                defaults={
                    'name': plan_data['name'],
                    'price': plan_data['price'],
                    'allowed_subjects_count': plan_data['allowed_subjects_count'],
                    'monthly_ai_generations': plan_data['monthly_ai_generations'],
                    'can_use_ai': plan_data['can_use_ai'],
                    'can_upload_documents': True,
                    'can_access_library': True,
                    'is_active': True,
                }
            )
            status = 'created' if created else 'exists'
            self.stdout.write(f'  {plan_data["name"]}: {status}')

    def create_admin_user(self):
        self.stdout.write('Creating admin user...')
        user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@edutech.test',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            user.set_password('admin123')
            user.save()
        else:
            user.is_staff = True
            user.is_superuser = True
            user.save()
        
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'role': 'admin',
                'email_verified': True,
            }
        )
        
        grade = Grade.objects.first()
        student_profile, _ = StudentProfile.objects.get_or_create(
            user=user,
            defaults={
                'email_verified': True,
                'onboarding_completed': True,
                'subscription': 'pro',
                'grade': grade,
            }
        )
        
        self.stdout.write(f'  Admin user: {"created" if created else "exists"}')
        return user

    def create_teacher_user(self, exam_board, subject, grade):
        self.stdout.write('Creating test teacher...')
        user, created = User.objects.get_or_create(
            username='test_teacher',
            defaults={
                'email': 'teacher@edutech.test',
                'first_name': 'Test',
                'last_name': 'Teacher',
            }
        )
        if created:
            user.set_password('teacher123')
            user.save()
        
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'role': 'teacher',
                'email_verified': True,
            }
        )
        
        self.stdout.write(f'  Teacher user: {"created" if created else "exists"}')
        return user

    def create_student_user(self, exam_board, subject, grade):
        self.stdout.write('Creating test student...')
        user, created = User.objects.get_or_create(
            username='test_student',
            defaults={
                'email': 'student@edutech.test',
                'first_name': 'Test',
                'last_name': 'Student',
            }
        )
        if created:
            user.set_password('student123')
            user.save()
        
        student_profile, _ = StudentProfile.objects.get_or_create(
            user=user,
            defaults={
                'grade': grade,
                'email_verified': True,
                'onboarding_completed': True,
                'subscription': 'free',
            }
        )
        
        StudentExamBoard.objects.get_or_create(
            student=student_profile,
            exam_board=exam_board
        )
        
        StudentSubject.objects.get_or_create(
            student=student_profile,
            subject=subject,
            exam_board=exam_board
        )
        
        self.stdout.write(f'  Student user: {"created" if created else "exists"}')
        return user

    def create_notes(self, subject, exam_board, grade, topics, user):
        self.stdout.write('Creating notes...')
        
        notes_content = {
            'Cell Biology': {
                'title': 'Introduction to Cell Biology',
                'full': 'Cells are the basic units of life. All living organisms are made up of cells. There are two main types: prokaryotic cells (bacteria) and eukaryotic cells (plants, animals, fungi). Key organelles include the nucleus, mitochondria, and cell membrane.',
                'summary': 'Cells = basic life units. Types: prokaryotic (bacteria), eukaryotic (plants/animals). Key parts: nucleus, mitochondria, membrane.'
            },
            'Human Biology': {
                'title': 'Human Body Systems Overview',
                'full': 'The human body consists of multiple organ systems working together. The digestive system breaks down food, the circulatory system transports nutrients and oxygen, the respiratory system exchanges gases, and the nervous system coordinates all activities.',
                'summary': 'Body systems: Digestive (food breakdown), Circulatory (transport), Respiratory (gas exchange), Nervous (coordination).'
            },
            'Plant Biology': {
                'title': 'Photosynthesis and Plant Processes',
                'full': 'Photosynthesis is the process by which plants convert light energy into chemical energy. The equation is: 6CO2 + 6H2O + light → C6H12O6 + 6O2. This occurs in chloroplasts and requires chlorophyll.',
                'summary': 'Photosynthesis: light → chemical energy. 6CO2 + 6H2O + light → glucose + O2. Occurs in chloroplasts.'
            },
            'Genetics': {
                'title': 'DNA and Inheritance',
                'full': 'DNA (Deoxyribonucleic Acid) is the molecule that carries genetic information. It has a double helix structure discovered by Watson and Crick. Genes are segments of DNA that code for proteins. Inheritance follows Mendelian laws.',
                'summary': 'DNA: double helix, carries genetic info. Genes code for proteins. Follows Mendelian inheritance laws.'
            },
            'Ecology': {
                'title': 'Ecosystems and Food Chains',
                'full': 'An ecosystem includes all living organisms and their physical environment. Food chains show energy flow: producers → primary consumers → secondary consumers → decomposers. Energy is lost at each trophic level.',
                'summary': 'Ecosystem: organisms + environment. Food chain: producers → consumers → decomposers. Energy lost at each level.'
            },
        }
        
        for topic in topics:
            if topic.name in notes_content:
                content = notes_content[topic.name]
                note, created = Note.objects.get_or_create(
                    title=content['title'],
                    subject=subject,
                    defaults={
                        'exam_board': exam_board,
                        'grade': grade,
                        'topic': topic,
                        'topic_text': topic.name,
                        'full_version_text': content['full'],
                        'summary_version_text': content['summary'],
                        'created_by': user,
                    }
                )
                status = 'created' if created else 'exists'
                self.stdout.write(f'  Note for {topic.name}: {status}')

    def create_flashcards(self, subject, exam_board, grade, topics, user):
        self.stdout.write('Creating flashcards...')
        
        flashcards_data = {
            'Cell Biology': [
                ('What is the powerhouse of the cell?', 'Mitochondria'),
                ('What controls cell activities?', 'Nucleus'),
                ('What is the function of ribosomes?', 'Protein synthesis'),
                ('What is the cell membrane made of?', 'Phospholipid bilayer'),
            ],
            'Human Biology': [
                ('What organ pumps blood?', 'Heart'),
                ('Where does digestion mainly occur?', 'Small intestine'),
                ('What carries oxygen in blood?', 'Red blood cells / Hemoglobin'),
                ('What is the basic unit of the nervous system?', 'Neuron'),
            ],
            'Plant Biology': [
                ('Where does photosynthesis occur?', 'Chloroplasts'),
                ('What gas do plants absorb?', 'Carbon dioxide'),
                ('What pigment is essential for photosynthesis?', 'Chlorophyll'),
                ('What is the product of photosynthesis?', 'Glucose and oxygen'),
            ],
            'Genetics': [
                ('What does DNA stand for?', 'Deoxyribonucleic Acid'),
                ('What are the building blocks of DNA?', 'Nucleotides'),
                ('How many chromosomes do humans have?', '46 (23 pairs)'),
                ('What is a gene?', 'A segment of DNA that codes for a protein'),
            ],
            'Ecology': [
                ('What is a producer?', 'An organism that makes its own food (autotroph)'),
                ('What is biodiversity?', 'The variety of life in an ecosystem'),
                ('What is the greenhouse effect?', 'Trapping of heat by atmospheric gases'),
                ('What is a food web?', 'Interconnected food chains in an ecosystem'),
            ],
        }
        
        for topic in topics:
            if topic.name in flashcards_data:
                for front, back in flashcards_data[topic.name]:
                    card, created = Flashcard.objects.get_or_create(
                        front_text=front,
                        subject=subject,
                        defaults={
                            'back_text': back,
                            'exam_board': exam_board,
                            'grade': grade,
                            'topic': topic,
                            'topic_text': topic.name,
                            'created_by': user,
                        }
                    )
                status = 'created' if created else 'exists'
                self.stdout.write(f'  Flashcards for {topic.name}: {status}')

    def create_questions(self, subject, exam_board, grade, topics, user):
        self.stdout.write('Creating interactive questions...')
        
        questions_by_topic = {}
        
        mcq_questions = {
            'Cell Biology': [
                {
                    'text': 'Which organelle is responsible for producing ATP?',
                    'options': ['Nucleus', 'Mitochondria', 'Ribosome', 'Golgi apparatus'],
                    'correct': 1,
                    'explanation': 'Mitochondria are the powerhouse of the cell, producing ATP through cellular respiration.',
                    'difficulty': 'easy'
                },
                {
                    'text': 'What type of transport requires energy?',
                    'options': ['Osmosis', 'Diffusion', 'Active transport', 'Facilitated diffusion'],
                    'correct': 2,
                    'explanation': 'Active transport moves molecules against their concentration gradient and requires ATP energy.',
                    'difficulty': 'medium'
                },
                {
                    'text': 'During which phase of mitosis do chromosomes align at the cell equator?',
                    'options': ['Prophase', 'Metaphase', 'Anaphase', 'Telophase'],
                    'correct': 1,
                    'explanation': 'During metaphase, chromosomes line up at the metaphase plate (cell equator).',
                    'difficulty': 'hard'
                },
            ],
            'Human Biology': [
                {
                    'text': 'Which blood vessel carries blood away from the heart?',
                    'options': ['Vein', 'Artery', 'Capillary', 'Lymph vessel'],
                    'correct': 1,
                    'explanation': 'Arteries carry oxygenated blood away from the heart to body tissues.',
                    'difficulty': 'easy'
                },
                {
                    'text': 'What enzyme begins protein digestion in the stomach?',
                    'options': ['Amylase', 'Lipase', 'Pepsin', 'Trypsin'],
                    'correct': 2,
                    'explanation': 'Pepsin is the main enzyme in the stomach that breaks down proteins into peptides.',
                    'difficulty': 'medium'
                },
            ],
            'Genetics': [
                {
                    'text': 'If a parent has genotype Aa, what gametes can they produce?',
                    'options': ['Only A', 'Only a', 'A and a', 'AA and aa'],
                    'correct': 2,
                    'explanation': 'Heterozygous (Aa) parents can produce gametes with either the A or a allele.',
                    'difficulty': 'medium'
                },
            ],
        }
        
        structured_questions = {
            'Plant Biology': [
                {
                    'text': 'Explain the process of photosynthesis and describe the role of light and chlorophyll.',
                    'model_answer': 'Photosynthesis is the process by which plants convert light energy into chemical energy stored in glucose. Light energy is absorbed by chlorophyll in the chloroplasts. The light reactions split water molecules, releasing oxygen and generating ATP and NADPH. These products are used in the Calvin cycle to fix carbon dioxide into glucose.',
                    'marking_guide': '1 mark: Define photosynthesis. 1 mark: Role of light (energy source). 1 mark: Role of chlorophyll (absorbs light). 2 marks: Describe light reactions and Calvin cycle.',
                    'max_marks': 5,
                    'difficulty': 'hard'
                },
            ],
            'Ecology': [
                {
                    'text': 'Describe how energy flows through a food chain and explain why only 10% of energy is transferred between trophic levels.',
                    'model_answer': 'Energy flows from producers to primary consumers to secondary consumers. At each trophic level, organisms use energy for metabolism, movement, and heat production. Only about 10% of energy is passed to the next level because 90% is lost through respiration, excretion, and parts not eaten.',
                    'marking_guide': '1 mark: Energy flow direction. 1 mark: Mention of trophic levels. 2 marks: Explain energy loss through respiration/metabolism. 1 mark: Explain 10% rule.',
                    'max_marks': 5,
                    'difficulty': 'medium'
                },
            ],
        }
        
        for topic in topics:
            questions_by_topic[topic.name] = []
            
            if topic.name in mcq_questions:
                for q in mcq_questions[topic.name]:
                    options_json = [{'text': opt, 'is_correct': i == q['correct']} for i, opt in enumerate(q['options'])]
                    question, created = InteractiveQuestion.objects.get_or_create(
                        question_text=q['text'],
                        subject=subject,
                        question_type='mcq',
                        defaults={
                            'exam_board': exam_board,
                            'grade': grade,
                            'topic': topic,
                            'topic_text': topic.name,
                            'difficulty': q['difficulty'],
                            'options': options_json,
                            'correct_answer': q['options'][q['correct']],
                            'correct_option_index': q['correct'],
                            'explanation': q['explanation'],
                            'max_marks': 1,
                            'created_by': user,
                        }
                    )
                    questions_by_topic[topic.name].append(question)
            
            if topic.name in structured_questions:
                for q in structured_questions[topic.name]:
                    question, created = InteractiveQuestion.objects.get_or_create(
                        question_text=q['text'],
                        subject=subject,
                        question_type='structured',
                        defaults={
                            'exam_board': exam_board,
                            'grade': grade,
                            'topic': topic,
                            'topic_text': topic.name,
                            'difficulty': q['difficulty'],
                            'correct_answer': q['model_answer'],
                            'model_answer': q['model_answer'],
                            'marking_guide': q['marking_guide'],
                            'max_marks': q['max_marks'],
                            'created_by': user,
                        }
                    )
                    questions_by_topic[topic.name].append(question)
            
            count = len(questions_by_topic[topic.name])
            self.stdout.write(f'  Questions for {topic.name}: {count} total')
        
        return questions_by_topic

    def create_quizzes(self, subject, exam_board, grade, topics, questions_by_topic, user):
        self.stdout.write('Creating quizzes...')
        
        for topic in topics:
            topic_questions = questions_by_topic.get(topic.name, [])
            if not topic_questions:
                continue
            
            for difficulty in ['easy', 'medium', 'hard']:
                diff_questions = [q for q in topic_questions if q.difficulty == difficulty]
                if not diff_questions:
                    continue
                
                quiz, created = StudentQuiz.objects.get_or_create(
                    title=f'{topic.name} - {difficulty.title()} Quiz',
                    subject=subject,
                    defaults={
                        'exam_board': exam_board,
                        'grade': grade,
                        'topic': topic.name,
                        'difficulty': difficulty,
                        'length': min(len(diff_questions), 5),
                        'is_pro_content': False,
                        'created_by': user,
                    }
                )
                if created:
                    quiz.questions.set(diff_questions)
                    quiz.save()
                
                status = 'created' if created else 'exists'
                self.stdout.write(f'  Quiz: {topic.name} {difficulty}: {status}')
