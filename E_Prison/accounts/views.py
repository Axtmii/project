from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm


def register(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created successfully! Please login.")
            return redirect("visitor_login")  # ✅ important redirect
    else:
        form = UserRegisterForm()
    return render(request, "accounts/register.html", {"form": form})




def user_logout(request):
    logout(request)
    return redirect("visitor_login")  # Redirect to visitor login after logout



@login_required
def dashboard(request):
    user = request.user
    if user.role == "admin":
        return render(request, "accounts/admin_dashboard.html", {"user": user})
    elif user.role == "security":
        return render(request, "accounts/security_dashboard.html", {"user": user})
    else:
        return render(request, "accounts/visitor_dashboard.html", {"user": user})


from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages

def visitor_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None and user.role in ["family", "visitor"]:
            login(request, user)
            return redirect("dashboard")
        else:
            messages.error(request, "Invalid visitor credentials")
    return render(request, "accounts/visitor_login.html")

def staff_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None and user.role in ["admin", "security"]:
            login(request, user)
            return redirect("dashboard")
        else:
            messages.error(request, "Invalid staff credentials")
    return render(request, "accounts/staff_login.html")

from django.shortcuts import render


def landing_page(request):
    """
    Renders the public-facing landing page for the application.
    
    If the user is already authenticated, it redirects them straight 
    to their dashboard to improve user experience.
    """
    if request.user.is_authenticated:
        # This line causes the redirect for logged-in users.
        return redirect('dashboard')
    
    # Unauthenticated users will see the landing page.
    return render(request, 'landing_page.html')

# accounts/views.py

from .models import User, Blacklist
from accounts.decorators import admin_required
# ... (other imports) ...
from django.shortcuts import get_object_or_404


@login_required
@admin_required
def blacklist_list(request):
    """ Displays a list of all blacklisted users. """
    blacklisted_users = Blacklist.objects.select_related('user', 'blacklisted_by').all()
    
    # Also get a list of users who are not yet blacklisted to add them
    non_blacklisted_users = User.objects.filter(
        role__in=['visitor', 'family'], 
        blacklist_entry__isnull=True
    )

    context = {
        'blacklisted_users': blacklisted_users,
        'non_blacklisted_users': non_blacklisted_users
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
        
        Blacklist.objects.create(
            user=user_to_blacklist,
            reason=reason,
            blacklisted_by=request.user
        )
        messages.success(request, f"User {user_to_blacklist.username} has been successfully blacklisted.")
    return redirect('blacklist_list')

@login_required
@admin_required
def remove_from_blacklist(request, pk):
    """ Removes a user from the blacklist. """
    blacklist_entry = get_object_or_404(Blacklist, pk=pk)
    username = blacklist_entry.user.username
    blacklist_entry.delete()
    messages.info(request, f"User {username} has been removed from the blacklist.")
    return redirect('blacklist_list')