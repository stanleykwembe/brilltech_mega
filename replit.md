# EduTech Freemium Multi-Portal Platform

## Overview

This project is a comprehensive freemium educational technology platform designed to serve three distinct user groups: Teachers & Admins, Students, and Content Managers. It facilitates content creation, interactive learning, and curriculum management with AI-powered features. The platform utilizes a freemium model with separate subscription tiers for teachers and students, offering extensive free access alongside premium features to enhance educational experiences. Its ambition is to provide a versatile and engaging learning environment, leveraging AI to simplify content generation and personalize student pathways.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### UI/UX Design
The platform features a modern design inspired by Windows 11 and iPhone aesthetics, incorporating glassmorphism, gradient backgrounds, smooth animations, and multi-layer shadows. It utilizes an 8px radius for cards, 4px for buttons, and 12px for modals, with 200-300ms transitions. Color themes are portal-specific: purple/indigo for Admin, orange/teal for Content Management, gray with indigo/purple accents for Teacher, and green/blue for Student. Frontend is built with Streamlit (main app), Django templates, Tailwind CSS, Alpine.js for interactivity, and GSAP for animations.

### Technical Implementation
The backend is powered by Django 5.0, structured as a monolithic 'core' Django app. It features distinct authentication systems for Teachers/Admins and Students, with role-based access control for `admin`, `content_manager`, and `teacher` roles. A robust portal redirection system ensures users are routed to their appropriate dashboards. Key features include:

- **Landing Pages**: Dedicated marketing pages for teachers and students with dynamic content and animations.
- **Public Papers Page**: Offers free access to exam papers with AJAX filters, lazy-loading, and ad integration.
- **Content Management Portal**: Allows content managers to upload and manage various educational materials, including official exam papers, interactive questions (MCQ, True-False, Fill-blank, Matching, Essay), notes, and flashcards. Supports bulk uploads and parsing for multiple exam boards (Cambridge, Edexcel, CAPS, ZIMSEC, IEB, AQA, OCR).
- **Teacher Portal**: Enables teachers to create and share content, with AI integration for generating lesson plans and assignments from PDFs.
- **Student Portal**: Provides an interactive learning environment with quizzes, notes, flashcards, and exam preparation. Features a multi-step onboarding process, progress tracking, and a pathway-based navigation system for studying, revising, and accessing information. Quizzes support auto-marking for MCQs and AI-assisted marking for structured questions.
- **AI Integration**: A dedicated service layer (`core/openai_service.py`) handles all AI interactions, supporting content generation for lesson plans, homework, and various question types, with model selection based on subscription tiers (GPT-3.5-turbo, GPT-4). AI-generated content is returned in structured JSON format.
- **REST API**: A comprehensive Django REST Framework API is provided for mobile applications, offering endpoints for students (authentication, quizzes, notes, flashcards, exam papers, progress tracking) and teachers (content access, document sharing), including offline support and Swagger/ReDoc documentation.
- **Feature Management**: An admin interface manages exam boards, subjects, grades, and subscription plans.
- **Communications**: Platform-wide announcements and email blast functionality.

### Data Storage
- **Database**: SQLite for development, designed for PostgreSQL compatibility.
- **Models**: Comprehensive models cover Teacher and Student systems, Official Exam Papers, and shared entities like Subject, Grade, ExamBoard.
- **File Storage**: Local file system, organized by content type (documents, notes, flashcards, exam papers) and date.

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
- **Streamlit**: For specific application interfaces.
- **OpenAI Python SDK**: Python client for the OpenAI API.
- **Django REST Framework**: For building RESTful APIs.
- **PyPDF2**: For PDF text extraction.