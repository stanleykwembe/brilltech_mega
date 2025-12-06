# EduTech Freemium Multi-Portal Platform

## Overview

This project is a comprehensive freemium educational technology platform designed to serve four distinct user groups: Teachers, Admins, Students, and Content Managers. It facilitates content creation, interactive learning, and curriculum management with AI-powered features. The platform utilizes a freemium model with separate subscription tiers for teachers and students, offering extensive free access alongside premium features to enhance educational experiences.

## Recent Changes (December 2025)

- **Social Login**: Added Google and Facebook social login via django-allauth for both Teacher and Student portals
- **Admin Panel Reorganization**: Separated subscription management into Teacher Plans (`/panel/features/teachers/plans/`) and Student Plans (`/panel/features/student/plans/`)
- **Admin Signup**: Added admin signup page at `/brilltech/signup/` for creating new administrator accounts
- **Django Admin**: Moved to `/brilltech/admin/` for future company CRM use
- **Student Pricing Model**: Implemented single-row configuration for all student subscription tiers (per-subject, multi-subject bundle, all-access, tutor add-on)

## User Preferences

Preferred communication style: Simple, everyday language.

## Test Accounts

| Portal | Username | Password |
|--------|----------|----------|
| Admin (Django) | superadmin | Super123! |
| Admin (Django) | admin | admin123 |
| Teacher | test_teacher | teacher123 |
| Student | test_student | student123 |

## URL Structure

### Public Pages
- `/` - Home/Dashboard (redirects to login if not authenticated)
- `/login/` - Teacher/Admin login
- `/signup/` - Teacher registration
- `/welcome/teacher/` - Teacher landing page
- `/welcome/student/` - Student landing page

### Admin Portals
- `/panel/` - Custom admin dashboard (for platform management)
- `/panel/features/` - Feature management (exam boards, subjects, grades)
- `/panel/features/teachers/plans/` - Teacher subscription plans management
- `/panel/features/student/plans/` - Student pricing configuration
- `/panel/users/` - User management
- `/panel/communications/` - Announcements and email blasts
- `/brilltech/admin/` - Django admin (for database-level access)
- `/brilltech/signup/` - Admin account signup

### Student Portal
- `/student/login/` - Student login
- `/student/signup/` - Student registration
- `/student/dashboard/` - Student dashboard
- `/student/study/` - Study page with collapsible navigation

### Teacher Portal
- `/` - Teacher dashboard
- `/lesson-plans/` - Lesson plan management
- `/assignments/` - Assignment management
- `/documents/` - Document management

### Content Manager Portal
- `/content/` - Content manager dashboard
- `/content/papers/` - Exam paper management

## System Architecture

### UI/UX Design
The platform features a modern design inspired by Windows 11 and iPhone aesthetics, incorporating glassmorphism, gradient backgrounds, smooth animations, and multi-layer shadows. It utilizes an 8px radius for cards, 4px for buttons, and 12px for modals, with 200-300ms transitions. Color themes are portal-specific: purple/indigo for Admin, orange/teal for Content Management, gray with indigo/purple accents for Teacher, and green/blue for Student. Frontend is built with Django templates, Tailwind CSS, Alpine.js for interactivity, and GSAP for animations.

### Technical Implementation
The backend is powered by Django 5.0, structured as a monolithic 'core' Django app. It features distinct authentication systems for Teachers/Admins and Students, with role-based access control for `admin`, `content_manager`, and `teacher` roles. A robust portal redirection system ensures users are routed to their appropriate dashboards. Key features include:

