from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import logging

# Local App Imports
from .forms import UserRegisterForm, StaffCreationForm, VisitorRegistrationForm  # Add the new form
from .models import User, Blacklist
from .decorators import admin_required
from visitor_management.models import Visit, EmergencyAlert  # Add EmergencyAlert
import re

logger = logging.getLogger(__name__)

# --- Core Authentication & Public Views ---

def landing_page(request):
    """
    Renders the public-facing landing page.
    If the user is already authenticated, redirects them to the dashboard.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing_page.html')

def register(request):
    """
    UPDATED: Handles new visitor registration with Aadhar-only ID proof.
    Redirects if user is already logged in.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == "POST":
        # Use the new Aadhar-focused registration form
        form = VisitorRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f"Account created successfully for {username}! Please login with your credentials.")
            return redirect("visitor_login")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = VisitorRegistrationForm()
    
    return render(request, "accounts/register.html", {"form": form})

# Alternative registration function specifically for visitors
def visitor_registration(request):
    """
    NEW: Dedicated visitor registration with Aadhar validation
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == "POST":
        form = VisitorRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            aadhar_masked = user.get_masked_aadhar() if hasattr(user, 'get_masked_aadhar') else 'XXXX XXXX XXXX'
            
            messages.success(
                request, 
                f"Registration successful! Welcome {user.full_name}. "
                f"Your account has been created with Aadhar: {aadhar_masked}"
            )
            
            # Auto-login the user after registration
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = VisitorRegistrationForm()
    
    return render(request, 'accounts/visitor_registration.html', {'form': form})

def visitor_login(request):
    """
    Handles login for 'visitor' and 'family' roles with enhanced debugging.
    """
    # If user is already authenticated, redirect them
    if request.user.is_authenticated:
        logger.info(f"User {request.user.username} already authenticated, redirecting to dashboard")
        return redirect('dashboard')

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        
        # Enhanced logging
        logger.info(f"=== LOGIN ATTEMPT ===")
        logger.info(f"Username: '{username}'")
        logger.info(f"Password provided: {'Yes' if password else 'No'}")
        logger.info(f"Password length: {len(password) if password else 0}")
        
        # Basic validation
        if not username or not password:
            logger.warning(f"Missing credentials - Username: {'✓' if username else '✗'}, Password: {'✓' if password else '✗'}")
            messages.error(request, "Both username and password are required.")
            return render(request, "accounts/visitor_login.html")
        
        # Check if user exists before attempting authentication
        try:
            user_exists = User.objects.get(username=username)
            logger.info(f"User '{username}' exists in database")
            logger.info(f"User role: {user_exists.role}")
            logger.info(f"User is_active: {user_exists.is_active}")
            logger.info(f"User has aadhar: {bool(getattr(user_exists, 'aadhar_number', None))}")
        except User.DoesNotExist:
            logger.error(f"User '{username}' does not exist in database")
            messages.error(request, "Invalid username or password.")
            return render(request, "accounts/visitor_login.html")
        
        # Attempt authentication
        logger.info(f"Attempting authentication for '{username}'")
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            logger.info(f"✓ Authentication successful for '{username}'")
            logger.info(f"Authenticated user role: {user.role}")
            
            # Check if user is blacklisted
            try:
                blacklist_entry = user.blacklist
                logger.warning(f"✗ User '{username}' is blacklisted: {blacklist_entry.reason}")
                messages.error(request, "Your account has been suspended. Please contact administration.")
                return render(request, "accounts/visitor_login.html")
            except Blacklist.DoesNotExist:
                logger.info(f"✓ User '{username}' is not blacklisted")
            except AttributeError:
                logger.info(f"✓ User '{username}' has no blacklist relation")
            
            # Check role permissions
            if user.role in ["family", "visitor"]:
                logger.info(f"✓ User '{username}' has correct role: {user.role}")
                
                # Check Aadhar information (optional warning)
                if not getattr(user, 'aadhar_number', None):
                    logger.info(f"⚠ User '{username}' missing Aadhar information")
                    messages.warning(request, "Please update your profile with Aadhar card information for security compliance.")
                else:
                    logger.info(f"✓ User '{username}' has Aadhar information")
                
                # Perform login
                logger.info(f"Logging in user '{username}'")
                login(request, user)
                logger.info(f"✓ User '{username}' logged in successfully")
                
                # Check if user is actually logged in
                if request.user.is_authenticated:
                    logger.info(f"✓ Login confirmed - redirecting '{username}' to dashboard")
                    return redirect("dashboard")
                else:
                    logger.error(f"✗ Login failed - user not authenticated after login() call")
                    messages.error(request, "Login failed. Please try again.")
            else:
                logger.warning(f"✗ User '{username}' has incorrect role: {user.role}")
                messages.error(request, "This login portal is for visitors only. Staff should use the staff login portal.")
        else:
            logger.error(f"✗ Authentication failed for '{username}' - invalid credentials")
            messages.error(request, "Invalid username or password. Please check your credentials and try again.")
    
    # Render the login form (GET request or failed POST)
    logger.info("Rendering visitor login form")
    return render(request, "accounts/visitor_login.html")

def staff_login(request):
    """
    Handles login for 'admin' and 'security' roles.
    Redirects if user is already logged in.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None and user.role in ["admin", "security"]:
            login(request, user)
            return redirect("dashboard")
        else:
            messages.error(request, "Invalid staff credentials.")
    
    return render(request, "accounts/staff_login.html")

