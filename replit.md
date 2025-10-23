# EduTech Freemium Teacher Platform

## Overview

This is a freemium educational technology platform for teachers and administrators to create, manage, and share educational content. It offers AI-powered content generation (lesson plans, assignments, questions), document management, and sharing functionalities. The platform operates on a freemium model with usage quotas and subscription tiers, aiming to empower educators with advanced tools.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Frameworks**: Streamlit (main application), Django templates (web views), Tailwind CSS (styling), Alpine.js (interactivity).
- **Icons**: Font Awesome.
- **UI/UX Design System**: Modern Windows 11/iPhone-inspired aesthetic with glassmorphism effects, gradient backgrounds, smooth animations, and multi-layer shadows.
  - **Design Tokens**: 8px radius for cards, 4px for buttons, 12px for modals; 200-300ms transitions; staggered animation delays.
  - **Color Themes**: Portal-specific color differentiation:
    - **Admin Portal**: Purple/indigo theme (indigo-800, purple gradients) for administrative authority
    - **Content Management Portal**: Orange/teal theme (orange-500, teal accents) for content creation
    - **Teacher Portal**: Gray-800 with indigo/purple accents for daily teaching workflows
  - **Modern Components**: Stat cards with gradient icons, progress bars, action cards with hover effects, modern form styling with rounded inputs.
  - **Animation System**: Scale-in animations with staggered delays (delay-100 through delay-400), smooth hover transitions, gradient text effects.
  - **CSS Architecture**: Base modern-dashboard.css for shared design system + portal-specific theme files (admin-theme.css, content-theme.css) for color overrides.
- **Interactive Elements**: Modals, forms, and dropdowns using Alpine.js with smooth transitions.

### Backend Architecture
- **Framework**: Django 5.0 (Python).
- **Application Structure**: Monolithic 'core' Django app.
- **Authentication**: Django's built-in system with custom UserProfile; supports username or email login; token-based email verification.
- **Role-Based Access Control**: `admin`, `content_manager`, `teacher` roles with dedicated portal routing and security decorators.
- **Content Management**: Dedicated Content Portal for content managers to upload (bulk upload with dynamic metadata forms) and manage educational materials.
- **AI Reformatting System**: Extracts and reformats content from PDFs using GPT-4, storing questions/memos in JSON format for review.
- **REST API**: Django REST Framework for mobile app integration, providing public and authentication-required endpoints for content access with filtering and pagination.
- **Feature Management**: Admin interface for managing exam boards, subjects, grades, and subscription plans (pricing, quotas, AI models).
- **Communications System**: Platform-wide announcements (targeted, scheduled, dismissible) and email blast functionality.

### Data Storage Solutions
- **Primary Database**: SQLite (development), designed for PostgreSQL compatibility.
- **Models**: Comprehensive models for user profiles, subscriptions (including `SubscribedSubject` for multi-subject support), educational metadata (`Subject`, `Grade`, `ExamBoard`), content (`PastPaper`, `Quiz`, `FormattedPaper`, `Assignment`), and usage tracking (`UsageQuota` with JSONField for per-subject quotas).
- **File Storage**: Local file system for uploaded documents, with organized directory structures.

### Authentication and Authorization
- **User Types**: Teachers and Admins, with Content Managers as an additional role.
- **Subscription Model**: Freemium with four tiers (Free, Starter, Growth, Premium) dictating subject limits, lesson plan quotas, and AI model access.
  - **Free (R0)**: 1 subject, 2 lesson plans/month, no AI.
  - **Starter (R50)**: 1 subject, 10 lesson plans/month, no AI.
  - **Growth (R100)**: 2 subjects, 20 lesson plans/subject/month, GPT-3.5 AI.
  - **Premium (R250)**: 3 subjects, unlimited lesson plans, GPT-4 AI.
- **Quota Enforcement**: Per-subject, monthly AI generation limits with upgrade prompts.
- **Teacher Codes**: Unique 6-character codes for Google Forms integration.

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