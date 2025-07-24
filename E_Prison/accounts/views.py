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
