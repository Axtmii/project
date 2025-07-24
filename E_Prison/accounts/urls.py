
from django.urls import path
from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    path("visitor-login/", views.visitor_login, name="visitor_login"),
    path("staff-login/", views.staff_login, name="staff_login"),
    path("logout/", views.user_logout, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),]
