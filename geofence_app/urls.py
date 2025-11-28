"""
URL configuration for geofence_app.
"""

from django.urls import path
from . import views
from . import taxi_simulation_views

app_name = 'geofence_app'

urlpatterns = [
    # Location and event endpoints
    path('events/location/', views.process_location_event, name='process_location_event'),
    path('events/recent/', views.get_recent_events, name='get_recent_events'),
    
    # Vehicle endpoints
    path('vehicles/<str:vehicle_id>/status/', views.get_vehicle_status, name='get_vehicle_status'),
    path('vehicles/<str:vehicle_id>/events/', views.get_vehicle_events, name='get_vehicle_events'),
    
    # Zone endpoints
    path('zones/', views.list_zones, name='list_zones'),
    path('zones/summary/', views.get_zones_summary, name='get_zones_summary'),
    path('zones/<str:zone_id>/', views.get_zone_details, name='get_zone_details'),
    path('zones/<str:zone_id>/events/', views.get_zone_events, name='get_zone_events'),
    
    # Taxi Simulation endpoints
    path('simulation/start/', taxi_simulation_views.start_simulation, name='start_simulation'),
    path('simulation/stop/', taxi_simulation_views.stop_simulation, name='stop_simulation'),
    path('simulation/status/', taxi_simulation_views.simulation_status, name='simulation_status'),
    path('simulation/metrics/', taxi_simulation_views.simulation_metrics, name='simulation_metrics'),
    path('simulation/reset/', taxi_simulation_views.reset_simulation, name='reset_simulation'),
    path('simulation/taxi/<str:taxi_id>/', taxi_simulation_views.taxi_details, name='taxi_details'),
    
    # Health and monitoring
    path('health/', views.health_check, name='health_check'),
    path('health/detailed/', views.detailed_health_check, name='detailed_health_check'),
    path('metrics/', views.get_metrics, name='get_metrics'),
    
    # Dashboard
    path('dashboard/', views.taxi_dashboard, name='taxi_dashboard'),
]
