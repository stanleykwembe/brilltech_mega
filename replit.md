# EduTech Freemium Teacher Platform

## Overview

This is a freemium educational technology platform designed for teachers and administrators to create, manage, and share educational content. The application combines AI-powered content generation with document management capabilities, offering features like lesson plan creation, homework/assignment generation, question generation in multiple formats, and document upload/sharing functionality. The platform operates on a freemium model with usage quotas and subscription tiers.

## Recent Changes

### October 22, 2025
- **Subscription System Overhaul**: Implemented subject-based resource allocation system
  - Updated subscription tiers: Free (R0), Starter (R50), Growth (R100), Premium (R250)
  - Subject limits per tier: 1/1/2/3 subjects respectively
  - Lesson plan quotas: 2/10/20/unlimited per subject per month
  - Created SubscribedSubject model for multi-subject support
  - Added teacher_code generation for Google Forms integration
  
- **Subject Selection UI**: Built comprehensive subject management
  - Subject selection during signup (1 subject for free tier)
  - Subject management in account settings with dynamic tier-based limits
  - Real-time validation and upgrade prompts using Alpine.js
  
- **Resource Filtering**: Implemented subject-based filtering across platform
  - All resources (lesson plans, assignments, documents) filtered by user's subscribed subjects
  - Validation prevents creating resources for non-subscribed subjects
  - Only subscribed subjects shown in dropdowns and selection interfaces
  
- **Quota Enforcement**: Added per-subject AI generation limits
  - Pre-generation checks validate quota before AI calls
  - Per-subject usage tracking with JSONField storage
  - Clear error messages with upgrade prompts when limits reached
  - Treats 0 limit as unlimited for Premium tier
  
- **AI Model Differentiation**: Tier-based AI model selection
  - Growth tier uses GPT-3.5-turbo (basic AI)
  - Premium tier uses GPT-4 (advanced AI)
  - Applied across all AI features (lesson plans, homework, questions)
  
- **Question Bank Models**: Created admin question management system
  - PastPaper model with exam board, grade, subject, chapter, section hierarchy
  - Quiz model with free/premium status and Google Forms integration
  - QuizResponse model for tracking student performance

### October 21, 2025
- **Enhanced Login Experience**: Updated login to accept both username and email for authentication
  - Smart detection of email vs username (checks for "@" symbol with fallback)
  - Updated UI label to "Username or Email" with helpful placeholder text
  - Improved error messaging for better UX without compromising security
- **Improved Message System**: Enhanced Django messages framework display
  - Auto-dismiss messages after 5 seconds
  - Manual close buttons with smooth transitions
  - Better visual styling with icons (check/exclamation/info)
  - Prevents message accumulation in the UI
- **Session Cleanup**: Cleared accumulated test messages from development

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Framework**: Streamlit for the main application interface with Django templates for web views
- **UI Framework**: Tailwind CSS for responsive design and styling
- **JavaScript**: Alpine.js for interactive components and form handling
- **Icons**: Font Awesome for consistent iconography

### Backend Architecture
- **Framework**: Django 5.0 with Python as the primary backend technology
- **Application Structure**: Single Django app called 'core' containing all business logic
- **Authentication**: Django's built-in authentication system with custom UserProfile model
- **File Handling**: Django's default file storage for document uploads
- **API Design**: Django views handling both web pages and AJAX endpoints for AI generation

### Data Storage Solutions
- **Primary Database**: SQLite (development) with Django ORM
- **Models Structure**:
  - User management (UserProfile with subscription and teacher_code, UsageQuota with per-subject tracking)
  - Subscription management (SubscribedSubject for multi-subject support, SubscriptionPlan with tier definitions)
  - Educational metadata (Subject, Grade, ExamBoard)
  - Content management (UploadedDocument, GeneratedAssignment)
  - Question Bank (PastPaper, Quiz, QuizResponse with hierarchical organization)
- **File Storage**: Local file system with organized directory structure for uploaded documents
- **Quota Tracking**: JSONField-based per-subject quota storage in UsageQuota model

### Authentication and Authorization
- **User Types**: Teachers and Admins with role-based access control
- **Email Verification**: Token-based email verification system for new accounts
- **Session Management**: Django's built-in session framework
- **Subscription Control**: Subject-based freemium model with four tiers
  - Free (R0): 1 subject, 2 lesson plans/month, no AI
  - Starter (R50): 1 subject, 10 lesson plans/month, no AI
  - Growth (R100): 2 subjects, 20 lesson plans/subject/month, GPT-3.5 AI
  - Premium (R250): 3 subjects, unlimited lesson plans, GPT-4 AI
- **Teacher Codes**: Unique 6-character codes for Google Forms integration and analytics

### AI Integration Architecture
- **Service Layer**: Dedicated OpenAI service module (core/openai_service.py)
- **Model Selection**: Tier-based AI model differentiation
  - Growth tier: GPT-3.5-turbo (basic AI with quotas)
  - Premium tier: GPT-4 (advanced AI, unlimited)
  - Free/Starter tiers: No AI access
- **Content Types**: Lesson plans, homework assignments, and questions in multiple formats (MCQ, Structured, Free Response, Cambridge-style)
- **Response Format**: Structured JSON responses for consistent data handling
- **Quota Management**: Per-subject monthly limits with automatic enforcement

## External Dependencies

### Third-Party Services
- **OpenAI API**: Tier-based AI integration (GPT-3.5-turbo for Growth, GPT-4 for Premium)
- **Email Service**: Django's email backend for user verification and notifications
- **PayFast** (pending): Payment gateway integration for R50/R100/R250 subscriptions

### Frontend Libraries
- **Tailwind CSS**: Utility-first CSS framework for styling
- **Alpine.js**: Lightweight JavaScript framework for interactivity
- **Font Awesome**: Icon library for UI elements

### Python Packages
- **Django 5.0**: Web framework and ORM
- **Streamlit**: Alternative interface framework
- **OpenAI Python SDK**: Official OpenAI API client library

### File Format Support
- **Document Formats**: PDF and DOCX for uploads and downloads
- **Image Support**: Standard web formats for document previews
- **Export Formats**: JSON for AI-generated content structure

### Development Environment
- **Hosting Platform**: Replit with specific CSRF and domain configurations
- **Database**: SQLite for development (designed to be PostgreSQL-compatible for production)
- **Static Files**: Django's static file handling for CSS, JavaScript, and media assets