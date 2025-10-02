from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction
import logging

# Local App Imports
from .forms import (
    UserRegisterForm, StaffCreationForm, VisitorRegistrationForm,
    UserProfileForm, FamilyAuthorizationForm  # NEW: Added profile forms
)
from .models import User, Blacklist
from .decorators import admin_required
from visitor_management.models import Visit, EmergencyAlert
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
    UPDATED: Handles new visitor registration with enhanced family relationships.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == "POST":
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

def visitor_registration(request):
    """
    Enhanced visitor registration with family relationship support
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == "POST":
        form = VisitorRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            aadhar_masked = user.get_masked_aadhar() if hasattr(user, 'get_masked_aadhar') else 'XXXX XXXX XXXX'
            
            # Enhanced success message with family connection info
            success_message = f"Registration successful! Welcome {user.full_name}. Your account has been created with Aadhar: {aadhar_masked}"
            
            if user.primary_family_member:
                success_message += f" | Connected to family member: {user.primary_family_member.full_name}"
            
            if user.can_authorize_emergency_visits:
                success_message += " | You can now authorize emergency visits for family members."
            
            messages.success(request, success_message)
            
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
    Enhanced login with family relationship context
    """
    if request.user.is_authenticated:
        logger.info(f"User {request.user.username} already authenticated, redirecting to dashboard")
        return redirect('dashboard')

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        
        logger.info(f"=== LOGIN ATTEMPT ===")
        logger.info(f"Username: '{username}'")
        logger.info(f"Password provided: {'Yes' if password else 'No'}")
        
        if not username or not password:
            logger.warning(f"Missing credentials - Username: {'✓' if username else '✗'}, Password: {'✓' if password else '✗'}")
            messages.error(request, "Both username and password are required.")
            return render(request, "accounts/visitor_login.html")
        
        try:
            user_exists = User.objects.get(username=username)
            logger.info(f"User '{username}' exists - Role: {user_exists.role}, Family: {user_exists.is_family_member}")
        except User.DoesNotExist:
            logger.error(f"User '{username}' does not exist in database")
            messages.error(request, "Invalid username or password.")
            return render(request, "accounts/visitor_login.html")
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            logger.info(f"✓ Authentication successful for '{username}'")
            
            # Check blacklist status
            try:
                blacklist_entry = user.blacklist
                logger.warning(f"✗ User '{username}' is blacklisted: {blacklist_entry.reason}")
                messages.error(request, "Your account has been suspended. Please contact administration.")
                return render(request, "accounts/visitor_login.html")
            except Blacklist.DoesNotExist:
                logger.info(f"✓ User '{username}' is not blacklisted")
            except AttributeError:
                logger.info(f"✓ User '{username}' has no blacklist relation")
            
            if user.role in ["family", "visitor"]:
                logger.info(f"✓ User '{username}' has correct role: {user.role}")
                
                # Enhanced login success message with family info
                login(request, user)
                
                welcome_message = f"Welcome back, {user.full_name or user.username}!"
                
                if user.role == 'family':
                    if user.can_authorize_emergency_visits:
                        welcome_message += " You can authorize emergency visits."
                    elif user.primary_family_member:
                        welcome_message += f" Connected to {user.primary_family_member.full_name} for emergency visits."
                
                messages.success(request, welcome_message)
                
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
    
    return render(request, "accounts/visitor_login.html")

def staff_login(request):
    """Handles login for 'admin' and 'security' roles."""
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
    """Logs the user out and redirects to the public landing page."""
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect("landing_page")

# --- Dashboard Router ---

@login_required
def dashboard(request):
    """Enhanced dashboard router with family relationship context"""
    user = request.user
    active_alert = EmergencyAlert.objects.filter(is_active=True).first()
    
    if user.role == "admin":
        pending_visits_count = 0
        active_staff_count = 0
        family_members_count = 0  # NEW: Track family members
        
        if user.jail:
            pending_visits_count = Visit.objects.filter(
                prisoner__jail=user.jail, 
                status='PENDING'
            ).count()
            active_staff_count = User.objects.filter(
                jail=user.jail, 
                role='security'
            ).count()
            # NEW: Count family members in jail
            family_members_count = User.objects.filter(
                role='family'
            ).count()

        context = {
            'pending_visits_count': pending_visits_count,
            'active_staff_count': active_staff_count,
            'family_members_count': family_members_count,  # NEW
            'active_alert': active_alert,
        }
        return render(request, "accounts/admin_dashboard.html", context)
    
    elif user.role == "security":
        return redirect("security_dashboard")
    
    else:  # For 'visitor' and 'family' roles
        # Enhanced profile completion check
        profile_complete = all([
            user.full_name,
            user.aadhar_number,
            user.phone_number,
            user.address
        ])
        
        if not profile_complete:
            messages.info(request, "Please complete your profile for enhanced security and better service.")
        
        # Family relationship notifications
        if user.role == 'family':
            if user.can_authorize_emergency_visits:
                family_count = user.family_members.count()
                if family_count > 0:
                    messages.info(request, f"You are authorizing emergency visits for {family_count} family member(s).")
            elif user.primary_family_member:
                messages.info(request, f"Emergency visits authorized by {user.primary_family_member.full_name}.")
        
        return redirect("my_visits")

