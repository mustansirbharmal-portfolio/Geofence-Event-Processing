"""
URL configuration for vehicle_tracking app.
"""

from django.urls import path
from . import views

app_name = 'vehicle_tracking'

urlpatterns = [
    # Vehicle-specific endpoints
    path('<str:vehicle_id>/history/', views.get_vehicle_history, name='get_vehicle_history'),
    path('<str:vehicle_id>/analytics/', views.get_vehicle_analytics, name='get_vehicle_analytics'),
    
    # Fleet management
    path('active/', views.list_active_vehicles, name='list_active_vehicles'),
]
