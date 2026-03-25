# EduTech Platform - PythonAnywhere Deployment Guide

This guide walks you through deploying the EduTech Django application on PythonAnywhere.

## Prerequisites

- A PythonAnywhere account (free or paid)
- Your project code (via GitHub or zip file)
- Gmail account for SMTP (works on free tier)

---

## Step 1: Create a PythonAnywhere Account

1. Go to [pythonanywhere.com](https://www.pythonanywhere.com)
2. Sign up for a free account (or paid for more resources)
3. Your site will be available at: `yourusername.pythonanywhere.com`

---

## Step 2: Upload Your Code

### Option A: Using Git (Recommended)

1. Open a **Bash console** from the PythonAnywhere dashboard
2. Clone your repository:
   ```bash
   git clone https://github.com/yourusername/your-repo.git
   ```

### Option B: Upload ZIP File

1. Go to the **Files** tab
2. Upload your project as a zip file
3. Open a Bash console and unzip:
   ```bash
   unzip your-project.zip
   ```

---

## Step 3: Create a Virtual Environment

In the Bash console:

```bash
# Navigate to your project folder
cd your-project-folder

# Create virtual environment with Python 3.10
mkvirtualenv --python=/usr/bin/python3.10 edutech-env

# Activate it (if not already active)
workon edutech-env

# Install dependencies
pip install -r requirements.txt
```

---

## Step 4: Set Up MySQL Database (Free Tier)

PythonAnywhere provides free MySQL databases.

### Create the Database:

1. Go to the **Databases** tab
2. Set a MySQL password (save this!)
3. Create a new database called `yourusername$edutech`

### Update Django Settings:

Create or edit a file for PythonAnywhere-specific settings. Add this to your `django_project/settings.py` or create a separate `settings_pythonanywhere.py`:

```python
# Database configuration for PythonAnywhere
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'yourusername$edutech',
        'USER': 'yourusername',
        'PASSWORD': 'your-mysql-password',
        'HOST': 'yourusername.mysql.pythonanywhere-services.com',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}
```

### Install MySQL Client:

```bash
pip install mysqlclient
```

If mysqlclient fails, try:
```bash
pip install pymysql
```

Then add to `django_project/__init__.py`:
```python
import pymysql
pymysql.install_as_MySQLdb()
```

---

## Step 5: Configure Environment Variables

### Option A: Using a .env file

1. Create `.env` file in your project root:
   ```
   SECRET_KEY=your-secret-key-here
   DEBUG=False
   EMAIL_HOST_USER=your-gmail@gmail.com
   EMAIL_HOST_PASSWORD=your-app-password
   OPENAI_API_KEY=your-openai-key
   ```

2. Install python-dotenv:
   ```bash
   pip install python-dotenv
   ```

3. Add to top of `django_project/settings.py`:
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```

### Option B: Using PythonAnywhere Environment Variables

1. Go to the **Web** tab
2. Scroll to **Virtualenv** section
3. Click on the WSGI configuration file link
4. Add environment variables at the top of the WSGI file:
   ```python
   import os
   os.environ['SECRET_KEY'] = 'your-secret-key'
   os.environ['DEBUG'] = 'False'
   os.environ['EMAIL_HOST_USER'] = 'your-gmail@gmail.com'
   os.environ['EMAIL_HOST_PASSWORD'] = 'your-app-password'
   os.environ['OPENAI_API_KEY'] = 'your-openai-key'
   ```

---

## Step 6: Configure the Web App

### Create Web App:

1. Go to the **Web** tab
2. Click **Add a new web app**
3. Choose **Manual configuration** (not Django)
4. Select **Python 3.10**

### Configure WSGI File:

1. Click on the WSGI configuration file link (e.g., `/var/www/yourusername_pythonanywhere_com_wsgi.py`)
2. Delete everything and replace with:

```python
import os
import sys

# Add your project directory to the sys.path
project_home = '/home/yourusername/your-project-folder'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables
os.environ['DJANGO_SETTINGS_MODULE'] = 'django_project.settings'
os.environ['SECRET_KEY'] = 'your-very-secure-secret-key-here'
os.environ['DEBUG'] = 'False'
os.environ['EMAIL_HOST_USER'] = 'your-gmail@gmail.com'
os.environ['EMAIL_HOST_PASSWORD'] = 'your-gmail-app-password'
os.environ['OPENAI_API_KEY'] = 'your-openai-api-key'

# Activate your virtual environment
activate_this = '/home/yourusername/.virtualenvs/edutech-env/bin/activate_this.py'
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

# Import Django WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

**Important:** Replace `yourusername` and `your-project-folder` with your actual values.

### Set Virtual Environment Path:

1. In the **Web** tab, scroll to **Virtualenv**
2. Enter: `/home/yourusername/.virtualenvs/edutech-env`

### Set Static Files:

1. In the **Web** tab, scroll to **Static files**
2. Add these mappings:

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/yourusername/your-project-folder/staticfiles/` |
| `/media/` | `/home/yourusername/your-project-folder/media/` |

---

## Step 7: Update Django Settings for Production

Edit `django_project/settings.py`:

```python
# Security settings for production
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = [
    'yourusername.pythonanywhere.com',
    'www.yourusername.pythonanywhere.com',
]

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# HTTPS settings (PythonAnywhere provides free SSL)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

---

## Step 8: Run Migrations and Collect Static Files

In the Bash console:

```bash
# Activate virtual environment
workon edutech-env

# Navigate to project
cd your-project-folder

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser (for admin access)
python manage.py createsuperuser
```

---

## Step 9: Email Configuration (Gmail SMTP)

Gmail SMTP works on PythonAnywhere free tier. Make sure these settings are in your `settings.py`:

```python
# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
```

**Important:** You need a Gmail App Password, not your regular password:
1. Go to Google Account > Security > 2-Step Verification (enable it)
2. Go to App Passwords
3. Create a new app password for "Mail"
4. Use this 16-character password as `EMAIL_HOST_PASSWORD`

---

## Step 10: Reload and Test

1. Go to the **Web** tab
2. Click the green **Reload** button
3. Visit `https://yourusername.pythonanywhere.com`

---

## Troubleshooting

### Check Error Logs:

1. Go to the **Web** tab
2. Click on **Error log** link
3. Look for error messages

### Common Issues:

| Problem | Solution |
|---------|----------|
| 500 Server Error | Check error log, usually a settings or import issue |
| Static files not loading | Run `collectstatic` and check static file mapping |
| Database errors | Verify MySQL credentials and run migrations |
| Module not found | Make sure all packages are installed in virtual environment |
| CSRF errors | Add your domain to ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS |

### CSRF Configuration:

Add to `settings.py`:
```python
CSRF_TRUSTED_ORIGINS = [
    'https://yourusername.pythonanywhere.com',
]
```

---

## Updating Your App

When you make changes to your code:

```bash
# In Bash console
cd your-project-folder
git pull  # if using git

# If dependencies changed
pip install -r requirements.txt

# If models changed
python manage.py migrate

# If static files changed
python manage.py collectstatic --noinput
```

Then click **Reload** in the Web tab.

---

## Free Tier Limitations

- CPU seconds: Limited daily quota
- MySQL database only (no PostgreSQL)
- 512MB storage
- No scheduled tasks (cron)
- No outbound connections except whitelisted sites (Gmail is whitelisted)
- Site sleeps after 3 months of inactivity on free tier

For production use, consider upgrading to a paid plan ($5/month) for:
- More CPU seconds
- No sleep timeout
- Scheduled tasks
- Full internet access
- Custom domains

---

## Quick Reference

| Item | Value |
|------|-------|
| Project Path | `/home/yourusername/your-project-folder` |
| Virtual Env | `/home/yourusername/.virtualenvs/edutech-env` |
| WSGI File | `/var/www/yourusername_pythonanywhere_com_wsgi.py` |
| MySQL Host | `yourusername.mysql.pythonanywhere-services.com` |
| Site URL | `https://yourusername.pythonanywhere.com` |
