from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.db.models import Q
from datetime import timedelta, datetime
import json
import logging

# Local App Imports
from .models import Visit, EmergencyAlert
from prison_core.models import Prisoner, Jail
from accounts.models import Blacklist, User
from accounts.decorators import visitor_required, security_required, admin_required

# Third-party Imports
import qrcode
from io import BytesIO
from django.core.files import File

# Set up logging
logger = logging.getLogger(__name__)

# --- Visitor Views ---

@login_required
@visitor_required
def request_visit(request):
    if Blacklist.objects.filter(user=request.user).exists():
        messages.error(request, "Your account has been suspended from making visit requests.")
        return redirect('dashboard')

    jails = Jail.objects.all().order_by('name')
    prisoners = Prisoner.objects.none()
    
    selected_jail_id = request.GET.get('jail')
    prisoner_search_query = request.GET.get('prisoner_name', '').strip()

    # Enhanced search logic
    if selected_jail_id and prisoner_search_query:
        try:
            selected_jail_id = int(selected_jail_id)
            # Search by first name (case-insensitive) and ensure they belong to selected jail
            prisoners = Prisoner.objects.filter(
                jail_id=selected_jail_id,
                first_name__icontains=prisoner_search_query
            ).select_related('jail').order_by('first_name', 'last_name')
            
            # Debug logging
            print(f"Search parameters: jail_id={selected_jail_id}, name='{prisoner_search_query}'")
            print(f"Search results: Found {prisoners.count()} prisoners")
            
            # Also try searching by prisoner_id if no results by name
            if not prisoners.exists():
                prisoners = Prisoner.objects.filter(
                    jail_id=selected_jail_id,
                    prisoner_id__icontains=prisoner_search_query
                ).select_related('jail').order_by('first_name', 'last_name')
                print(f"Fallback search by ID: Found {prisoners.count()} prisoners")
            
        except (ValueError, TypeError) as e:
            messages.error(request, "Invalid facility selected.")
            prisoners = Prisoner.objects.none()
            print(f"Search error: {e}")

    # 🔧 FIXED Emergency visit eligibility check
    can_request_emergency = False
    
    # Check if user has properly set up prisoner relationship
    if (hasattr(request.user, 'related_prisoner') and 
        request.user.related_prisoner and 
        hasattr(request.user, 'relationship_to_prisoner') and 
        request.user.relationship_to_prisoner):
        
        # Check cooldown period
        last_emergency = Visit.objects.filter(
            visitor=request.user, 
            visit_type='EMERGENCY'
        ).order_by('-visit_date').first()
        
        if not last_emergency or (timezone.now().date() - last_emergency.visit_date > timedelta(days=20)):
            can_request_emergency = True
        
        print(f"🔍 DEBUG: User {request.user.username} emergency eligibility:")
        print(f"  - related_prisoner: {getattr(request.user, 'related_prisoner', 'None')}")
        print(f"  - relationship_to_prisoner: {getattr(request.user, 'relationship_to_prisoner', 'None')}")
        print(f"  - can_request_emergency: {can_request_emergency}")
    
    # Handle form submission
    if request.method == 'POST':
        prisoner_id = request.POST.get('prisoner_id')
        visit_date = request.POST.get('visit_date')
        time_slot = request.POST.get('time_slot')
        visit_type = request.POST.get('visit_type', 'REGULAR')
        
        # 🔍 DEBUG: Print received form data
        print(f"🔍 FORM SUBMISSION DEBUG:")
        print(f"  - prisoner_id: {prisoner_id}")
        print(f"  - visit_date: {visit_date}")
        print(f"  - time_slot: {time_slot}")
        print(f"  - visit_type: '{visit_type}'")
        
        try:
            prisoner = get_object_or_404(Prisoner, id=prisoner_id)
            
            # 🔧 ENHANCED Validation - check if this specific prisoner relationship
            if visit_type == 'EMERGENCY':
                if not (hasattr(request.user, 'related_prisoner') and 
                       request.user.related_prisoner and 
                       request.user.related_prisoner.id == int(prisoner_id) and
                       hasattr(request.user, 'relationship_to_prisoner') and 
                       request.user.relationship_to_prisoner):
                    messages.error(request, "Emergency visits are only available for your related family member.")
                    return redirect('request_visit')
                
                # Check cooldown period
                last_emergency = Visit.objects.filter(
                    visitor=request.user, 
                    visit_type='EMERGENCY'
                ).order_by('-visit_date').first()
                
                if last_emergency and (timezone.now().date() - last_emergency.visit_date <= timedelta(days=20)):
                    days_left = 20 - (timezone.now().date() - last_emergency.visit_date).days
                    messages.error(request, f"You must wait {days_left} more days before requesting another emergency visit.")
                    return redirect('request_visit')
            
            # Check for duplicate requests
            existing_visit = Visit.objects.filter(
                visitor=request.user,
                prisoner=prisoner,
                visit_date=visit_date,
                visit_time_slot=time_slot,
                status__in=['PENDING', 'APPROVED']
            ).first()
            
            if existing_visit:
                messages.warning(request, f"You already have a {existing_visit.status.lower()} visit request for this date and time.")
                return redirect('my_visits')
            
            # 🔧 CRITICAL: Create visit request with proper visit_type
            visit = Visit.objects.create(
                visitor=request.user,
                prisoner=prisoner,
                visit_date=visit_date,
                visit_time_slot=time_slot,
                status='PENDING',
                visit_type=visit_type  # 🚨 This should save correctly now
            )
            
            # 🔍 DEBUG: Verify what was actually saved
            print(f"✅ VISIT CREATED:")
            print(f"  - Visit ID: {visit.id}")
            print(f"  - visit_type saved as: '{visit.visit_type}'")
            print(f"  - visitor: {visit.visitor.username}")
            print(f"  - prisoner: {visit.prisoner.first_name} {visit.prisoner.last_name}")
            
            messages.success(request, f"Your {visit_type.lower()} visit request has been submitted successfully! Visit ID: {visit.id}")
            return redirect('my_visits')
            
        except Exception as e:
            messages.error(request, f"Error submitting visit request: {str(e)}")
            print(f"Visit request error: {e}")

    context = {
        'jails': jails,
        'prisoners': prisoners,
        'search_query': prisoner_search_query,
        'selected_jail': selected_jail_id,
        'can_request_emergency': can_request_emergency,
    }
    
    return render(request, 'visitor_management/request_visit.html', context)

