"""
URL configuration for taxi-specific API endpoints.
"""

from django.urls import path
from . import taxi_views

urlpatterns = [
    # Taxi status endpoints
    path('taxis/', taxi_views.get_all_taxis_status, name='all_taxis_status'),
    path('taxis/<str:taxi_id>/', taxi_views.get_taxi_status, name='taxi_status'),
    path('taxis/<str:taxi_id>/route/', taxi_views.get_taxi_route_history, name='taxi_route_history'),
    
    # State-based taxi queries
    path('states/<str:state_name>/taxis/', taxi_views.get_taxis_by_state, name='taxis_by_state'),
    path('states/<str:state_name>/activity/', taxi_views.get_state_taxi_activity, name='state_taxi_activity'),
    
    # Health check
    path('health/', taxi_views.taxi_health_check, name='taxi_health_check'),
]
