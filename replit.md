# EduTech Freemium Multi-Portal Platform

## Overview

This is a comprehensive freemium educational technology platform serving three distinct user groups:
1. **Teachers & Admins**: Create, manage, and share educational content with AI-powered generation
2. **Students**: Interactive learning platform with quizzes, notes, flashcards, and exam preparation
3. **Content Managers**: Create and curate educational materials for both teacher and student portals

The platform operates on a freemium model with separate subscription tiers for teachers and students, offering generous free access while providing premium features for enhanced learning and teaching.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Frameworks**: Streamlit (main application), Django templates (web views), Tailwind CSS (styling), Alpine.js (interactivity), GSAP (animations).
- **Icons**: Font Awesome.
- **Landing Pages**: Dedicated marketing landing pages for teachers (`/welcome/teacher/`) and students (`/welcome/student/`) featuring:
  - Hero sections with animated gradient text and floating cards
  - Feature showcases (6 for teachers, 7 for students)
  - Detailed pricing tables (4 tiers for teachers, 2 for students)
  - Testimonials sections with real stock photos (3 per page)
  - FAQ sections (6 Q&As each covering platform features)
  - GSAP scroll-triggered animations and smooth transitions
  - Tailwind CDN for rapid prototyping (should be replaced with PostCSS build for production)
  - Stock images stored in `core/static/core/img/testimonials/`