@login_required
@visitor_required
def my_visits(request):
    visits = Visit.objects.filter(visitor=request.user).order_by('-visit_date')
    return render(request, 'visitor_management/my_visits.html', {'visits': visits})

# --- Admin Views ---

@login_required
@admin_required
def review_visits(request):
    if not request.user.jail:
        messages.error(request, "You must be assigned to a jail to review visits.")
        return redirect('dashboard')
    pending_visits = Visit.objects.filter(prisoner__jail=request.user.jail, status='PENDING').order_by('visit_date')
    return render(request, 'visitor_management/review_visits.html', {'visits': pending_visits})

@login_required
@admin_required
def visit_detail_review(request, visit_id):
    visit = get_object_or_404(Visit, id=visit_id, prisoner__jail=request.user.jail)
    return render(request, 'visitor_management/visit_detail_review.html', {'visit': visit})

@login_required
@admin_required
def decide_visit(request, visit_id, decision):
    """
    Enhanced QR code generation with additional security data
    """
    visit = get_object_or_404(Visit, id=visit_id, prisoner__jail=request.user.jail)
    if decision == 'approve':
        visit.status = 'APPROVED'
        
        # Enhanced QR data with facility and date information for better security
        qr_data = f"Visit ID: {visit.id}\nVisitor: {visit.visitor.username}\nPrisoner: {visit.prisoner.prisoner_id}\nDate: {visit.visit_date}\nFacility: {visit.prisoner.jail.name}"
        
        qr_image = qrcode.make(qr_data)
        buffer = BytesIO()
        qr_image.save(buffer, format='PNG')
        file_name = f'visit_qr_{visit.id}.png'
        visit.qr_code.save(file_name, File(buffer), save=False)
        
        messages.success(request, f"Visit approved and secure QR code generated for Visit ID: {visit.id}")
        print(f"QR CODE GENERATED: Visit ID {visit.id}, Visitor: {visit.visitor.username}")
        
    elif decision == 'reject':
        visit.status = 'REJECTED'
        messages.warning(request, "Visit has been rejected.")
    
    visit.save()
    return redirect('review_visits')

# --- Security Staff Views ---

@login_required
@security_required
def security_dashboard(request):
    """
    Enhanced security dashboard with comprehensive visitor management and emergency alerts
    """
    if not request.user.jail:
        messages.error(request, "You must be assigned to a jail to access the security dashboard.")
        return redirect('dashboard')
    
    today = timezone.now().date()
    
    # Get visitors currently inside (checked in but not checked out)
    currently_inside = Visit.objects.filter(
        prisoner__jail=request.user.jail,
        check_in_time__isnull=False,
        check_out_time__isnull=True
    ).select_related('visitor', 'prisoner').order_by('-check_in_time')
    
    # Get approved visits for today that haven't been checked in yet
    approved_visits = Visit.objects.filter(
        prisoner__jail=request.user.jail,
        visit_date=today,
        status='APPROVED',
        check_in_time__isnull=True
    ).select_related('visitor', 'prisoner').order_by('visit_time_slot')
    
    # Get recent emergency alerts
    recent_alerts = EmergencyAlert.objects.filter(is_active=True).order_by('-issued_at')[:5]
    active_alert_count = EmergencyAlert.objects.filter(is_active=True).count()
    
    # Enhanced logging for security monitoring
    print(f"SECURITY DASHBOARD - {request.user.jail.name if request.user.jail else 'Unknown'}")
    print(f"Currently inside count: {currently_inside.count()}")
    print(f"Approved visits count: {approved_visits.count()}")
    
    context = {
        'currently_inside': currently_inside,
        'approved_visits': approved_visits,
        'current_visitor_count': currently_inside.count(),
        'recent_alerts': recent_alerts,
        'active_alert_count': active_alert_count,
    }
    
    return render(request, 'visitor_management/security_dashboard.html', context)