@login_required
def user_logout(request):
    """
    Logs the user out and redirects to the public landing page.
    """
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect("landing_page")

# --- Dashboard Router ---

@login_required
def dashboard(request):
    """
    Acts as a router, directing users to their appropriate dashboard or page.
    For admins, it also gathers key metrics for display.
    """
    user = request.user
    
    # Get active emergency alert for all users
    active_alert = EmergencyAlert.objects.filter(is_active=True).first()
    
    if user.role == "admin":
        # Gather live data for the admin dashboard
        pending_visits_count = 0
        active_staff_count = 0
        
        if user.jail:
            pending_visits_count = Visit.objects.filter(
                prisoner__jail=user.jail, 
                status='PENDING'
            ).count()
            active_staff_count = User.objects.filter(
                jail=user.jail, 
                role='security'
            ).count()

        context = {
            'pending_visits_count': pending_visits_count,
            'active_staff_count': active_staff_count,
            'active_alert': active_alert,  # Add emergency alert context
        }
        return render(request, "accounts/admin_dashboard.html", context)
    
    elif user.role == "security":
        return redirect("security_dashboard")
    
    else:  # For 'visitor' and 'family' roles
        # Check if visitor needs to update Aadhar information
        if not getattr(user, 'aadhar_number', None):
            messages.info(request, "Please update your profile with Aadhar card information for enhanced security.")
        
        return redirect("my_visits")

# --- Staff Management Views (Admin Only) ---

