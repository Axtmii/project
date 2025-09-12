from django.urls import path
from . import views

urlpatterns = [
    # Core Authentication URLs
    path('register/', views.register, name='register'),
    path('login/visitor/', views.visitor_login, name='visitor_login'),
    path('login/staff/', views.staff_login, name='staff_login'),
    path('logout/', views.user_logout, name='logout'),

    # Dashboard Router
    path('dashboard/', views.dashboard, name='dashboard'),

    # Staff Management URLs (Admin Only)
    path('staff/manage/', views.manage_security_staff, name='manage_security_staff'),
    path('staff/delete/<int:pk>/', views.delete_security_staff, name='delete_security_staff'),

    # Blacklist Management URLs (Admin Only)
    path('blacklist/', views.blacklist_list, name='blacklist_list'),
    path('blacklist/add/', views.add_to_blacklist, name='add_to_blacklist'),
    path('blacklist/remove/<int:pk>/', views.remove_from_blacklist, name='remove_from_blacklist'),

    # --- NEW: Additional URLs for Enhanced Functionality ---
    # NEW: Aadhar-focused visitor registration (alternative to existing register)
    path('visitor/register/', views.visitor_registration, name='visitor_registration'),
    
    # NEW: Emergency Alert API (fixes the 404 error)
    path('api/check-alert/', views.check_alert_api, name='check_alert_api'),
    
    # NEW: Aadhar information update for existing users
    path('profile/update-aadhar/', views.update_aadhar_info, name='update_aadhar_info'),
]
