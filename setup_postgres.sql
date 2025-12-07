-- =====================================================
-- EduTech Platform - PostgreSQL Database Setup Script
-- =====================================================
-- 
-- This script creates the database schema for PostgreSQL.
-- 
-- USAGE:
-- 1. Create a PostgreSQL database first:
--    CREATE DATABASE edutech;
-- 
-- 2. Run this script:
--    psql -U your_username -d edutech -f setup_postgres.sql
-- 
-- 3. Set environment variables and run Django migrations:
--    export DATABASE_URL="postgresql://user:password@localhost:5432/edutech"
--    python manage.py migrate
-- 
-- NOTE: It's recommended to use Django migrations instead of this script.
--       This script is provided as a reference for database structure.
-- =====================================================

-- Create database (run this separately as superuser if needed)
-- CREATE DATABASE edutech WITH ENCODING 'UTF8';

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- CORE TABLES
-- =====================================================

-- Exam Boards (Cambridge, Edexcel, CAPS, etc.)
CREATE TABLE IF NOT EXISTS core_examboard (
    id SERIAL PRIMARY KEY,
    name_full VARCHAR(200) NOT NULL,
    abbreviation VARCHAR(10) NOT NULL
);

-- Grades/Levels
CREATE TABLE IF NOT EXISTS core_grade (
    id SERIAL PRIMARY KEY,
    number INTEGER NOT NULL
);