@login_required
@security_required
def check_in_visitor(request):
    """
    Enhanced check-in with better error handling and logging
    """
    if request.method == 'POST':
        visit_id = request.POST.get('visit_id')
        
        try:
            visit = Visit.objects.get(
                id=visit_id, 
                prisoner__jail=request.user.jail, 
                status='APPROVED', 
                visit_date=timezone.now().date()
            )
            
            if visit.check_in_time:
                messages.warning(request, f"Visitor {visit.visitor.full_name or visit.visitor.username} has already been checked in at {visit.check_in_time.strftime('%I:%M %p')}.")
            else:
                visit.check_in_time = timezone.now()
                visit.save()
                
                visitor_name = visit.visitor.full_name or visit.visitor.username
                messages.success(request, f"✓ Visitor {visitor_name} checked in successfully at {timezone.now().strftime('%I:%M %p')}.")
                
                # Security logging
                print(f"CHECK-IN SUCCESS: Visit ID {visit_id}, Visitor: {visit.visitor.username}, Time: {timezone.now()}")
                
        except Visit.DoesNotExist:
            messages.error(request, "Invalid or expired visit ID for this facility.")
            print(f"CHECK-IN FAILED: Visit ID {visit_id} not found or invalid")
    
    return redirect('security_dashboard')

@login_required
@security_required
def check_out_visitor(request, visit_id):
    """
    Enhanced check-out with validation and logging
    """
    visit = get_object_or_404(Visit, id=visit_id, prisoner__jail=request.user.jail)
    
    # Validation: ensure visitor was checked in
    if not visit.check_in_time:
        messages.error(request, "Cannot check out visitor who was never checked in.")
        return redirect('security_dashboard')
    
    if visit.check_out_time:
        visitor_name = visit.visitor.full_name or visit.visitor.username
        messages.warning(request, f"Visitor {visitor_name} was already checked out at {visit.check_out_time.strftime('%I:%M %p')}.")
    else:
        visit.check_out_time = timezone.now()
        visit.status = 'COMPLETED'
        visit.save()
        
        visitor_name = visit.visitor.full_name or visit.visitor.username
        messages.success(request, f"✓ Visitor {visitor_name} has been checked out successfully at {timezone.now().strftime('%I:%M %p')}.")
        
        # Security logging
        print(f"CHECK-OUT SUCCESS: Visit ID {visit_id}, Visitor: {visit.visitor.username}, Time: {timezone.now()}")
    
    return redirect('security_dashboard')

@login_required
@security_required
def get_live_visitor_count(request):
    """
    HTMX endpoint for live visitor count (preserved for compatibility)
    """
    count = Visit.objects.filter(
        prisoner__jail=request.user.jail,
        check_in_time__isnull=False,
        check_out_time__isnull=True
    ).count()
    return render(request, 'visitor_management/partials/visitor_count_partial.html', {'current_visitor_count': count})

@login_required
@security_required
def verify_visit_details(request, visit_id):
    """
    HTMX endpoint for visit verification (preserved for compatibility)
    """
    try:
        visit = Visit.objects.select_related('visitor', 'prisoner').get(
            id=visit_id, prisoner__jail=request.user.jail,
            status='APPROVED', visit_date=timezone.now().date()
        )
        if visit.check_in_time:
            return HttpResponse(f'<div class="alert alert-warning animate__animated animate__headShake"><strong>Already Checked In:</strong> This visitor was checked in at {visit.check_in_time.strftime("%I:%M %p")}.</div>')
        return render(request, 'visitor_management/partials/visit_verification_partial.html', {'visit': visit})
    except Visit.DoesNotExist:
        return HttpResponse('<div class="alert alert-danger animate__animated animate__headShake"><strong>Invalid Visit:</strong> No approved visit found with this ID for today at this facility.</div>')

