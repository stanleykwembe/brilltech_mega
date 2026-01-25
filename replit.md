# EduTech Freemium Multi-Portal Platform

## Overview
This project is a comprehensive freemium educational technology platform designed to serve Teachers, Admins, Students, and Content Managers. It facilitates content creation, interactive learning, and curriculum management with AI-powered features. The platform utilizes a freemium model with separate subscription tiers for teachers and students, offering extensive free access alongside premium features to enhance educational experiences. Its core purpose is to provide an accessible and engaging educational experience, leveraging AI for personalized learning and content generation.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### UI/UX Design
The platform features a modern design inspired by Windows 11 and iPhone aesthetics, incorporating glassmorphism, gradient backgrounds, smooth animations, and multi-layer shadows. It utilizes an 8px radius for cards, 4px for buttons, and 12px for modals, with 200-300ms transitions. Color themes are portal-specific: purple/indigo for Admin, orange/teal for Content Management, gray with indigo/purple accents for Teacher, and green/blue for Student. The frontend is built with Django templates, Tailwind CSS, Alpine.js for interactivity, and GSAP for animations.

### Technical Implementation
The backend is powered by Django 5.0, structured as a monolithic 'core' Django app. It features distinct authentication systems for Teachers/Admins and Students, with role-based access control for `admin`, `content_manager`, and `teacher` roles. A robust portal redirection system ensures users are routed to their appropriate dashboards. Key features include:
- **Landing Pages**: Dedicated marketing pages for teachers and students.
- **Public Papers Page**: Offers free access to exam papers with AJAX filters, lazy-loading, and ad integration.
- **Content Management Portal**: Allows content managers to upload and manage various educational materials, including official exam papers, interactive questions (MCQ, True-False, Fill-blank, Matching, Essay), notes, and flashcards, supporting multiple exam boards.
- **Teacher Portal**: Enables teachers to create and share content, with AI integration for generating lesson plans and assignments from PDFs.
- **Student Portal**: Provides an interactive learning environment with quizzes, notes, flashcards, and exam preparation. Features multi-step onboarding, progress tracking, and pathway-based navigation. Quizzes support auto-marking for MCQs and AI-assisted marking for structured questions.
- **AI Integration**: A dedicated service layer (`core/openai_service.py`) handles all AI interactions, supporting content generation for lesson plans, homework, and various question types, with model selection based on subscription tiers (GPT-3.5-turbo, GPT-4). AI-generated content is returned in structured JSON.
- **REST API**: A comprehensive Django REST Framework API provides endpoints for mobile applications, including offline support and Swagger/ReDoc documentation.
- **Feature Management**: An admin interface manages exam boards, subjects, grades, and subscription plans.
- **Communications**: Platform-wide announcements and email blast functionality.
- **Performance Optimization**: Utilizes WhiteNoise for static file compression, Tailwind CSS build system, caching, and lazy loading for images.
- **Async Email Sending**: All email operations (signup, verification, password reset) use background threads via `send_email_async()` helper to prevent HTTP request blocking and Gunicorn worker timeouts. Emails are logged at info/error levels for production debugging.
- **CRM System**: Integrated full CRM system in the BrillTech Admin Portal with Tasks, Leads, Sales Pipeline, Mailing Lists, and Email Campaigns.
- **Social Login**: Integrated Google and Facebook social login via django-allauth for both Teacher and Student portals.
- **Subscription Management**: Comprehensive admin tools for managing teacher and student subscription plans, including dynamic pricing and manual status changes.

### Subscription Systems
- **Teacher Subscriptions**: Configurable tiers (Free, Starter, Growth, Premium) with varying prices, AI generation quotas, and subject limits.
- **Student Subscriptions**: Simplified tiered pricing model:
  - **Starter (R100/month)**: 2 subjects, 1 exam board
  - **Standard (R200/month)**: 4 subjects, any exam boards
  - **Full Access (R500/month)**: Unlimited subjects, all exam boards
  - **Tutor Add-on (+R500/month)**: Live tutor support
  - All prices admin-configurable via `StudentSubscriptionPricing` model
  - Subscription status tracked via `StudentSubscription` model with active/expired/cancelled states
  - Subject/board limits enforced based on active subscription plan

### Data Storage
- **Database**: SQLite for development, designed for PostgreSQL compatibility.
- **Models**: Comprehensive models for Teacher and Student systems, Official Exam Papers, and shared entities.
- **File Storage**: Local file system, organized by content type and date.

## External Dependencies

### Third-Party Services
- **OpenAI API**: For AI content generation (GPT-3.5-turbo, GPT-4).
- **PayFast**: Payment gateway for subscription management.
- **Google Forms**: Used for teacher quizzes integration.
- **Google OAuth**: For Google social login.
- **Facebook OAuth**: For Facebook social login.

### Frontend Libraries
- **Tailwind CSS**: Utility-first CSS framework.
- **Alpine.js**: Lightweight JavaScript framework for UI interactivity.
- **Font Awesome**: Icon library.
- **GSAP**: JavaScript animation library.

### Python Packages
- **Django**: Web framework.
- **OpenAI Python SDK**: Python client for OpenAI API.
- **Django REST Framework**: For building RESTful APIs.
- **PyPDF2**: For PDF text extraction.
- **python-docx**: For Word document handling.
- **Pillow**: Image processing.
- **psycopg2-binary**: PostgreSQL adapter.
- **django-allauth**: For social authentication.
- **WhiteNoise**: For serving static files efficiently.