- **UI/UX Design System**: Modern Windows 11/iPhone-inspired aesthetic with glassmorphism effects, gradient backgrounds, smooth animations, and multi-layer shadows.
  - **Design Tokens**: 8px radius for cards, 4px for buttons, 12px for modals; 200-300ms transitions; staggered animation delays.
  - **Color Themes**: Portal-specific color differentiation:
    - **Admin Portal**: Purple/indigo theme (indigo-800, purple gradients) for administrative authority
    - **Content Management Portal**: Orange/teal theme (orange-500, teal accents) for content creation
    - **Teacher Portal**: Gray-800 with indigo/purple accents for daily teaching workflows
    - **Student Portal**: Green/blue theme (emerald-500 #10b981, blue-500 #3b82f6) for engaging interactive learning
  - **Modern Components**: Stat cards with gradient icons, progress bars, action cards with hover effects, modern form styling with rounded inputs.
  - **Animation System**: Scale-in animations with staggered delays (delay-100 through delay-400), smooth hover transitions, gradient text effects.
  - **CSS Architecture**: Base modern-dashboard.css for shared design system + portal-specific theme files (admin-theme.css, content-theme.css, student-theme.css) for color overrides.
- **Interactive Elements**: Modals, forms, and dropdowns using Alpine.js with smooth transitions.

### Backend Architecture
- **Framework**: Django 5.0 (Python).
- **Application Structure**: Monolithic 'core' Django app.
- **Authentication Systems**: 
  - Teachers/Admins: Django's built-in with custom UserProfile; username/email login; token-based email verification
  - Students: Separate StudentProfile system with independent registration, parent email notifications, multi-step onboarding
- **Role-Based Access Control**: `admin`, `content_manager`, `teacher` roles with dedicated portal routing and security decorators. Students have separate access control via `@student_login_required`.
- **Content Management**: Dedicated Content Portal for content managers to:
  - Teacher Content: Upload/manage past papers, formatted papers, teacher quizzes (bulk upload with dynamic metadata forms)
  - Student Content: Create interactive questions (MCQ/True-False/Fill-blank/Matching/Essay), build quizzes, upload notes (full + summary versions), create flashcards, upload exam papers
  - **Official Exam Papers**: Secure bulk upload system with folder structure parsing, 2-step preview/confirm flow, path sanitization to prevent directory traversal, and support for Cambridge, Edexcel, CAPS, ZIMSEC, IEB, AQA, and OCR board formats
- **AI Integration**: 
  - Teacher Portal: Extracts and reformats content from PDFs using GPT-4, generates lesson plans and assignments
  - Content Creation: AI-powered question generation for interactive quizzes
- **REST API**: Comprehensive Django REST Framework API for mobile app:
  - Student endpoints: Authentication, quiz engine, notes, flashcards, exam papers, progress tracking
  - Teacher endpoints: Content access, document sharing
  - Offline support: Bulk download and sync endpoints
  - Documentation: Swagger UI and ReDoc
- **Feature Management**: Admin interface for managing exam boards, subjects, grades, subscription plans (pricing, quotas, AI models).
- **Communications System**: Platform-wide announcements (targeted, scheduled, dismissible) and email blast functionality.

### Data Storage Solutions
- **Primary Database**: SQLite (development), designed for PostgreSQL compatibility.
- **Models**: 
  - **Teacher System**: UserProfile, SubscribedSubject, UploadedDocument, Assignment, AssignmentShare, Quiz (Google Forms), QuizResponse, PastPaper, FormattedPaper, UsageQuota
  - **Student System**: StudentProfile, StudentExamBoard, StudentSubject, StudentQuiz, StudentQuizAttempt, StudentQuizQuota, InteractiveQuestion, Note, Flashcard, ExamPaper, StudentProgress
  - **Official Exam Papers**: OfficialExamPaper (with ForeignKeys to ExamBoard and optional Subject, unique constraint on board/code/year/session/paper/variant/type)
  - **Shared**: Subject, Grade, ExamBoard, Announcement, EmailBlast
- **File Storage**: Local file system with organized directories:
  - documents/%Y/%m/ - Teacher uploaded documents
  - notes/full/%Y/%m/ and notes/summary/%Y/%m/ - Student study notes
  - flashcards/images/ - Flashcard images
  - exam_papers/%Y/%m/ - Full exam papers and marking schemes
  - official_exam_papers/%Y/%m/ - Official exam papers from various boards
  - questions/images/ - Interactive question images

### Authentication and Authorization

#### Portal Redirection System
The platform uses intelligent role-based redirection to route users to their correct portal:

**Login Redirection Rules:**
1. **Student Account** (via teacher login) → Error message + redirect to student login page
2. **Teacher Account** (via student login) → Error message + redirect to teacher login page
3. **Admin/Staff Login** → `/panel/` (Admin Portal)
4. **Content Manager Login** → `/content/` (Content Manager Portal)
5. **Teacher Login** → `/` (Teacher Portal)
6. **Student Login** → `/student/dashboard/` (or `/student/onboarding/` if incomplete)

**Dashboard Access Protection:**
- **Root URL (`/`)**: Automatically redirects based on user type:
  - Students → Student Portal
  - Admins → Admin Portal  
  - Content Managers → Content Portal
  - Teachers → Teacher Dashboard
- **Admin Portal (`/panel/`)**: Requires admin/staff privileges (redirects others to their correct portal)
- **Content Portal (`/content/`)**: Requires content_manager role or admin privileges
- **Student Portal (`/student/`)**: Requires StudentProfile (blocks teachers/admins)

**Security Features:**
- Cross-portal protection prevents access to wrong dashboards
- Automatic redirection ensures users always land on their intended portal
- Clear error messages guide users to the correct login page
- Onboarding flow enforcement for new students

#### Teacher System
- **User Types**: Teachers and Admins, with Content Managers as an additional role.
- **Subscription Model**: Freemium with four tiers (Free, Starter, Growth, Premium) dictating subject limits, lesson plan quotas, and AI model access.
  - **Free (R0)**: 1 subject, 2 lesson plans/month, no AI.
  - **Starter (R50)**: 1 subject, 10 lesson plans/month, no AI.
  - **Growth (R100)**: 2 subjects, 20 lesson plans/subject/month, GPT-3.5 AI.
  - **Premium (R250)**: 3 subjects, unlimited lesson plans, GPT-4 AI.
- **Quota Enforcement**: Per-subject, monthly AI generation limits with upgrade prompts.
- **Teacher Codes**: Unique 6-character codes for Google Forms integration.

#### Student System
- **Independent Registration**: Students register separately from teachers with email/parent email verification.
- **Onboarding Flow**: Multi-step wizard for selecting grade, exam boards, and subjects (up to 10 per board).
- **Subscription Tiers**:
  - **Free (R0)**: 2 exam boards, 2 different quizzes per topic (lifetime), unlimited retries, all subjects access, full notes/flashcards.
  - **Pro (R100/month)**: 5 exam boards, unlimited quizzes, all subjects, early access to new features.
- **Quota System**: StudentQuizQuota tracks quiz attempts per topic. Free users can take 2 different quizzes per topic but retry unlimited times. Pro users have unlimited access.
- **Progress Tracking**: StudentProgress tracks quizzes attempted/passed, average scores, notes viewed, flashcards reviewed per subject/topic.
- **Payment Integration**: PayFast integration for Pro subscriptions with IPN handling, signature verification, and automatic subscription activation.

### AI Integration Architecture
- **Service Layer**: `core/openai_service.py` for all AI interactions.
- **Model Selection**: Tier-based (GPT-3.5-turbo for Growth, GPT-4 for Premium).
- **Content Generation**: Supports lesson plans, homework, and questions (MCQ, Structured, Free Response, Cambridge-style).
- **Response Format**: Structured JSON for AI-generated content.

## External Dependencies

### Third-Party Services
- **OpenAI API**: For AI content generation (GPT-3.5-turbo, GPT-4).
- **PayFast**: Payment gateway for subscriptions.
- **Google Forms**: Integration via teacher codes for quizzes.

### Frontend Libraries
- **Tailwind CSS**: For styling.
- **Alpine.js**: For interactive UI elements.
- **Font Awesome**: For iconography.

### Python Packages
- **Django**: Web framework.
- **Streamlit**: Alternative interface framework.
- **OpenAI Python SDK**: For OpenAI API communication.
- **Django REST Framework**: For API development.
- **PyPDF2**: For PDF text extraction.

### File Format Support
- **Document Formats**: PDF, DOCX, TXT (for bulk uploads).
- **Image Support**: Standard web formats.
- **Export Formats**: JSON for AI-generated content.