@login_required
@security_required
def get_visit_details_json(request, visit_id):
    """
    Enhanced API endpoint for QR code verification with complete visitor/prisoner details
    """
    try:
        visit = Visit.objects.select_related('visitor', 'prisoner', 'prisoner__jail').get(
            id=visit_id,                          # Layer 2: Must exist in database
            prisoner__jail=request.user.jail,     # Layer 5: Must be same facility
            status='APPROVED',                    # Layer 3: Must be approved status
            visit_date=timezone.now().date()      # Layer 4: Must be today's date
        )

        # Additional validation: prevent duplicate check-ins
        if visit.check_in_time:
            return JsonResponse({
                'error': f'Visitor already checked in at {visit.check_in_time.strftime("%I:%M %p")}. Duplicate check-ins are not allowed.'
            }, status=409)

        # Build complete visitor data with image
        visitor_photo_url = None
        if visit.visitor.profile_photo:
            visitor_photo_url = request.build_absolute_uri(visit.visitor.profile_photo.url)

        # Build complete prisoner data with image
        prisoner_photo_url = None
        if visit.prisoner.photo:
            prisoner_photo_url = request.build_absolute_uri(visit.prisoner.photo.url)

        # Return comprehensive visitor and prisoner details
        data = {
            'visit_id': visit.id,
            
            # Visitor details
            'visitor_name': visit.visitor.full_name or visit.visitor.username,
            'visitor_photo_url': visitor_photo_url,
            'visitor_details': {
                'username': visit.visitor.username,
                'email': visit.visitor.email or '',
                'phone': getattr(visit.visitor, 'phone_number', '') or '',
                'role': visit.visitor.role or '',
                'date_joined': visit.visitor.date_joined.strftime('%Y-%m-%d') if visit.visitor.date_joined else ''
            },
            
            # Prisoner details
            'prisoner_name': f"{visit.prisoner.first_name} {visit.prisoner.last_name}",
            'prisoner_photo_url': prisoner_photo_url,
            'prisoner_details': {
                'prisoner_id': visit.prisoner.prisoner_id,
                'jail_name': visit.prisoner.jail.name,
                'cell_number': getattr(visit.prisoner, 'cell_number', '') or '',
                'date_of_birth': visit.prisoner.date_of_birth.strftime('%Y-%m-%d') if getattr(visit.prisoner, 'date_of_birth', None) else '',
                'gender': getattr(visit.prisoner, 'gender', '') or '',
                'status': getattr(visit.prisoner, 'status', '') or ''
            },
            
            # Visit details
            'visit_time_slot': visit.visit_time_slot,
            'visit_type': getattr(visit, 'visit_type', 'REGULAR'),
            'visit_date': str(visit.visit_date),
        }
        
        # Security logging
        print(f"✓ QR VERIFICATION SUCCESS - Visit ID: {visit_id}, Visitor: {data['visitor_name']}, Facility: {request.user.jail.name}")
        return JsonResponse(data)

    except Visit.DoesNotExist:
        # Security logging for failed attempts
        print(f"✗ QR VERIFICATION FAILED - Visit ID: {visit_id}, User: {request.user.username}, Facility: {request.user.jail.name if request.user.jail else 'None'}")
        return JsonResponse({
            'error': 'Security validation failed. No approved visit found with this ID for today at this facility.'
        }, status=404)