# --- NEW: Profile Management Views ---

@login_required
def user_profile(request):
    """Display user profile page with family information"""
    user = request.user
    
    # Get family members
    family_members = user.get_family_members() if hasattr(user, 'get_family_members') else []
    
    # Get active emergency alert
    active_alert = EmergencyAlert.objects.filter(is_active=True).first()
    
    context = {
        'user': user,
        'family_members': family_members,
        'active_alert': active_alert,
        'can_request_emergency': user.can_request_emergency_visit() if hasattr(user, 'can_request_emergency_visit') else False,
    }
    
    return render(request, 'accounts/user_profile.html', context)

@login_required
def edit_profile(request):
    """Edit user profile information with family relationship support"""
    user = request.user
    
    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, request.FILES, instance=user)
        auth_form = None
        
        # Only family members can set authorization
        if user.role == 'family':
            auth_form = FamilyAuthorizationForm(request.POST, instance=user)
        
        # Validate forms
        forms_valid = profile_form.is_valid()
        if auth_form:
            forms_valid = forms_valid and auth_form.is_valid()
        
        if forms_valid:
            try:
                with transaction.atomic():
                    # Save profile
                    updated_user = profile_form.save()
                    
                    # Save authorization settings if applicable
                    if auth_form:
                        auth_form.save()
                    
                    # Update role based on family connection
                    if updated_user.primary_family_member or updated_user.can_authorize_emergency_visits:
                        updated_user.role = 'family'
                        updated_user.is_family_member = True
                    else:
                        updated_user.role = 'visitor'
                        updated_user.is_family_member = False
                    
                    updated_user.save()
                    
                    # Enhanced success message
                    success_msg = 'Profile updated successfully!'
                    if updated_user.primary_family_member:
                        success_msg += f' Connected to {updated_user.primary_family_member.full_name}.'
                    if updated_user.can_authorize_emergency_visits:
                        success_msg += ' You can now authorize emergency visits.'
                    
                    messages.success(request, success_msg)
                    return redirect('user_profile')
            
            except Exception as e:
                messages.error(request, f'Error updating profile: {str(e)}')
                logger.error(f"Profile update error for user {user.username}: {str(e)}")
        else:
            messages.error(request, 'Please correct the errors below.')
    
    else:
        profile_form = UserProfileForm(instance=user)
        auth_form = None
        if user.role == 'family':
            auth_form = FamilyAuthorizationForm(instance=user)
    
    active_alert = EmergencyAlert.objects.filter(is_active=True).first()
    
    context = {
        'profile_form': profile_form,
        'auth_form': auth_form,
        'active_alert': active_alert,
    }
    
    return render(request, 'accounts/edit_profile.html', context)

# @login_required
# def family_management(request):
#     """Manage family member connections and authorizations"""
#     user = request.user
    
#     # Only family members can access this page
#     if user.role != 'family':
#         messages.error(request, "Only family members can access this page.")
#         return redirect('dashboard')
    
#     # Get family members and related information
#     family_members = user.get_family_members() if hasattr(user, 'get_family_members') else []
#     authorized_members = User.objects.filter(
#         role='family',
#         can_authorize_emergency_visits=True
#     ).exclude(id=user.id)
    
#     # Get users connected to this user as primary family member
#     connected_members = User.objects.filter(primary_family_member=user) if user.can_authorize_emergency_visits else []
    
#     active_alert = EmergencyAlert.objects.filter(is_active=True).first()
    
#     context = {
#         'family_members': family_members,
#         'authorized_members': authorized_members,
#         'connected_members': connected_members,
#         'can_authorize': user.can_authorize_emergency_visits,
#         'active_alert': active_alert,
#     }
    
#     return render(request, 'accounts/family_management.html', context)

# --- Staff Management Views (Admin Only) ---

@login_required
@admin_required
def manage_security_staff(request):
    """Allows an admin to view existing security staff and create new accounts"""
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
    """Deletes a security staff member's account."""
    staff_member = get_object_or_404(User, pk=pk, role='security', jail=request.user.jail)
    username = staff_member.username
    staff_member.delete()
    messages.warning(request, f"Security account for {username} has been deleted.")
    return redirect('manage_security_staff')

# --- Blacklist Management Views (Admin Only) ---

