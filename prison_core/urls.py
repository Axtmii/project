# prison_core/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Jail Management URLs
    path('jails/', views.jail_list, name='jail_list'),
    path('jails/new/', views.JailCreateView.as_view(), name='jail_create'),
    path('jails/edit/<int:pk>/', views.JailUpdateView.as_view(), name='jail_update'),
    path('jails/delete/<int:pk>/', views.JailDeleteView.as_view(), name='jail_delete'),

    # Prisoner Management URLs
    path('prisoners/', views.prisoner_list, name='prisoner_list'),
    path('prisoners/new/', views.prisoner_create, name='prisoner_create'),
    path('prisoners/<int:pk>/', views.prisoner_detail, name='prisoner_detail'),
    # Add paths for prisoner_update and prisoner_delete here if you create those views
]