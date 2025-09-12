from django.urls import path
from . import views

urlpatterns = [
    # === VISITOR MANAGEMENT URLs ===
    
    # Visitor URLs
    path('request/', views.request_visit, name='request_visit'),
    path('my-visits/', views.my_visits, name='my_visits'),

    # Admin URLs for Visit Management
    path('review/', views.review_visits, name='review_visits'),
    path('review/<int:visit_id>/', views.visit_detail_review, name='visit_detail_review'),
    path('decide/<int:visit_id>/<str:decision>/', views.decide_visit, name='decide_visit'),
    
    # === SECURITY DASHBOARD URLs ===
    
    # Security Staff URLs
    path('security/dashboard/', views.security_dashboard, name='security_dashboard'),
    path('security/check-in/', views.check_in_visitor, name='check_in_visitor'),
    path('security/check-out/<int:visit_id>/', views.check_out_visitor, name='check_out_visitor'),
    path('security/live-count/', views.get_live_visitor_count, name='get_live_visitor_count'),
    path('security/verify-visit/<int:visit_id>/', views.verify_visit_details, name='verify_visit_details'),
    
    # === EMERGENCY ALERT SYSTEM URLs ===
    
    # New Enhanced Emergency System
    path('security/emergency-alert/', views.trigger_emergency_alert, name='trigger_emergency_alert'),
    path('security/emergency-log/', views.emergency_log_view, name='emergency_log'),
    
    # Legacy Emergency System (for backward compatibility)
    path('security/trigger-alarm/', views.trigger_emergency_alarm, name='trigger_emergency_alarm'),
    
    # === ALERT MANAGEMENT URLs (Admin Only) ===
    
    path('alerts/', views.manage_alerts, name='manage_alerts'),
    path('alerts/deactivate/<int:pk>/', views.deactivate_alert, name='deactivate_alert'),
    
    # === API ENDPOINTS ===
    
    # QR Code Verification API
    path('api/visit-details/<int:visit_id>/', views.get_visit_details_json, name='get_visit_details_json'),
    
    # Debug & Development APIs
    path('debug/qr-validation/<int:visit_id>/', views.debug_qr_validation, name='debug_qr_validation'),
    path('api/check-alert/', views.check_alert_api, name='check_alert_api'),

]
