"""
URL configuration for ArcGIS-based geofencing endpoints.
"""

from django.urls import path
from . import arcgis_views

app_name = 'arcgis_geofence'

urlpatterns = [
    # Location event processing
    path('events/location/', arcgis_views.process_arcgis_location_event, name='process_location'),
    
    # Vehicle status and tracking
    path('vehicles/<str:vehicle_id>/status/', arcgis_views.get_vehicle_status_arcgis, name='vehicle_status'),
    path('vehicles/search/', arcgis_views.search_vehicles_by_state, name='search_vehicles'),
    
    # State/zone management
    path('states/', arcgis_views.get_all_states, name='all_states'),
    
    # Simulation control
    path('simulation/status/', arcgis_views.get_simulation_status, name='simulation_status'),
    path('simulation/start/', arcgis_views.start_simulation, name='start_simulation'),
    path('simulation/stop/', arcgis_views.stop_simulation, name='stop_simulation'),
    path('simulation/search/', arcgis_views.search_taxis_by_zone, name='search_taxis'),
    
    # Trace events
    path('trace-events/', arcgis_views.get_trace_events, name='trace_events'),
]
