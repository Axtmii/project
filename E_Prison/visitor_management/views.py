# visitor_management/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
# This is the correct way
from .models import Visit  # Import Visit from the current app's models
from prison_core.models import Prisoner, Jail  # Import Prisoner and Jail from the prison_core app
from accounts.decorators import visitor_required, security_required, admin_required
import datetime
import qrcode
from io import BytesIO
from django.core.files import File
from PIL import Image

# -- Visitor Views --

from django.utils import timezone
from datetime import timedelta

# ... (keep other imports) ...

@login_required
@visitor_required
def request_visit(request):
    jails = Jail.objects.all()
    prisoners = Prisoner.objects.none()
    
    selected_jail_id = request.GET.get('jail')
    prisoner_search_query = request.GET.get('prisoner_name')

    if selected_jail_id and prisoner_search_query:
        prisoners = Prisoner.objects.filter(
            jail_id=selected_jail_id,
            first_name__icontains=prisoner_search_query
        )

    # --- Emergency Visit Eligibility Check ---
    can_request_emergency = False
    if request.user.is_family_member:
        # Find the last emergency visit for this user
        last_emergency_visit = Visit.objects.filter(
            visitor=request.user,
            visit_type='EMERGENCY'
        ).order_by('-visit_date').first()
        
        if not last_emergency_visit:
            # They've never had one, so they are eligible
            can_request_emergency = True
        else:
            # Check if 20 days have passed
            if timezone.now().date() > last_emergency_visit.visit_date + timedelta(days=20):
                can_request_emergency = True
    
    # --- Handle POST request ---
    if request.method == 'POST':
        prisoner_id = request.POST.get('prisoner_id')
        visit_date = request.POST.get('visit_date')
        time_slot = request.POST.get('time_slot')
        # Check if the emergency button was clicked
        visit_type = request.POST.get('visit_type', 'REGULAR')
        
        prisoner = get_object_or_404(Prisoner, id=prisoner_id)

        # Server-side check to prevent non-family members from submitting emergency requests
        if visit_type == 'EMERGENCY' and not can_request_emergency:
            messages.error(request, "You are not eligible to make an emergency visit request at this time.")
            return redirect('request_visit')

        Visit.objects.create(
            visitor=request.user,
            prisoner=prisoner,
            visit_date=visit_date,
            visit_time_slot=time_slot,
            status='PENDING',
            visit_type=visit_type # Set the visit type
        )
        messages.success(request, f"Your {visit_type.lower()} visit request has been submitted.")
        return redirect('my_visits')

    context = {
        'jails': jails,
        'prisoners': prisoners,
        'search_query': prisoner_search_query,
        'selected_jail': selected_jail_id,
        'can_request_emergency': can_request_emergency # Pass eligibility to template
    }
    return render(request, 'visitor_management/request_visit.html', context)


@login_required
@visitor_required
def my_visits(request):
    """
    Displays a list of all visits requested by the logged-in visitor.
    """
    visits = Visit.objects.filter(visitor=request.user).order_by('-visit_date')
    return render(request, 'visitor_management/my_visits.html', {'visits': visits})

# -- Admin Views --

@login_required
@admin_required
def review_visits(request):
    """
    Lists pending visit requests for the admin's jail.
    """
    pending_visits = Visit.objects.filter(prisoner__jail=request.user.jail, status='PENDING')
    return render(request, 'visitor_management/review_visits.html', {'visits': pending_visits})

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Visit
from accounts.decorators import admin_required
import qrcode
from io import BytesIO
from django.core.files import File
# The 'Image' import from PIL is no longer needed for this function
# from PIL import Image 

@login_required
@admin_required
def decide_visit(request, visit_id, decision):
    """
    Allows an admin to approve or reject a visit.
    """
    visit = get_object_or_404(Visit, id=visit_id, prisoner__jail=request.user.jail)
    
    if decision == 'approve':
        visit.status = 'APPROVED'
        
        # --- CORRECTED QR CODE LOGIC ---
        # 1. Generate the QR code image directly.
        #    It's good practice to include more identifying info.
        qr_data = f"Visit ID: {visit.id}\nVisitor: {visit.visitor.username}\nPrisoner: {visit.prisoner.prisoner_id}"
        qr_image = qrcode.make(qr_data)
        
        # 2. Create an in-memory buffer to hold the image data.
        buffer = BytesIO()
        
        # 3. Save the generated QR image directly into the buffer in PNG format.
        qr_image.save(buffer, format='PNG')
        
        # 4. Define a unique filename and save the buffer's content to the Visit model's qr_code field.
        file_name = f'visit_qr_{visit.id}.png'
        # 'save=False' is important here to prevent saving the model twice.
        visit.qr_code.save(file_name, File(buffer), save=False)
        
        messages.success(request, "Visit has been approved and QR code generated.")

    elif decision == 'reject':
        visit.status = 'REJECTED'
        messages.warning(request, "Visit has been rejected.")
        
    # Save all changes to the visit object at the end.
    visit.save()
    return redirect('review_visits')
# -- Security Staff Views --

@login_required
@security_required
def security_dashboard(request):
    """
    Dashboard for security staff to see today's approved visits and manage check-ins.
    """
    today = datetime.date.today()
    approved_visits = Visit.objects.filter(
        prisoner__jail=request.user.jail,
        visit_date=today,
        status='APPROVED'
    )
    
    currently_inside = Visit.objects.filter(
        prisoner__jail=request.user.jail,
        check_in_time__isnull=False,
        check_out_time__isnull=True
    )

    return render(request, 'visitor_management/security_dashboard.html', {
        'approved_visits': approved_visits,
        'currently_inside': currently_inside
    })

@login_required
@security_required
def check_in_visitor(request):
    """
    Processes a visitor's check-in via their visit ID (from QR code).
    """
    if request.method == 'POST':
        visit_id = request.POST.get('visit_id')
        try:
            visit = Visit.objects.get(
                id=visit_id, 
                prisoner__jail=request.user.jail, 
                status='APPROVED',
                visit_date=datetime.date.today()
            )
            if visit.check_in_time:
                messages.warning(request, "This visitor has already been checked in.")
            else:
                visit.check_in_time = datetime.datetime.now()
                visit.save()
                messages.success(request, f"Visitor {visit.visitor.username} checked in successfully.")
        except Visit.DoesNotExist:
            messages.error(request, "Invalid or expired visit ID for this facility.")
            
    return redirect('security_dashboard')

@login_required
@security_required
def check_out_visitor(request, visit_id):
    """
    Processes a visitor's check-out.
    """
    visit = get_object_or_404(Visit, id=visit_id, prisoner__jail=request.user.jail)
    visit.check_out_time = datetime.datetime.now()
    visit.status = 'COMPLETED'
    visit.save()
    messages.info(request, f"Visitor {visit.visitor.username} has been checked out.")
    return redirect('security_dashboard')



@login_required
@admin_required
def visit_detail_review(request, visit_id):
    """
    Displays the full details of a single visit request for an admin to review.
    This includes the visitor's photo, ID proof, and prisoner details.
    """
    # Ensure the visit exists and belongs to the admin's jail
    visit = get_object_or_404(Visit, id=visit_id, prisoner__jail=request.user.jail)
    
    context = {
        'visit': visit
    }
    return render(request, 'visitor_management/visit_detail_review.html', context)