-- Subjects
CREATE TABLE IF NOT EXISTS core_subject (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

-- =====================================================
-- USER TABLES
-- =====================================================

-- Django auth_user table is created by Django migrations
-- This references it for foreign keys

-- User Profiles (extends Django User)
CREATE TABLE IF NOT EXISTS core_userprofile (
    id SERIAL PRIMARY KEY,
    role VARCHAR(10) NOT NULL DEFAULT 'teacher',
    subscription VARCHAR(20) NOT NULL DEFAULT 'free',
    user_id INTEGER NOT NULL UNIQUE REFERENCES auth_user(id) ON DELETE CASCADE
);

-- Student Profiles
CREATE TABLE IF NOT EXISTS core_studentprofile (
    id SERIAL PRIMARY KEY,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    verification_token VARCHAR(100),
    verification_token_created TIMESTAMP WITH TIME ZONE,
    onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,
    parent_email VARCHAR(254),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    user_id INTEGER NOT NULL UNIQUE REFERENCES auth_user(id) ON DELETE CASCADE,
    grade_id INTEGER REFERENCES core_grade(id)
);

-- BrillTech Admin (separate from Django users)
CREATE TABLE IF NOT EXISTS core_brilltechadmin (
    id SERIAL PRIMARY KEY,
    username VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

-- =====================================================
-- CONTENT TABLES
-- =====================================================

-- Uploaded Documents
CREATE TABLE IF NOT EXISTS core_uploadeddocument (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    type VARCHAR(20) NOT NULL,
    file_url VARCHAR(200) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    tags TEXT NOT NULL DEFAULT '[]',
    board_id INTEGER NOT NULL REFERENCES core_examboard(id),
    grade_id INTEGER NOT NULL REFERENCES core_grade(id),
    subject_id INTEGER NOT NULL REFERENCES core_subject(id),
    uploaded_by_id INTEGER NOT NULL REFERENCES auth_user(id)
);

-- Generated Lesson Plans
CREATE TABLE IF NOT EXISTS core_generatedlessonplan (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    source_document VARCHAR(200),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    content JSONB,
    shared_link VARCHAR(500) UNIQUE,
    board_id INTEGER NOT NULL REFERENCES core_examboard(id),
    grade_id INTEGER NOT NULL REFERENCES core_grade(id),
    subject_id INTEGER NOT NULL REFERENCES core_subject(id),
    teacher_id INTEGER NOT NULL REFERENCES auth_user(id)
);

-- Generated Assignments
CREATE TABLE IF NOT EXISTS core_generatedassignment (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    question_type VARCHAR(20) NOT NULL,
    due_date TIMESTAMP WITH TIME ZONE NOT NULL,
    file_url VARCHAR(200) NOT NULL,
    shared_link VARCHAR(500) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    content JSONB,
    board_id INTEGER NOT NULL REFERENCES core_examboard(id),
    grade_id INTEGER NOT NULL REFERENCES core_grade(id),
    subject_id INTEGER NOT NULL REFERENCES core_subject(id),
    teacher_id INTEGER NOT NULL REFERENCES auth_user(id)
);

-- Official Exam Papers
CREATE TABLE IF NOT EXISTS core_officialexampaper (
    id SERIAL PRIMARY KEY,
    paper_type VARCHAR(20) NOT NULL,
    year INTEGER NOT NULL,
    session VARCHAR(20) NOT NULL,
    paper_number VARCHAR(10) NOT NULL,
    variant VARCHAR(10),
    file_url VARCHAR(500) NOT NULL,
    marking_scheme_url VARCHAR(500),
    syllabus_code VARCHAR(20),
    uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    board_id INTEGER NOT NULL REFERENCES core_examboard(id),
    grade_id INTEGER NOT NULL REFERENCES core_grade(id),
    subject_id INTEGER NOT NULL REFERENCES core_subject(id),
    uploaded_by_id INTEGER NOT NULL REFERENCES auth_user(id)
);

-- =====================================================
-- CRM TABLES
-- =====================================================

-- CRM Leads
CREATE TABLE IF NOT EXISTS core_crmlead (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(254) NOT NULL,
    phone VARCHAR(20),
    company VARCHAR(200),
    job_title VARCHAR(100),
    lead_type VARCHAR(20) NOT NULL DEFAULT 'individual',
    source VARCHAR(30) NOT NULL DEFAULT 'website',
    pipeline_stage VARCHAR(20) NOT NULL DEFAULT 'new',
    estimated_value DECIMAL(10, 2),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by_id INTEGER REFERENCES auth_user(id),
    assigned_to_id INTEGER REFERENCES auth_user(id)
);

-- CRM Tasks
CREATE TABLE IF NOT EXISTS core_crmtask (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    priority VARCHAR(10) NOT NULL DEFAULT 'medium',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    due_date DATE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    assigned_to_id INTEGER REFERENCES auth_user(id),
    created_by_id INTEGER REFERENCES auth_user(id),
    related_lead_id INTEGER REFERENCES core_crmlead(id)
);

-- CRM Activities
CREATE TABLE IF NOT EXISTS core_crmactivity (
    id SERIAL PRIMARY KEY,
    activity_type VARCHAR(20) NOT NULL DEFAULT 'note',
    title VARCHAR(200) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by_id INTEGER REFERENCES auth_user(id),
    lead_id INTEGER NOT NULL REFERENCES core_crmlead(id) ON DELETE CASCADE
);

-- CRM Mailing Lists
CREATE TABLE IF NOT EXISTS core_crmmailinglist (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by_id INTEGER REFERENCES auth_user(id)
);

-- CRM Mailing List Subscribers
CREATE TABLE IF NOT EXISTS core_crmmailinglistsubscriber (
    id SERIAL PRIMARY KEY,
    email VARCHAR(254) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    subscribed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    unsubscribed_at TIMESTAMP WITH TIME ZONE,
    mailing_list_id INTEGER NOT NULL REFERENCES core_crmmailinglist(id) ON DELETE CASCADE
);

-- CRM Email Campaigns
CREATE TABLE IF NOT EXISTS core_crmemailcampaign (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    subject VARCHAR(500) NOT NULL,
    body TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    sent_at TIMESTAMP WITH TIME ZONE,
    recipient_count INTEGER NOT NULL DEFAULT 0,
    sent_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by_id INTEGER REFERENCES auth_user(id),
    mailing_list_id INTEGER NOT NULL REFERENCES core_crmmailinglist(id)
);

-- =====================================================
-- SUBSCRIPTION TABLES
-- =====================================================

-- Teacher Subscription Plans
CREATE TABLE IF NOT EXISTS core_subscriptionplan (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    price DECIMAL(10, 2) NOT NULL DEFAULT 0,
    ai_generations_per_month INTEGER NOT NULL DEFAULT 0,
    max_subjects INTEGER NOT NULL DEFAULT 0,
    features JSONB,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Student Subscription Pricing
CREATE TABLE IF NOT EXISTS core_studentsubscriptionpricing (
    id SERIAL PRIMARY KEY,
    per_subject_price DECIMAL(10, 2) NOT NULL DEFAULT 100.00,
    per_subject_max_subjects INTEGER NOT NULL DEFAULT 3,
    bundle_price DECIMAL(10, 2) NOT NULL DEFAULT 200.00,
    bundle_min_subjects INTEGER NOT NULL DEFAULT 4,
    bundle_max_subjects INTEGER NOT NULL DEFAULT 5,
    all_access_price DECIMAL(10, 2) NOT NULL DEFAULT 300.00,
    tutor_addon_price DECIMAL(10, 2) NOT NULL DEFAULT 500.00,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- =====================================================
-- INDEXES
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_crmlead_pipeline ON core_crmlead(pipeline_stage);
CREATE INDEX IF NOT EXISTS idx_crmlead_email ON core_crmlead(email);
CREATE INDEX IF NOT EXISTS idx_crmtask_status ON core_crmtask(status);
CREATE INDEX IF NOT EXISTS idx_crmtask_due_date ON core_crmtask(due_date);
CREATE INDEX IF NOT EXISTS idx_examboard_abbr ON core_examboard(abbreviation);
CREATE INDEX IF NOT EXISTS idx_studentprofile_user ON core_studentprofile(user_id);

-- =====================================================
-- INITIAL DATA
-- =====================================================

-- Default subscription plans
INSERT INTO core_subscriptionplan (name, price, ai_generations_per_month, max_subjects, is_active) VALUES
('Free', 0, 5, 1, TRUE),
('Starter', 99, 50, 3, TRUE),
('Growth', 199, 200, 10, TRUE),
('Premium', 399, -1, -1, TRUE)
ON CONFLICT (name) DO NOTHING;

-- Default exam boards
INSERT INTO core_examboard (name_full, abbreviation) VALUES
('Cambridge International Examinations', 'CIE'),
('Edexcel', 'EDEXCEL'),
('Curriculum and Assessment Policy Statement', 'CAPS'),
('Zimbabwe School Examinations Council', 'ZIMSEC'),
('Independent Examinations Board', 'IEB'),
('Assessment and Qualifications Alliance', 'AQA'),
('Oxford, Cambridge and RSA', 'OCR')
ON CONFLICT DO NOTHING;

-- Default grades
INSERT INTO core_grade (number) VALUES (1), (2), (3), (4), (5), (6), (7), (8), (9), (10), (11), (12)
ON CONFLICT DO NOTHING;

-- Default subjects
INSERT INTO core_subject (name) VALUES
('Mathematics'), ('English'), ('Science'), ('Physics'), ('Chemistry'),
('Biology'), ('Geography'), ('History'), ('Computer Science'), ('Economics'),
('Business Studies'), ('Accounting'), ('Art'), ('Music'), ('Physical Education')
ON CONFLICT DO NOTHING;

-- Default student pricing
INSERT INTO core_studentsubscriptionpricing (id, per_subject_price, bundle_price, all_access_price, tutor_addon_price)
VALUES (1, 100.00, 200.00, 300.00, 500.00)
ON CONFLICT DO NOTHING;

-- =====================================================
-- NOTES
-- =====================================================
-- 
-- After running this script, you should:
-- 1. Run Django migrations: python manage.py migrate
-- 2. Create a superuser: python manage.py createsuperuser
-- 3. Create test accounts if needed
-- 
-- For production, remember to:
-- - Use strong passwords
-- - Enable SSL connections
-- - Set up proper backup procedures
-- - Configure connection pooling (e.g., PgBouncer)
-- =====================================================
