# visitor_management/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Visitor URLs
    path('request/', views.request_visit, name='request_visit'),
    path('my-visits/', views.my_visits, name='my_visits'),

    # Admin URLs for Visit Management
    path('review/', views.review_visits, name='review_visits'),
    path('decide/<int:visit_id>/<str:decision>/', views.decide_visit, name='decide_visit'),
    path('review/<int:visit_id>/', views.visit_detail_review, name='visit_detail_review'),


    # Security Staff URLs
    path('security/dashboard/', views.security_dashboard, name='security_dashboard'),
    path('security/check-in/', views.check_in_visitor, name='check_in_visitor'),
    path('security/check-out/<int:visit_id>/', views.check_out_visitor, name='check_out_visitor'),
]