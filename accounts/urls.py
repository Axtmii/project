from django.urls import path
from . import views

urlpatterns = [
    # === CORE AUTHENTICATION URLs ===
    
    # Traditional registration and login
    path('register/', views.register, name='register'),
    path('login/visitor/', views.visitor_login, name='visitor_login'),
    path('login/staff/', views.staff_login, name='staff_login'),
    path('logout/', views.user_logout, name='user_logout'),  # Fixed: Added missing 'user_' prefix

    # Enhanced visitor registration (alternative registration flow)
    path('visitor/register/', views.visitor_registration, name='visitor_registration'),

    # === DASHBOARD ROUTER ===
    
    path('dashboard/', views.dashboard, name='dashboard'),

    # === PROFILE MANAGEMENT URLs ===
    
    # User Profile Management
    path('profile/', views.user_profile, name='user_profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/update-aadhar/', views.update_aadhar_info, name='update_aadhar_info'),
    
    # Family Relationship Management
    # path('family/', views.family_management, name='family_management'),

    # === STAFF MANAGEMENT URLs (Admin Only) ===
    
    path('staff/manage/', views.manage_security_staff, name='manage_security_staff'),
    path('staff/delete/<int:pk>/', views.delete_security_staff, name='delete_security_staff'),

    # === BLACKLIST MANAGEMENT URLs (Admin Only) ===
    
    path('blacklist/', views.blacklist_list, name='blacklist_list'),
    path('blacklist/add/', views.add_to_blacklist, name='add_to_blacklist'),
    path('blacklist/remove/<int:pk>/', views.remove_from_blacklist, name='remove_from_blacklist'),

    # === API ENDPOINTS ===
    
    # Emergency Alert System APIs
    path('api/check-alert/', views.check_alert_api, name='check_alert_api'),
    
    # Family Management APIs
    path('api/family-members/', views.get_family_members_api, name='get_family_members_api'),
    
    # === ADMIN UTILITIES ===
    
    # Enhanced user management for admins
    # path('admin/users/', views.admin_user_list, name='admin_user_list'),
    # path('admin/users/<int:user_id>/', views.admin_user_detail, name='admin_user_detail'),
    # path('admin/family-relations/', views.admin_family_relations, name='admin_family_relations'),
]
