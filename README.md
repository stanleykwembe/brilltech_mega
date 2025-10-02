# EduTech Freemium Teacher Platform

A comprehensive freemium educational technology platform designed for teachers and administrators to create, manage, and share educational content with AI-powered assistance.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Module Documentation](#module-documentation)
- [Technology Stack](#technology-stack)
- [Setup Instructions](#setup-instructions)
- [Deployment Guide](#deployment-guide)
- [Subscription Tiers](#subscription-tiers)
- [API Documentation](#api-documentation)
- [Database Schema](#database-schema)

---

## Overview

The EduTech Freemium Teacher Platform is a Django-based web application that helps teachers create lesson plans, generate assignments, manage documents, and distribute homework to students. The platform integrates OpenAI's GPT-5 for AI-powered content generation and uses PayFast for subscription payments.

**Key Highlights:**
- 🤖 AI-powered lesson plan and homework generation
- 📚 Comprehensive document management system
- 🔗 Shareable assignment links for student distribution
- 💳 PayFast-integrated subscription system with 4 pricing tiers
- ✉️ Email verification for account security
- 📊 Usage analytics and quota tracking

---

## Features

### 1. **User Management & Authentication**
- Teacher and Admin role-based access control
- Email verification system with token-based activation
- Secure password management with reset functionality
- Account settings for profile customization
- Session management

### 2. **AI-Powered Content Generation** (Premium Feature)
- **Lesson Plans**: Generate comprehensive lesson plans with objectives, materials, activities, and assessments
- **Homework/Assignments**: Create custom homework with various question types
- **Question Generator**: Generate practice questions in multiple formats:
  - Multiple Choice Questions (MCQ)
  - Structured/Short Answer
  - Free Response/Essay
  - Cambridge-style Structured Questions

### 3. **Document Management**
- Upload and organize educational documents (PDF, DOCX)
- Categorize by subject, grade, and exam board
- Document types: Lesson Plans, Homework, Past Papers, Sample Questions
- Download and share documents with classes

### 4. **Class & Assignment Management**
- Create and manage class groups
- Share assignments with specific classes
- Generate unique shareable links for each assignment
- Track assignment views and access analytics
- Revoke access to shared assignments
- Set due dates and expiry dates for assignments

### 5. **Subscription System**
- **Free Tier (R0)**: Basic document upload and management
- **Starter Tier (R50/month)**: Enhanced document features (no AI)
- **Growth Tier (R100/month)**: Access to pre-made content library for 1 subject
- **Premium Tier (R250/month)**: Full AI access for unlimited content generation

### 6. **Payment Integration**
- Secure PayFast payment gateway integration
- Signature validation and webhook verification
- Payment history tracking
- Automatic subscription activation
- Support for South African Rand (ZAR) currency

### 7. **Account Settings**
- Personal information management (name, email, institution, bio)
- Password change with current password verification
- Email notification preferences
- Usage statistics dashboard
- Email verification status

---

## System Architecture

### **Backend Architecture**
```
├── Django 5.0 Framework
│   ├── Core App (main business logic)
│   ├── User Authentication & Authorization
│   ├── ORM for Database Management
│   └── Django Admin Interface
├── OpenAI Integration (GPT-5)
├── PayFast Payment Gateway
└── Email Service (Gmail SMTP)
```

### **Frontend Architecture**
```
├── Django Templates (Jinja2)
├── Tailwind CSS (Utility-first styling)
├── Alpine.js (Lightweight JavaScript framework)
├── Font Awesome (Icons)
└── Streamlit (Alternative interface - app.py)
```

### **Data Layer**
```
├── SQLite (Development)
├── PostgreSQL (Production-ready)
├── Django ORM
└── JSON for AI content storage
```

---

## Module Documentation

### **1. Authentication Module** (`core/views.py`)

**Views:**
- `login_view`: Handles user login with email verification check
- `logout_view`: Logs out users and clears session
- `signup_view`: User registration with automatic email verification
- `verify_email`: Token-based email verification
- `resend_verification`: Resends verification email

**Key Features:**
- Inactive users (unverified emails) cannot log in
- Secure token generation for email verification
- Password hashing using Django's built-in system

---

### **2. Content Management Module**

#### **Lesson Plans** (`lesson_plans_view`)
**Functionality:**
- Upload custom lesson plans (PDF/DOCX)
- AI-generated lesson plans with structured JSON output
- Categorization by subject, grade, and exam board
- View, download, and delete lesson plans

**AI Generation Process:**
1. User provides: subject, grade, exam board, topic, duration
2. OpenAI GPT-5 generates structured lesson plan
3. Output includes: objectives, materials, activities, assessment, homework
4. Stored in `UploadedDocument.ai_content` as JSON

#### **Assignments** (`assignments_view`)
**Functionality:**
- Upload existing assignments
- Generate AI-powered homework
- Share assignments with class groups
- Track shared assignments and revoke access

**Assignment Sharing:**
- Unique token-based URLs (32-character secure tokens)
- No login required for students to view assignments
- Teachers can set due dates and expiry dates
- View count tracking and last accessed timestamp

#### **Question Generator** (`questions_view`)
**Functionality:**
- Generate practice questions in 4 formats:
  - MCQ (Multiple Choice)
  - Structured (Short Answer)
  - Free Response (Essay)
  - Cambridge-style Structured
- Specify number of questions and topic
- Export as PDF or view inline

---

### **3. AI Service Module** (`core/openai_service.py`)

**Functions:**

#### `generate_lesson_plan(subject, grade, board, topic, duration)`
- Uses GPT-5 with structured JSON output
- Returns: title, objectives, materials, activities, assessment, homework
- Error handling for API failures

#### `generate_homework(subject, grade, board, topic, question_type, num_questions)`
- Generates homework questions based on type
- Returns: title, instructions, questions array, total marks
- Each question includes: question text, marks, answer guidance

#### `generate_questions(subject, grade, board, topic, question_type, num_questions)`
- Similar to homework generation
- Focused on practice questions
- Supports all 4 question formats

**Configuration:**
- API Key: Stored in environment variable `OPENAI_API_KEY`
- Model: `gpt-5`
- Response Format: JSON object for structured parsing

---

### **4. Class Management Module**

#### **Models:**
- `ClassGroup`: Represents a class/group of students
  - Fields: name, description, subject, grade, teacher, is_active
  - Unique constraint: teacher + class name

- `AssignmentShare`: Links assignments to classes
  - Links to either `GeneratedAssignment` OR `UploadedDocument`
  - Unique token for public access
  - Tracks: view_count, last_accessed, shared_at, expires_at, revoked_at

#### **Views:**
- `classes_view`: List all classes for a teacher
- `create_class`: Create new class group
- `edit_class`: Update class details
- `delete_class`: Soft delete (marks inactive)
- `create_share`: Share assignment with class
- `revoke_share`: Revoke access to shared assignment
- `public_assignment_view`: Public view for students (no login)
- `public_assignment_download`: Download shared assignment

**Security Features:**
- Teachers can only share their own assignments
- Teachers can only share to their own classes
- Token-based access (no student accounts needed)
- Automatic expiry checking
- Revocation capability

---

### **5. Subscription & Payment Module**

#### **Models:**

**SubscriptionPlan:**
- Defines 4 pricing tiers
- Feature flags: `can_upload_documents`, `can_use_ai`, `can_access_library`
- Quotas: `monthly_ai_generations`, `allowed_subjects_count`

**UserSubscription:**
- Tracks user's current plan
- Status: active, cancelled, expired, pending
- Period tracking: `current_period_start`, `current_period_end`
- Selected subject (for Growth plan)

**PayFastPayment:**
- Records all payment transactions
- Stores PayFast payment ID, merchant ID, amounts
- ITN (Instant Transaction Notification) data storage

#### **PayFast Service** (`core/payfast_service.py`)

**Key Functions:**

`generate_signature(data_dict, passphrase)`:
- Creates MD5 signature for payment validation
- URL-encodes parameters in alphabetical order
- Adds passphrase for security

`generate_payment_form_data(user, plan, subscription)`:
- Creates payment form fields for PayFast
- Includes: merchant details, user info, amounts, callback URLs
- Custom fields for tracking: user_id, plan_id, subscription_id

`validate_signature(post_data, passphrase)`:
- Verifies PayFast webhook signatures
- Prevents payment tampering

`validate_server_confirmation(post_data)`:
- Server-to-server verification with PayFast
- Ensures payment legitimacy

**Security Layers:**
1. Signature validation (MD5 hash)
2. Server confirmation (HTTP request to PayFast)
3. IP validation (PayFast IP whitelist)
4. Merchant ID verification
5. Amount verification

#### **Subscription Views:**

`subscription_dashboard`:
- Display current plan and features
- Show payment history
- List upgrade/downgrade options
- Subject selection for Growth plan

`initiate_subscription`:
- Create PayFastPayment record
- Generate payment form with signature
- Redirect to PayFast payment page

`payfast_notify` (Webhook):
- Receives PayFast ITN notifications
- Validates signature and merchant ID
- Verifies payment with server confirmation
- Activates subscription on successful payment
- Updates payment status

`payment_success`:
- User redirect after successful payment
- Displays confirmation message

`payment_cancelled`:
- User redirect after cancelled payment

---

### **6. Subscription Utilities** (`core/subscription_utils.py`)

**Functions:**

`get_user_subscription(user)`:
- Retrieves or creates user subscription
- Auto-assigns Free plan to new users

`user_has_feature(user, feature)`:
- Checks if user's plan includes a feature
- Features: 'upload_documents', 'use_ai', 'access_library'

`require_subscription_feature(feature)`:
- Decorator to protect views by feature
- Redirects to subscription page if access denied

`require_premium`:
- Shortcut decorator for AI features
- Requires 'use_ai' feature (Premium plan)

**Usage Example:**
```python
@require_premium
def generate_assignment_ai(request):
    # Only Premium users can access this
    ...
```

---

### **7. Document Management Module**

#### **Models:**

**UploadedDocument:**
- Stores both uploaded and AI-generated content
- Fields:
  - `uploaded_by`: User who created it
  - `title`, `subject`, `grade`, `board`
  - `type`: lesson_plan, homework, past_paper, sample_questions
  - `file`: Actual file upload (PDF/DOCX)
  - `ai_content`: JSON field for AI-generated content
  - `tags`: For categorization
  - `created_at`: Timestamp

**File Operations:**
- `delete_document`: Delete document and file
- `download_document`: Download file with proper MIME type
- `view_document`: Display document metadata
- `view_document_inline`: Inline PDF viewer

---

### **8. Account Settings Module**

**View:** `account_settings`

**Features:**

1. **Profile Management:**
   - Update first name, last name, email
   - Add institution/school name
   - Write bio
   - Email uniqueness validation

2. **Security:**
   - Change password with current password verification
   - 8+ character minimum password requirement
   - Session preservation after password change (using `update_session_auth_hash`)

3. **Email & Notifications:**
   - Display email verification status
   - Resend verification email
   - Toggle email notifications on/off

4. **Usage Statistics:**
   - Total AI generations count
   - Documents created count
   - Assignments created count
   - Assignments shared count

**Template:** Tabbed interface with Alpine.js
- Profile & Personal Info tab
- Security tab
- Email & Notifications tab
- Usage Statistics tab

---

## Technology Stack

### **Backend:**
- **Python 3.10+**
- **Django 5.0** - Web framework
- **OpenAI Python SDK 1.108+** - AI integration
- **PostgreSQL / SQLite** - Database
- **python-dotenv** - Environment management

### **Frontend:**
- **Tailwind CSS** - Utility-first CSS framework
- **Alpine.js** - Lightweight JavaScript framework
- **Font Awesome** - Icon library
- **Django Templates** - Server-side rendering

### **Third-Party Services:**
- **OpenAI GPT-5** - AI content generation
- **PayFast** - Payment gateway (South African)
- **Gmail SMTP** - Email service

### **File Handling:**
- **python-docx** - DOCX file processing
- **PyPDF2** - PDF file processing
- **Pillow** - Image processing
- **ReportLab** - PDF generation

### **Additional Libraries:**
- **Requests** - HTTP library
- **Streamlit** - Alternative UI framework
- **Stripe** - (Alternative payment option)

---

## Setup Instructions

### **1. Download the Project**
From Replit:
1. Click the three dots menu (⋯) in the top-right
2. Select "Download as ZIP"
3. Extract the ZIP file to your local machine

### **2. Install Dependencies**

**Using pip (recommended):**
```bash
pip install -r requirements.txt
```

**Or using Poetry:**
```bash
poetry install
```

### **3. Environment Variables**
Create a `.env` file in the project root:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (for PostgreSQL)
DATABASE_URL=postgresql://user:password@localhost:5432/edutech

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Email Configuration
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# PayFast Configuration
PAYFAST_MERCHANT_ID=your-merchant-id
PAYFAST_MERCHANT_KEY=your-merchant-key
PAYFAST_PASSPHRASE=your-passphrase
PAYFAST_URL=https://sandbox.payfast.co.za/eng/process
SITE_URL=http://localhost:8000
```

### **4. Database Setup**

**Run migrations:**
```bash
python manage.py migrate
```

**Create superuser (admin):**
```bash
python manage.py createsuperuser
```

**Seed subscription plans:**
```bash
python manage.py seed_plans
```

This creates the 4 default plans:
- Free (R0)
- Starter (R50)
- Growth (R100)
- Premium (R250)

### **5. Run the Development Server**

**Django:**
```bash
python manage.py runserver 0.0.0.0:5000
```

**Streamlit (alternative):**
```bash
streamlit run app.py
```

### **6. Access the Application**

- **Web Interface:** http://localhost:5000
- **Admin Panel:** http://localhost:5000/admin
- **Streamlit:** http://localhost:8501

---

## Deployment Guide

### **Option 1: Deploy on Replit**
The app is already configured for Replit:
1. Click "Publish" in Replit
2. Configure custom domain (optional)
3. Environment variables are already set

### **Option 2: Deploy on Railway/Render**

**1. Update settings for production:**
```python
# django_project/settings.py
DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com']
```

**2. Use PostgreSQL:**
```bash
pip install psycopg2-binary
```

**3. Configure static files:**
```bash
python manage.py collectstatic
```

**4. Use Gunicorn:**
```bash
pip install gunicorn
gunicorn django_project.wsgi:application --bind 0.0.0.0:8000
```

### **Option 3: Deploy on Heroku**

**1. Create `Procfile`:**
```
web: gunicorn django_project.wsgi --log-file -
```

**2. Create `runtime.txt`:**
```
python-3.10.12
```

**3. Push to Heroku:**
```bash
heroku create your-app-name
git push heroku main
heroku run python manage.py migrate
heroku run python manage.py createsuperuser
heroku run python manage.py seed_plans
```

### **Production Checklist:**
- [ ] Set `DEBUG = False`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Use PostgreSQL database
- [ ] Set secure `SECRET_KEY`
- [ ] Configure HTTPS
- [ ] Set up proper email backend
- [ ] Update PayFast to production credentials
- [ ] Configure static files serving (WhiteNoise or CDN)
- [ ] Enable CSRF protection
- [ ] Set up logging and monitoring
- [ ] Configure backup strategy

---

## Subscription Tiers

| Feature | Free | Starter | Growth | Premium |
|---------|------|---------|--------|---------|
| **Price** | R0 | R50/month | R100/month | R250/month |
| **Upload Documents** | ✅ | ✅ | ✅ | ✅ |
| **AI Generation** | ❌ | ❌ | ❌ | ✅ |
| **Content Library** | ❌ | ❌ | ✅ (1 subject) | ✅ (All) |
| **Monthly AI Generations** | 0 | 0 | 0 | Unlimited |
| **Document Storage** | Limited | Enhanced | Enhanced | Unlimited |
| **Class Management** | ✅ | ✅ | ✅ | ✅ |
| **Assignment Sharing** | ✅ | ✅ | ✅ | ✅ |

---

## API Documentation

### **Authentication Endpoints**

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET/POST | `/login/` | User login | No |
| GET | `/logout/` | User logout | Yes |
| POST | `/signup/` | User registration | No |
| GET | `/verify-email/<token>/` | Email verification | No |
| POST | `/resend-verification/` | Resend verification email | Yes |

### **Content Management Endpoints**

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET/POST | `/` | Dashboard | Yes |
| GET/POST | `/lesson-plans/` | Lesson plans management | Yes |
| GET/POST | `/assignments/` | Assignments management | Yes |
| GET/POST | `/questions/` | Question generator | Yes |
| GET/POST | `/documents/` | Document library | Yes |

### **AI Generation Endpoints**

| Method | Endpoint | Description | Auth Required | Plan Required |
|--------|----------|-------------|---------------|---------------|
| POST | `/generate-assignment/` | Generate AI assignment | Yes | Premium |
| POST | `/generate-questions/` | Generate AI questions | Yes | Premium |

### **Document Operations**

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/document/<id>/delete/` | Delete document | Yes |
| GET | `/document/<id>/download/` | Download document | Yes |
| GET | `/document/<id>/view/` | View document details | Yes |
| GET | `/document/<id>/inline/` | View document inline | Yes |

### **Class Management Endpoints**

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/classes/` | List classes | Yes |
| POST | `/classes/create/` | Create class | Yes |
| POST | `/classes/<id>/edit/` | Edit class | Yes |
| POST | `/classes/<id>/delete/` | Delete class | Yes |

### **Assignment Sharing Endpoints**

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/assignments/share/create/` | Share assignment | Yes |
| POST | `/assignments/share/<id>/revoke/` | Revoke share | Yes |
| GET | `/share/a/<token>/` | View shared assignment | No |
| GET | `/share/a/<token>/download/` | Download shared assignment | No |

### **Subscription & Payment Endpoints**

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/subscription/dashboard/` | Subscription dashboard | Yes |
| POST | `/subscription/initiate/<plan_id>/` | Initiate payment | Yes |
| POST | `/payfast/notify/` | PayFast webhook (ITN) | No |
| GET | `/payment/success/` | Payment success redirect | Yes |
| GET | `/payment/cancelled/` | Payment cancelled redirect | Yes |

### **Account Settings**

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET/POST | `/account/settings/` | Account settings | Yes |

---

## Database Schema

### **Core Models**

#### **User & Profile**
```
User (Django built-in)
├── username
├── email
├── password
└── is_active

UserProfile
├── user (FK → User)
├── role (teacher/admin)
├── subscription (legacy field)
├── email_verified
├── verification_token
├── bio
├── institution
└── email_notifications
```

#### **Educational Metadata**
```
Subject
└── name

Grade
└── number

ExamBoard
├── name_full
└── abbreviation
```

#### **Content Management**
```
UploadedDocument
├── uploaded_by (FK → User)
├── title
├── subject (FK → Subject)
├── grade (FK → Grade)
├── board (FK → ExamBoard)
├── type (lesson_plan/homework/past_paper/sample_questions)
├── file (FileField)
├── ai_content (JSONField)
├── created_at
└── tags

GeneratedAssignment
├── teacher (FK → User)
├── title
├── subject (FK → Subject)
├── grade (FK → Grade)
├── board (FK → ExamBoard)
├── question_type
├── due_date
├── file_url
├── instructions
├── shared_link (unique token)
├── created_at
└── content (JSONField)
```

#### **Usage Tracking**
```
UsageQuota
├── user (FK → User)
├── lesson_plans_used (JSONField)
└── assignments_used (JSONField)
```

#### **Class Management**
```
ClassGroup
├── teacher (FK → User)
├── name
├── description
├── subject (FK → Subject)
├── grade (FK → Grade)
├── created_at
└── is_active

AssignmentShare
├── teacher (FK → User)
├── class_group (FK → ClassGroup)
├── generated_assignment (FK → GeneratedAssignment, nullable)
├── uploaded_document (FK → UploadedDocument, nullable)
├── token (unique)
├── shared_at
├── due_date
├── expires_at
├── revoked_at
├── view_count
├── last_accessed
└── notes
```

#### **Subscription & Payments**
```
SubscriptionPlan
├── name
├── plan_type (free/starter/growth/premium)
├── price
├── billing_period
├── can_upload_documents
├── can_use_ai
├── can_access_library
├── allowed_subjects_count
├── monthly_ai_generations
├── description
└── is_active

UserSubscription
├── user (FK → User)
├── plan (FK → SubscriptionPlan)
├── status (active/cancelled/expired/pending)
├── started_at
├── current_period_start
├── current_period_end
├── cancelled_at
├── payfast_token
└── selected_subject (FK → Subject)

PayFastPayment
├── user (FK → User)
├── subscription (FK → UserSubscription)
├── plan (FK → SubscriptionPlan)
├── payfast_payment_id (unique)
├── merchant_id
├── amount_gross
├── amount_fee
├── amount_net
├── status
├── payment_status_text
├── itn_data (JSONField)
├── created_at
└── completed_at
```

---

## Security Features

### **1. Authentication & Authorization**
- Email verification required for account activation
- Role-based access control (Teacher/Admin)
- Secure password hashing (Django's PBKDF2)
- Session-based authentication
- CSRF protection on all forms

### **2. Payment Security**
- PayFast signature validation (MD5 hash)
- Server-to-server payment confirmation
- IP whitelisting for webhook endpoints
- Merchant ID verification
- Amount verification to prevent tampering

### **3. Data Protection**
- Teacher can only access their own data
- Ownership validation on all CUD operations
- Unique constraints on critical data
- File upload validation
- SQL injection protection (Django ORM)

### **4. Content Sharing Security**
- Unique 32-character tokens for shares
- Expiry date enforcement
- Revocation capability
- View count tracking
- Teacher ownership validation

---

## Future Enhancements

### **Planned Features:**
1. **Content Protection:**
   - Watermarking on AI-generated content
   - Download limits per user
   - Usage analytics for suspicious activity
   - Expiring share links (auto-expire after 30 days)

2. **Collaboration:**
   - Teacher-to-teacher content sharing
   - Department/school-wide content libraries
   - Collaborative lesson planning

3. **Analytics:**
   - Student performance tracking
   - Assignment completion rates
   - Content usage analytics
   - Teacher engagement metrics

4. **Mobile App:**
   - React Native mobile application
   - Offline access to downloaded content
   - Push notifications

5. **Institutional Plans:**
   - School/district licensing
   - Bulk user management
   - Custom branding
   - Advanced analytics

---

## Support & Documentation

### **Admin Access:**
- **Admin Panel:** `/admin/`
- **Default Admin:** username: `admin`, password: `admin123`

### **Test Accounts:**
- **Teacher Account:** username: `stancho`, email: `skwembe@gmail.com`

### **Environment:**
- **Development:** SQLite database
- **Production:** PostgreSQL (recommended)

### **Key Configuration Files:**
- `django_project/settings.py` - Django settings
- `core/urls.py` - URL routing
- `core/models.py` - Database models
- `core/views.py` - Business logic
- `core/openai_service.py` - AI integration
- `core/payfast_service.py` - Payment processing

### **Logging:**
- Check Django logs for errors
- PayFast webhook logs in PayFastPayment model
- Email verification logs in console

---

## Contributing

### **Development Workflow:**
1. Fork the repository
2. Create feature branch: `git checkout -b feature/your-feature`
3. Make changes and test locally
4. Run migrations: `python manage.py makemigrations && python manage.py migrate`
5. Test all features
6. Commit changes: `git commit -m "Add your feature"`
7. Push to branch: `git push origin feature/your-feature`
8. Create Pull Request

### **Code Standards:**
- Follow PEP 8 style guide
- Use meaningful variable names
- Add comments for complex logic
- Write docstrings for functions
- Keep views focused and clean
- Use Django best practices

---

## License

This project is proprietary software. All rights reserved.

---

## Contact & Support

For questions, issues, or feature requests:
- **Email:** support@edutech.co.za
- **Documentation:** See this README
- **Admin Panel:** `/admin/` for backend management

---

**Built with ❤️ for teachers by teachers**
