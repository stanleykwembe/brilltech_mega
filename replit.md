# EduTech Freemium Teacher Platform

## Overview

This is a freemium educational technology platform designed for teachers and administrators to create, manage, and share educational content. The application combines AI-powered content generation with document management capabilities, offering features like lesson plan creation, homework/assignment generation, question generation in multiple formats, and document upload/sharing functionality. The platform operates on a freemium model with usage quotas and subscription tiers.

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
  - User management (UserProfile, UsageQuota)
  - Educational metadata (Subject, Grade, ExamBoard)
  - Content management (UploadedDocument, GeneratedAssignment)
- **File Storage**: Local file system with organized directory structure for uploaded documents

### Authentication and Authorization
- **User Types**: Teachers and Admins with role-based access control
- **Email Verification**: Token-based email verification system for new accounts
- **Session Management**: Django's built-in session framework
- **Subscription Control**: Freemium model with usage quotas and tier-based feature access

### AI Integration Architecture
- **Service Layer**: Dedicated OpenAI service module (core/openai_service.py)
- **Model**: GPT-5 for content generation
- **Content Types**: Lesson plans, homework assignments, and questions in multiple formats (MCQ, Structured, Free Response, Cambridge-style)
- **Response Format**: Structured JSON responses for consistent data handling

## External Dependencies

### Third-Party Services
- **OpenAI API**: GPT-5 integration for AI-powered content generation
- **Email Service**: Django's email backend for user verification and notifications

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