from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib import messages

User = get_user_model()

def admin_signup(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        
        errors = []
        
        if not username:
            errors.append('Username is required')
        if not email:
            errors.append('Email is required')
        if not password:
            errors.append('Password is required')
        if password != password2:
            errors.append('Passwords do not match')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters')
        
        if User.objects.filter(username=username).exists():
            errors.append('Username already exists')
        if User.objects.filter(email=email).exists():
            errors.append('Email already exists')
        
        if errors:
            return render(request, 'core/admin_signup.html', {'errors': errors})
        
        try:
            user = User.objects.create_superuser(username, email, password)
            messages.success(request, f'Admin account "{username}" created successfully! Please log in.')
            return redirect('/brilltech/admin/login/')
        except Exception as e:
            return render(request, 'core/admin_signup.html', {'errors': [str(e)]})
    
    return render(request, 'core/admin_signup.html')