@login_required
@admin_required
def blacklist_list(request):
    """Displays a list of all blacklisted users and a form to add new ones."""
    blacklisted_users = Blacklist.objects.all()
    non_blacklisted_users = User.objects.filter(
        role__in=['visitor', 'family'], 
        blacklist__isnull=True
    )
    
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
    """Handles the submission to add a user to the blacklist."""
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
        
        # Enhanced logging with family information
        family_info = ""
        if user_to_blacklist.role == 'family':
            family_info = f" (Family member"
            if user_to_blacklist.can_authorize_emergency_visits:
                family_info += ", Emergency Authorizer"
            family_info += ")"
        
        logger.info(f"User {user_to_blacklist.username}{family_info} blacklisted by {request.user.username}. Reason: {reason}")
        
        messages.success(request, f"User {user_to_blacklist.username} has been successfully blacklisted.")
    
    return redirect('blacklist_list')

@login_required
@admin_required
def remove_from_blacklist(request, pk):
    """Removes a user from the blacklist."""
    blacklist_entry = get_object_or_404(Blacklist, pk=pk)
    username = blacklist_entry.user.username
    
    logger.info(f"User {username} removed from blacklist by {request.user.username}")
    
    blacklist_entry.delete()
    messages.info(request, f"User {username} has been removed from the blacklist.")
    return redirect('blacklist_list')

# --- API Endpoints ---

@login_required
@require_http_methods(["GET"])
def check_alert_api(request):
    """API endpoint to check if there's an active emergency alert"""
    try:
        active_alert = EmergencyAlert.objects.filter(is_active=True).order_by('-issued_at').first()
        
        if active_alert:
            response_data = {
                'active': True,
                'alert_id': active_alert.id,
                'message': active_alert.message[:200],
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
        logger.error(f"Alert check API error - User: {request.user.username}, Error: {str(e)}")
        
        return JsonResponse({
            'active': False,
            'error': 'Unable to check alert status',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'error'
        }, status=500)

# --- Utility Functions ---

def validate_aadhar_format(aadhar_number):
    """Helper function to validate Aadhar number format"""
    if not aadhar_number:
        return False
    
    aadhar_clean = re.sub(r'[\s-]', '', str(aadhar_number))
    
    if not re.match(r'^\d{12}$', aadhar_clean):
        return False
    
    if aadhar_clean[0] in ['0', '1']:
        return False
    
    return True

@login_required
def update_aadhar_info(request):
    """Allow existing users to update their Aadhar information"""
    if request.method == 'POST':
        aadhar_number = request.POST.get('aadhar_number', '').strip()
        aadhar_image = request.FILES.get('aadhar_image')
        
        if not aadhar_number:
            messages.error(request, "Aadhar number is required.")
            return redirect('update_aadhar_info')
        
        if not validate_aadhar_format(aadhar_number):
            messages.error(request, "Invalid Aadhar number format. Please enter a valid 12-digit Aadhar number.")
            return redirect('update_aadhar_info')
        
        aadhar_clean = re.sub(r'[\s-]', '', aadhar_number)
        
        existing_user = User.objects.filter(aadhar_number=aadhar_clean).exclude(pk=request.user.pk)
        if existing_user.exists():
            messages.error(request, "This Aadhar number is already registered with another account.")
            return redirect('update_aadhar_info')
        
        request.user.aadhar_number = aadhar_clean
        if aadhar_image:
            request.user.id_proof = aadhar_image
        request.user.save()
        
        messages.success(request, "Your Aadhar information has been updated successfully.")
        return redirect('user_profile')  # Changed from dashboard to user_profile
    
    return render(request, 'accounts/update_aadhar.html')

# --- NEW: Family Relationship Management API ---

@login_required
@require_http_methods(["GET"])
def get_family_members_api(request):
    """API endpoint to get user's family members"""
    try:
        user = request.user
        
        if user.role != 'family':
            return JsonResponse({
                'status': 'error',
                'message': 'Only family members can access this endpoint'
            }, status=403)
        
        family_members = []
        
        if hasattr(user, 'get_family_members'):
            for member in user.get_family_members():
                family_members.append({
                    'id': member.id,
                    'full_name': member.full_name or member.username,
                    'username': member.username,
                    'relationship': member.get_relationship_to_primary_display() if member.relationship_to_primary else 'N/A',
                    'can_authorize_emergency': member.can_authorize_emergency_visits,
                    'role': member.get_role_display()
                })
        
        return JsonResponse({
            'status': 'success',
            'family_members': family_members,
            'count': len(family_members),
            'can_authorize': user.can_authorize_emergency_visits
        })
        
    except Exception as e:
        logger.error(f"Family members API error - User: {request.user.username}, Error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Unable to fetch family members'
        }, status=500)