@login_required
@admin_required
def manage_security_staff(request):
    """
    Allows an admin to view existing security staff and create new accounts
    for their assigned jail.
    """
    if not request.user.jail:
        messages.error(request, "You must be assigned to a jail to manage staff.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = StaffCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'security'
            user.is_staff = True 
            user.jail = request.user.jail
            user.save()
            messages.success(request, f"Security account for {user.username} created successfully.")
            return redirect('manage_security_staff')
    else:
        form = StaffCreationForm()

    security_staff = User.objects.filter(jail=request.user.jail, role='security')
    
    # Add emergency alert context
    active_alert = EmergencyAlert.objects.filter(is_active=True).first()
    
    context = {
        'form': form,
        'security_staff': security_staff,
        'active_alert': active_alert,
    }
    return render(request, 'accounts/manage_security_staff.html', context)

@login_required
@admin_required
def delete_security_staff(request, pk):
    """ Deletes a security staff member's account. """
    staff_member = get_object_or_404(User, pk=pk, role='security', jail=request.user.jail)
    username = staff_member.username
    staff_member.delete()
    messages.warning(request, f"Security account for {username} has been deleted.")
    return redirect('manage_security_staff')

# --- Blacklist Management Views (Admin Only) ---

@login_required
@admin_required
def blacklist_list(request):
    """ Displays a list of all blacklisted users and a form to add new ones. """
    blacklisted_users = Blacklist.objects.all()
    non_blacklisted_users = User.objects.filter(
        role__in=['visitor', 'family'], 
        blacklist__isnull=True
    )
    
    # Add emergency alert context
    active_alert = EmergencyAlert.objects.filter(is_active=True).first()
    
    context = {
        'blacklisted_users': blacklisted_users,
        'non_blacklisted_users': non_blacklisted_users,
        'active_alert': active_alert,
    }
    return render(request, 'accounts/blacklist_management.html', context)

@login_required
@admin_required
def add_to_blacklist(request):
    """ Handles the submission to add a user to the blacklist. """
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        reason = request.POST.get('reason')
        
        if not user_id or not reason:
            messages.error(request, "User and reason are required.")
            return redirect('blacklist_list')
        
        user_to_blacklist = get_object_or_404(User, id=user_id)
        
        # Check if user is already blacklisted
        if hasattr(user_to_blacklist, 'blacklist'):
            messages.warning(request, f"User {user_to_blacklist.username} is already blacklisted.")
            return redirect('blacklist_list')
        
        Blacklist.objects.create(
            user=user_to_blacklist,
            reason=reason,
            blacklisted_by=request.user
        )
        
        # Log the blacklist action
        logger.info(f"User {user_to_blacklist.username} blacklisted by {request.user.username}. Reason: {reason}")
        
        messages.success(request, f"User {user_to_blacklist.username} has been successfully blacklisted.")
    
    return redirect('blacklist_list')

@login_required
@admin_required
def remove_from_blacklist(request, pk):
    """ Removes a user from the blacklist. """
    blacklist_entry = get_object_or_404(Blacklist, pk=pk)
    username = blacklist_entry.user.username
    
    # Log the removal
    logger.info(f"User {username} removed from blacklist by {request.user.username}")
    
    blacklist_entry.delete()
    messages.info(request, f"User {username} has been removed from the blacklist.")
    return redirect('blacklist_list')

# --- NEW: API Endpoint for Emergency Alerts ---

@login_required
@require_http_methods(["GET"])
def check_alert_api(request):
    """
    API endpoint to check if there's an active emergency alert
    Returns JSON with alert status and details
    """
    try:
        # Get the most recent active alert
        active_alert = EmergencyAlert.objects.filter(is_active=True).order_by('-issued_at').first()
        
        if active_alert:
            response_data = {
                'active': True,
                'alert_id': active_alert.id,
                'message': active_alert.message[:200],  # Limit message length for API
                'issued_by': active_alert.issued_by.get_full_name() or active_alert.issued_by.username,
                'issued_at': active_alert.issued_at.strftime('%Y-%m-%d %H:%M:%S'),
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'success'
            }
            
            logger.info(f"Alert check API: Active alert #{active_alert.id} found - User: {request.user.username}")
            
        else:
            response_data = {
                'active': False,
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'success'
            }
            
            logger.debug(f"Alert check API: No active alerts - User: {request.user.username}")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Alert check API error - User: {request.user.username}, Error: {str(e)}")
        
        return JsonResponse({
            'active': False,
            'error': 'Unable to check alert status',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'error'
        }, status=500)

# --- NEW: Aadhar Validation Helper Functions ---

def validate_aadhar_format(aadhar_number):
    """Helper function to validate Aadhar number format"""
    if not aadhar_number:
        return False
    
    # Remove spaces and hyphens
    aadhar_clean = re.sub(r'[\s-]', '', str(aadhar_number))
    
    # Check if it's exactly 12 digits
    if not re.match(r'^\d{12}$', aadhar_clean):
        return False
    
    # Aadhar numbers don't start with 0 or 1
    if aadhar_clean[0] in ['0', '1']:
        return False
    
    return True

@login_required
def update_aadhar_info(request):
    """
    NEW: Allow existing users to update their Aadhar information
    for compliance with new security requirements
    """
    if request.method == 'POST':
        aadhar_number = request.POST.get('aadhar_number', '').strip()
        aadhar_image = request.FILES.get('aadhar_image')
        
        if not aadhar_number:
            messages.error(request, "Aadhar number is required.")
            return redirect('update_aadhar_info')
        
        # Validate Aadhar format
        if not validate_aadhar_format(aadhar_number):
            messages.error(request, "Invalid Aadhar number format. Please enter a valid 12-digit Aadhar number.")
            return redirect('update_aadhar_info')
        
        # Clean Aadhar number
        aadhar_clean = re.sub(r'[\s-]', '', aadhar_number)
        
        # Check for duplicates
        existing_user = User.objects.filter(aadhar_number=aadhar_clean).exclude(pk=request.user.pk)
        if existing_user.exists():
            messages.error(request, "This Aadhar number is already registered with another account.")
            return redirect('update_aadhar_info')
        
        # Update user information
        request.user.aadhar_number = aadhar_clean
        if aadhar_image:
            request.user.id_proof = aadhar_image
        request.user.save()
        
        messages.success(request, "Your Aadhar information has been updated successfully.")
        return redirect('dashboard')
    
    return render(request, 'accounts/update_aadhar.html')