@login_required
@security_required
def debug_qr_validation(request, visit_id):
    """
    Comprehensive QR validation debug with layer-by-layer analysis
    """
    debug_data = {
        'visit_id': visit_id,
        'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        'user': request.user.username,
        'user_jail': request.user.jail.name if request.user.jail else 'No Jail Assigned',
        'layers': {},
        'final_result': 'UNKNOWN'
    }
    
    print(f"\n🔍 QR VALIDATION DEBUG - Visit ID: {visit_id}")
    print("=" * 60)
    
    try:
        # Layer 1: Basic Existence Check
        print("Layer 1: Checking if visit exists in database...")
        visit = Visit.objects.get(id=visit_id)
        debug_data['layers']['layer_1_existence'] = {
            'status': 'PASS',
            'message': 'Visit found in database',
            'details': {
                'visitor': visit.visitor.username,
                'prisoner': f"{visit.prisoner.first_name} {visit.prisoner.last_name}",
                'created': str(getattr(visit, 'created_at', 'Unknown'))
            }
        }
        print("✅ Layer 1 PASSED: Visit exists")
        
        # Layer 2: Facility Validation
        print(f"Layer 2: Checking facility match...")
        print(f"   Visit Facility: {visit.prisoner.jail.name}")
        print(f"   User Facility: {request.user.jail.name if request.user.jail else 'None'}")
        
        if request.user.jail and visit.prisoner.jail == request.user.jail:
            debug_data['layers']['layer_2_facility'] = {
                'status': 'PASS',
                'message': 'Facility matches',
                'details': {
                    'visit_facility': visit.prisoner.jail.name,
                    'user_facility': request.user.jail.name
                }
            }
            print("✅ Layer 2 PASSED: Facility matches")
        else:
            debug_data['layers']['layer_2_facility'] = {
                'status': 'FAIL',
                'message': 'Facility mismatch or user has no jail assigned',
                'details': {
                    'visit_facility': visit.prisoner.jail.name,
                    'user_facility': request.user.jail.name if request.user.jail else 'None'
                }
            }
            print("❌ Layer 2 FAILED: Facility mismatch")
        
        # Layer 3: Status Validation
        print(f"Layer 3: Checking visit status...")
        print(f"   Current Status: {visit.status}")
        print(f"   Required Status: APPROVED")
        
        if visit.status == 'APPROVED':
            debug_data['layers']['layer_3_status'] = {
                'status': 'PASS',
                'message': 'Visit is approved',
                'details': {'status': visit.status}
            }
            print("✅ Layer 3 PASSED: Status is APPROVED")
        else:
            debug_data['layers']['layer_3_status'] = {
                'status': 'FAIL',
                'message': f'Visit status is {visit.status}, not APPROVED',
                'details': {'status': visit.status, 'required': 'APPROVED'}
            }
            print(f"❌ Layer 3 FAILED: Status is {visit.status}")
        
        # Layer 4: Date Validation
        today = timezone.now().date()
        print(f"Layer 4: Checking visit date...")
        print(f"   Visit Date: {visit.visit_date}")
        print(f"   Today's Date: {today}")
        
        if visit.visit_date == today:
            debug_data['layers']['layer_4_date'] = {
                'status': 'PASS',
                'message': 'Visit is scheduled for today',
                'details': {
                    'visit_date': str(visit.visit_date),
                    'today': str(today)
                }
            }
            print("✅ Layer 4 PASSED: Visit is for today")
        else:
            days_diff = (visit.visit_date - today).days
            debug_data['layers']['layer_4_date'] = {
                'status': 'FAIL',
                'message': f'Visit is scheduled for {visit.visit_date}, not today ({today})',
                'details': {
                    'visit_date': str(visit.visit_date),
                    'today': str(today),
                    'days_difference': days_diff
                }
            }
            print(f"❌ Layer 4 FAILED: Visit is {days_diff} days {'in the future' if days_diff > 0 else 'in the past'}")
        
        # Layer 5: Check-in Status
        print(f"Layer 5: Checking if visitor is already checked in...")
        print(f"   Check-in Time: {visit.check_in_time or 'Not checked in'}")
        
        if visit.check_in_time is None:
            debug_data['layers']['layer_5_checkin'] = {
                'status': 'PASS',
                'message': 'Visitor not yet checked in',
                'details': {'check_in_time': None}
            }
            print("✅ Layer 5 PASSED: Not checked in yet")
        else:
            debug_data['layers']['layer_5_checkin'] = {
                'status': 'FAIL',
                'message': f'Visitor already checked in at {visit.check_in_time.strftime("%I:%M %p")}',
                'details': {'check_in_time': str(visit.check_in_time)}
            }
            print(f"❌ Layer 5 FAILED: Already checked in at {visit.check_in_time}")
        
        # Final Result
        all_passed = all(layer['status'] == 'PASS' for layer in debug_data['layers'].values())
        if all_passed:
            debug_data['final_result'] = 'PASS'
            debug_data['message'] = 'All validation layers passed - QR code is valid'
            print("\n🎉 FINAL RESULT: QR CODE VALID - All layers passed")
        else:
            failed_layers = [name for name, layer in debug_data['layers'].items() if layer['status'] == 'FAIL']
            debug_data['final_result'] = 'FAIL'
            debug_data['message'] = f'Validation failed at: {", ".join(failed_layers)}'
            print(f"\n❌ FINAL RESULT: QR CODE REJECTED - Failed layers: {', '.join(failed_layers)}")
        
    except Visit.DoesNotExist:
        debug_data['layers']['layer_1_existence'] = {
            'status': 'FAIL',
            'message': 'Visit ID not found in database',
            'details': {'visit_id': visit_id}
        }
        debug_data['final_result'] = 'FAIL'
        debug_data['message'] = 'Visit does not exist'
        print("❌ Layer 1 FAILED: Visit does not exist")
        print("\n❌ FINAL RESULT: QR CODE REJECTED - Visit not found")
    
    print("=" * 60)
    return JsonResponse(debug_data)

# --- Emergency Alert System ---

def is_security_staff(user):
    """Check if user is security staff"""
    return user.is_authenticated and (user.is_staff or hasattr(user, 'jail'))

def classify_emergency_type(reason):
    """Classify emergency type based on reason keywords"""
    reason_lower = reason.lower()
    
    if any(keyword in reason_lower for keyword in ['fight', 'violence', 'attack', 'assault', 'riot']):
        return 'VIOLENCE/FIGHT'
    elif any(keyword in reason_lower for keyword in ['medical', 'injury', 'hurt', 'sick', 'health', 'ambulance']):
        return 'MEDICAL EMERGENCY'
    elif any(keyword in reason_lower for keyword in ['fire', 'smoke', 'burn', 'flames']):
        return 'FIRE EMERGENCY'
    elif any(keyword in reason_lower for keyword in ['escape', 'missing', 'fled', 'breakout']):
        return 'ESCAPE ATTEMPT'
    elif any(keyword in reason_lower for keyword in ['breach', 'unauthorized', 'security', 'intruder']):
        return 'SECURITY BREACH'
    elif any(keyword in reason_lower for keyword in ['lockdown', 'lock down', 'secure', 'containment']):
        return 'LOCKDOWN REQUIRED'
    elif any(keyword in reason_lower for keyword in ['weapon', 'knife', 'gun', 'contraband']):
        return 'WEAPON/CONTRABAND'
    else:
        return 'GENERAL EMERGENCY'