- **Landing Pages**: Dedicated marketing pages for teachers and students with dynamic content and animations.
- **Public Papers Page**: Offers free access to exam papers with AJAX filters, lazy-loading, and ad integration.
- **Content Management Portal**: Allows content managers to upload and manage various educational materials, including official exam papers, interactive questions (MCQ, True-False, Fill-blank, Matching, Essay), notes, and flashcards. Supports bulk uploads and parsing for multiple exam boards (Cambridge, Edexcel, CAPS, ZIMSEC, IEB, AQA, OCR).
- **Teacher Portal**: Enables teachers to create and share content, with AI integration for generating lesson plans and assignments from PDFs.
- **Student Portal**: Provides an interactive learning environment with quizzes, notes, flashcards, and exam preparation. Features a multi-step onboarding process, progress tracking, and a pathway-based navigation system for studying, revising, and accessing information. Quizzes support auto-marking for MCQs and AI-assisted marking for structured questions.
- **AI Integration**: A dedicated service layer (`core/openai_service.py`) handles all AI interactions, supporting content generation for lesson plans, homework, and various question types, with model selection based on subscription tiers (GPT-3.5-turbo, GPT-4). AI-generated content is returned in structured JSON format.
- **REST API**: A comprehensive Django REST Framework API is provided for mobile applications, offering endpoints for students (authentication, quizzes, notes, flashcards, exam papers, progress tracking) and teachers (content access, document sharing), including offline support and Swagger/ReDoc documentation.
- **Feature Management**: An admin interface manages exam boards, subjects, grades, and subscription plans (separate for teachers and students).
- **Communications**: Platform-wide announcements and email blast functionality.

### Subscription Systems

#### Teacher Subscriptions (SubscriptionPlan model)
Managed at `/panel/features/teachers/plans/`
- Free, Starter, Growth, Premium tiers
- Configurable: price, AI generations quota, subject limits

#### Student Subscriptions (StudentSubscriptionPricing model)
Managed at `/panel/features/student/plans/`
- Per-subject pricing (R100/subject for 1-3 subjects)
- Multi-subject bundle (R200 flat for 4-5 subjects)
- All-access (R300 for unlimited subjects)
- Tutor add-on (+R500 for email support)
- All prices and bounds are admin-configurable

### Data Storage
- **Database**: SQLite for development, designed for PostgreSQL compatibility.
- **Models**: Comprehensive models cover Teacher and Student systems, Official Exam Papers, and shared entities like Subject, Grade, ExamBoard.
- **File Storage**: Local file system, organized by content type (documents, notes, flashcards, exam papers) and date.

## Key Files

- `core/views.py` - Main teacher and admin views
- `core/student_views.py` - Student portal views
- `core/models.py` - Database models
- `core/urls.py` - URL routing for core app
- `core/student_urls.py` - URL routing for student portal
- `core/admin_signup_views.py` - Admin signup functionality
- `core/openai_service.py` - AI integration service
- `django_project/urls.py` - Root URL configuration
- `django_project/settings.py` - Django settings

## External Dependencies

### Third-Party Services
- **OpenAI API**: For AI content generation (GPT-3.5-turbo, GPT-4).
- **PayFast**: Payment gateway for subscription management.
- **Google Forms**: Used for teacher quizzes integration.

### Frontend Libraries
- **Tailwind CSS**: Utility-first CSS framework for styling.
- **Alpine.js**: Lightweight JavaScript framework for UI interactivity.
- **Font Awesome**: Icon library.
- **GSAP**: JavaScript animation library.

### Python Packages
- **Django**: Web framework.
- **OpenAI Python SDK**: Python client for the OpenAI API.
- **Django REST Framework**: For building RESTful APIs.
- **PyPDF2**: For PDF text extraction.
- **python-docx**: For Word document handling.
- **Pillow**: Image processing.
- **psycopg2-binary**: PostgreSQL adapter.

## Environment Variables

Required secrets (set in Replit Secrets):
- `OPENAI_API_KEY` - OpenAI API key for AI features
- `EMAIL_HOST_USER` - Email sending (SMTP username)
- `EMAIL_HOST_PASSWORD` - Email sending (SMTP password)

### Social Login (Optional)
To enable Google/Facebook login, add these secrets:
- `GOOGLE_CLIENT_ID` - Google OAuth client ID (from Google Cloud Console)
- `GOOGLE_CLIENT_SECRET` - Google OAuth client secret
- `FACEBOOK_APP_ID` - Facebook App ID (from Facebook Developer Console)
- `FACEBOOK_APP_SECRET` - Facebook App Secret

**Setup Instructions:**
1. **Google**: Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → Create OAuth 2.0 Client ID
   - Add authorized redirect URI: `https://your-domain/accounts/google/login/callback/`
2. **Facebook**: Go to [Facebook Developers](https://developers.facebook.com/) → Create App → Facebook Login
   - Add valid OAuth redirect URI: `https://your-domain/accounts/facebook/login/callback/`
