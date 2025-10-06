# accounts/decorators.py

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages

def admin_required(function):
    def wrap(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == 'admin':
            return function(request, *args, **kwargs)
        else:
            messages.error(request, "You do not have permission to access this page.")
            return redirect('staff_login')
    return wrap

def security_required(function):
    def wrap(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == 'security':
            return function(request, *args, **kwargs)
        else:
            messages.error(request, "You do not have permission to access this page.")
            return redirect('staff_login')
    return wrap

def visitor_required(function):
    def wrap(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role in ['visitor', 'family']:
            return function(request, *args, **kwargs)
        else:
            messages.error(request, "You must be logged in as a visitor to access this page.")
            return redirect('visitor_login')
    return wrap