def send_emergency_notifications(emergency_alert, emergency_reason, location, request):
    """Send emergency notifications to all relevant personnel"""
    try:
        # Get all staff users (administrators, security staff, etc.)
        staff_users = User.objects.filter(
            Q(is_staff=True) | 
            Q(is_superuser=True)
        ).distinct()
        
        # Prepare email content
        subject = f"🚨 EMERGENCY ALERT #{emergency_alert.id} - IMMEDIATE RESPONSE REQUIRED"
        
        html_message = f"""
        <div style="background-color: #dc3545; color: white; padding: 20px; border-radius: 8px; font-family: Arial, sans-serif;">
            <h2 style="margin: 0 0 20px 0;">🚨 FACILITY EMERGENCY ALERT 🚨</h2>
            
            <div style="background-color: rgba(255,255,255,0.1); padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                <h3 style="margin: 0 0 10px 0; color: #fff;">Alert Details</h3>
                <p><strong>Alert ID:</strong> #{emergency_alert.id}</p>
                <p><strong>Emergency Type:</strong> {classify_emergency_type(emergency_reason)}</p>
                <p><strong>Location:</strong> {location}</p>
                <p><strong>Reported By:</strong> {request.user.get_full_name() or request.user.username}</p>
                <p><strong>Time:</strong> {emergency_alert.issued_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div style="background-color: rgba(255,255,255,0.1); padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                <h3 style="margin: 0 0 10px 0; color: #fff;">Emergency Description</h3>
                <p style="font-size: 16px; line-height: 1.5;">{emergency_reason}</p>
            </div>
            
            <div style="background-color: #ffc107; color: #000; padding: 15px; border-radius: 6px;">
                <h3 style="margin: 0 0 10px 0;">⚠️ IMMEDIATE ACTION REQUIRED</h3>
                <ul style="margin: 0; padding-left: 20px;">
                    <li>Respond to emergency situation immediately</li>
                    <li>Contact facility if you are off-site</li>
                    <li>Follow emergency protocols for {classify_emergency_type(emergency_reason)}</li>
                    <li>Report to command center for coordination</li>
                </ul>
            </div>
            
            <div style="margin-top: 20px; text-align: center; font-size: 12px; opacity: 0.8;">
                E-Prison Management System - Emergency Alert #{emergency_alert.id}
            </div>
        </div>
        """
        
        plain_message = f"""
🚨 FACILITY EMERGENCY ALERT 🚨

Alert ID: #{emergency_alert.id}
Emergency Type: {classify_emergency_type(emergency_reason)}
Location: {location}
Reported By: {request.user.get_full_name() or request.user.username}
Time: {emergency_alert.issued_at.strftime('%Y-%m-%d %H:%M:%S')}

EMERGENCY DESCRIPTION:
{emergency_reason}

⚠️ IMMEDIATE ACTION REQUIRED:
- Respond to emergency situation immediately
- Contact facility if you are off-site  
- Follow emergency protocols for {classify_emergency_type(emergency_reason)}
- Report to command center for coordination

E-Prison Management System - Emergency Alert #{emergency_alert.id}
        """
        
        # Send emails to all staff
        email_recipients = []
        for staff in staff_users:
            if staff.email and staff.email.strip():
                email_recipients.append(staff.email)
        
        notifications_sent = 0
        if email_recipients:
            try:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=plain_message,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@prison.gov'),
                    to=email_recipients
                )
                msg.attach_alternative(html_message, "text/html")
                msg.send()
                
                notifications_sent = len(email_recipients)
                print(f"Emergency emails sent to {notifications_sent} recipients: {', '.join(email_recipients)}")
                
            except Exception as e:
                logger.error(f"Failed to send emergency emails: {e}")
                print(f"Failed to send emergency emails: {e}")
        
        # Here you could add SMS notifications using services like Twilio
        print(f"SMS notifications would be sent to facility staff phones")
        
        return {
            'success': notifications_sent > 0,
            'count': notifications_sent,
            'recipients': email_recipients
        }
        
    except Exception as e:
        logger.error(f"Error sending emergency notifications: {e}")
        return {
            'success': False,
            'count': 0,
            'error': str(e)
        }

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@login_required
@user_passes_test(is_security_staff)
@require_POST
def trigger_emergency_alert(request):
    """Trigger facility-wide emergency alert"""
    try:
        # Parse request data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()
        
        # Extract emergency information
        emergency_reason = data.get('emergency_reason', '').strip()
        facility_id = data.get('facility_id')
        security_user = data.get('security_user', request.user.username)
        location = data.get('location', 'Security Dashboard')
        timestamp = data.get('timestamp', timezone.now().isoformat())
        
        # Validation
        if not emergency_reason or len(emergency_reason) < 10:
            error_msg = 'Emergency reason must be at least 10 characters long.'
            if request.content_type == 'application/json':
                return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
            else:
                messages.error(request, error_msg)
                return redirect('security_dashboard')
        
        # Create comprehensive emergency message
        emergency_message = f"""
🚨 FACILITY EMERGENCY ALERT 🚨

Emergency Type: {classify_emergency_type(emergency_reason)}
Location: {location}
Reported By: {request.user.get_full_name() or request.user.username}
Timestamp: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

EMERGENCY DETAILS:
{emergency_reason}

IMMEDIATE ACTION REQUIRED:
- Respond to emergency situation immediately
- Contact facility if you are off-site
- Follow emergency protocols

Facility: {getattr(request.user, 'jail', 'Unknown Facility')}
Security User: {security_user}
User IP: {get_client_ip(request)}
        """.strip()
        
        # Create emergency alert record using your existing model
        emergency_alert = EmergencyAlert.objects.create(
            message=emergency_message,
            issued_by=request.user,
            is_active=True
        )
        
        # Send notifications
        try:
            notification_result = send_emergency_notifications(emergency_alert, emergency_reason, location, request)
        except Exception as e:
            logger.error(f"Failed to send emergency notifications: {e}")
            notification_result = {'success': False, 'count': 0}
        
        # Log the emergency
        logger.critical(
            f"🚨 EMERGENCY ALERT ACTIVATED 🚨\n"
            f"Alert ID: {emergency_alert.id}\n"
            f"User: {request.user.username}\n"
            f"Reason: {emergency_reason}\n"
            f"Location: {location}\n"
            f"Timestamp: {timezone.now()}\n"
            f"IP: {get_client_ip(request)}"
        )
        
        # Print to console for immediate visibility
        print(f"\n{'='*60}")
        print(f"🚨 EMERGENCY ALERT ACTIVATED 🚨")
        print(f"{'='*60}")
        print(f"Alert ID: {emergency_alert.id}")
        print(f"Security User: {request.user.username} ({request.user.get_full_name() or 'No full name'})")
        print(f"Emergency Type: {classify_emergency_type(emergency_reason)}")
        print(f"Reason: {emergency_reason}")
        print(f"Location: {location}")
        print(f"Timestamp: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Notifications Sent: {notification_result.get('count', 0)} recipients")
        print(f"{'='*60}\n")
        
        # Return success response
        success_msg = f'Emergency alert #{emergency_alert.id} activated. All security personnel have been notified.'
        
        if request.content_type == 'application/json':
            return JsonResponse({
                'status': 'success', 
                'message': success_msg,
                'alert_id': emergency_alert.id,
                'timestamp': emergency_alert.issued_at.isoformat(),
                'emergency_type': classify_emergency_type(emergency_reason),
                'notifications_sent': notification_result.get('count', 0)
            })
        else:
            messages.success(request, success_msg)
            return redirect('security_dashboard')
            
    except json.JSONDecodeError:
        error_msg = 'Invalid JSON data in emergency request.'
        logger.error(error_msg)
        if request.content_type == 'application/json':
            return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
        else:
            messages.error(request, error_msg)
            return redirect('security_dashboard')
    
    except Exception as e:
        error_msg = f'Emergency alert system error: {str(e)}'
        logger.error(f"Emergency alert error: {e}", exc_info=True)
        
        if request.content_type == 'application/json':
            return JsonResponse({'status': 'error', 'message': error_msg}, status=500)
        else:
            messages.error(request, 'Emergency alert system error. Please contact administrator immediately!')
            return redirect('security_dashboard')

@login_required
@user_passes_test(is_security_staff)
def emergency_log_view(request):
    """View emergency alert logs"""
    # Get all emergency alerts, ordered by most recent first
    alerts = EmergencyAlert.objects.all().order_by('-issued_at')
    
    # Filter by active/resolved status
    status_filter = request.GET.get('status')
    if status_filter == 'active':
        alerts = alerts.filter(is_active=True)
    elif status_filter == 'resolved':
        alerts = alerts.filter(is_active=False)
    
    # Filter by date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        try:
            alerts = alerts.filter(issued_at__gte=datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    
    if date_to:
        try:
            alerts = alerts.filter(issued_at__lte=datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
        except ValueError:
            pass
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        alerts = alerts.filter(
            Q(message__icontains=search_query) |
            Q(issued_by__username__icontains=search_query) |
            Q(issued_by__first_name__icontains=search_query) |
            Q(issued_by__last_name__icontains=search_query)
        )
    
    # Handle resolve/reactivate actions
    if request.method == 'POST':
        alert_id = request.POST.get('alert_id')
        action = request.POST.get('action')
        
        try:
            alert = EmergencyAlert.objects.get(id=alert_id)
            if action == 'resolve':
                alert.is_active = False
                alert.save()
                messages.success(request, f'Emergency Alert #{alert.id} has been resolved.')
            elif action == 'reactivate':
                alert.is_active = True
                alert.save()
                messages.success(request, f'Emergency Alert #{alert.id} has been reactivated.')
        except EmergencyAlert.DoesNotExist:
            messages.error(request, 'Alert not found.')
        
        return redirect('emergency_log')
    
    # Paginate results
    from django.core.paginator import Paginator
    paginator = Paginator(alerts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get statistics
    stats = {
        'total_alerts': EmergencyAlert.objects.count(),
        'active_alerts': EmergencyAlert.objects.filter(is_active=True).count(),
        'resolved_alerts': EmergencyAlert.objects.filter(is_active=False).count(),
        'alerts_today': EmergencyAlert.objects.filter(
            issued_at__date=timezone.now().date()
        ).count(),
    }
    
    context = {
        'alerts': page_obj,
        'stats': stats,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
    }
    
    return render(request, 'security/emergency_log.html', context)

# --- Legacy Emergency Alert Views (for backward compatibility) ---

@login_required
@admin_required
def manage_alerts(request):
    """
    Admin interface for managing emergency alerts
    """
    if request.method == 'POST':
        message = request.POST.get('message')
        if message:
            EmergencyAlert.objects.filter(is_active=True).update(is_active=False)
            EmergencyAlert.objects.create(message=message, issued_by=request.user)
            messages.success(request, "Emergency alert has been broadcast to all users.")
        else:
            messages.error(request, "Alert message cannot be empty.")
        return redirect('manage_alerts')
    
    active_alert = EmergencyAlert.objects.filter(is_active=True).first()
    alert_history = EmergencyAlert.objects.order_by('-issued_at')[:10]  # Limit for performance
    context = {'active_alert': active_alert, 'alert_history': alert_history}
    return render(request, 'visitor_management/manage_alerts.html', context)

@login_required
@admin_required
def deactivate_alert(request, pk):
    """
    Deactivate emergency alert
    """
    alert = get_object_or_404(EmergencyAlert, pk=pk)
    alert.is_active = False
    alert.save()
    messages.info(request, "The emergency alert has been deactivated.")
    return redirect('manage_alerts')

@login_required
@security_required
def trigger_emergency_alarm(request):
    """
    Legacy emergency alarm trigger (kept for backward compatibility)
    """
    if request.method == 'POST':
        try:
            # Deactivate any existing alerts to ensure this is the only active one
            EmergencyAlert.objects.filter(is_active=True).update(is_active=False)
            
            # Create facility-specific emergency alert
            facility_name = request.user.jail.name if request.user.jail else 'Unknown Location'
            alert_message = f"🚨 PANIC ALARM TRIGGERED AT GATE: {facility_name} 🚨"
            
            emergency_alert = EmergencyAlert.objects.create(
                message=alert_message, 
                issued_by=request.user,
                is_active=True
            )
            
            messages.error(request, "🚨 EMERGENCY ALARM ACTIVATED! All administrators have been notified immediately.")
            
            # Comprehensive security logging
            print(f"🚨 EMERGENCY ALERT TRIGGERED 🚨")
            print(f"Facility: {facility_name}")
            print(f"Triggered by: {request.user.username} ({request.user.get_full_name()})")
            print(f"Time: {timezone.now()}")
            print(f"Alert ID: {emergency_alert.id}")
            
        except Exception as e:
            messages.error(request, f"Failed to trigger emergency alarm: {str(e)}")
            print(f"EMERGENCY ALERT FAILED: {str(e)} - User: {request.user.username}")
    
    return redirect('security_dashboard')

# Fix the date issue by updating Visit ID 11 to today's date
def fix_visit_date_for_testing():
    """
    Helper function to fix visit date for testing
    Run this in Django shell: python manage.py shell
    >>> from visitor_management.views import fix_visit_date_for_testing
    >>> fix_visit_date_for_testing()
    """
    try:
        visit = Visit.objects.get(id=11)
        visit.visit_date = timezone.now().date()
        visit.save()
        print(f"✅ Visit ID 11 date updated to: {visit.visit_date}")
        return True
    except Visit.DoesNotExist:
        print("❌ Visit ID 11 not found")
        return False

# --- Utility Functions ---

def update_all_pending_visits_to_today():
    """
    Helper function to update all pending/approved visits to today's date for testing
    """
    today = timezone.now().date()
    updated_visits = Visit.objects.filter(
        status__in=['PENDING', 'APPROVED'],
        visit_date__lt=today
    ).update(visit_date=today)
    
    print(f"✅ Updated {updated_visits} visits to today's date: {today}")
    return updated_visits

# Add this to your views.py

@login_required
def check_alert_api(request):
    """API endpoint to check if there's an active emergency alert"""
    try:
        active_alert = EmergencyAlert.objects.filter(is_active=True).first()
        
        if active_alert:
            return JsonResponse({
                'active': True,
                'alert_id': active_alert.id,
                'message': active_alert.message,
                'issued_by': active_alert.issued_by.username,
                'issued_at': active_alert.issued_at.isoformat(),
                'timestamp': timezone.now().isoformat()
            })
        else:
            return JsonResponse({
                'active': False,
                'timestamp': timezone.now().isoformat()
            })
            
    except Exception as e:
        logger.error(f"Alert check API error: {e}")
        return JsonResponse({
            'active': False,
            'error': 'Unable to check alert status',
            'timestamp': timezone.now().isoformat()
        }, status=500)
