"""
Django admin configuration for vehicle tracking.
Provides admin interface for vehicle management and monitoring.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
import json

# Since we're using Cosmos DB for data storage, we'll create custom admin views
# that interface with our services rather than traditional Django models


class VehicleTrackingAdmin:
    """Custom admin interface for vehicle tracking."""
    
    def __init__(self):
        self.app_label = 'vehicle_tracking'
    
    def get_urls(self):
        """Define custom admin URLs."""
        from django.urls import path
        return [
            path('vehicles/', self.vehicle_list_view, name='vehicle_list'),
            path('vehicles/<str:vehicle_id>/', self.vehicle_detail_view, name='vehicle_detail'),
            path('analytics/', self.analytics_view, name='vehicle_analytics'),
        ]
    
    def vehicle_list_view(self, request):
        """Display list of active vehicles."""
        from django.shortcuts import render
        from geofence_app.cosmos_service import cosmos_service
        
        try:
            # Get recent events to find active vehicles
            recent_events = cosmos_service.get_recent_events(limit=1000, event_type='location_update')
            
            # Group by vehicle
            vehicles = {}
            for event in recent_events:
                vehicle_id = event['vehicle_id']
                if vehicle_id not in vehicles:
                    vehicles[vehicle_id] = {
                        'vehicle_id': vehicle_id,
                        'last_update': event['timestamp'],
                        'latitude': event.get('latitude'),
                        'longitude': event.get('longitude'),
                        'event_count': 0
                    }
                vehicles[vehicle_id]['event_count'] += 1
            
            context = {
                'title': 'Vehicle Tracking',
                'vehicles': list(vehicles.values()),
                'total_vehicles': len(vehicles)
            }
            
            return render(request, 'admin/vehicle_tracking/vehicle_list.html', context)
            
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error loading vehicles: {str(e)}')
            return render(request, 'admin/vehicle_tracking/vehicle_list.html', {
                'title': 'Vehicle Tracking',
                'vehicles': [],
                'total_vehicles': 0
            })
    
    def vehicle_detail_view(self, request, vehicle_id):
        """Display detailed view of a specific vehicle."""
        from django.shortcuts import render
        from geofence_app.cosmos_service import cosmos_service
        from geofence_app.h3_geofence_service import h3_geofence_service
        
        try:
            # Get vehicle status
            status = cosmos_service.get_vehicle_current_status(vehicle_id)
            
            if not status:
                from django.http import Http404
                raise Http404(f"Vehicle {vehicle_id} not found")
            
            # Get vehicle events
            events = cosmos_service.get_vehicle_events(vehicle_id, limit=50)
            
            # Get zone details
            zone_details = []
            if status.get('current_zones'):
                for zone_id in status['current_zones']:
                    zone = h3_geofence_service.get_zone_by_id(zone_id)
                    if zone:
                        zone_details.append({
                            'id': zone.id,
                            'name': zone.name,
                            'description': zone.description
                        })
            
            context = {
                'title': f'Vehicle {vehicle_id}',
                'vehicle_id': vehicle_id,
                'status': status,
                'zone_details': zone_details,
                'events': events[:20],  # Show last 20 events
                'total_events': len(events)
            }
            
            return render(request, 'admin/vehicle_tracking/vehicle_detail.html', context)
            
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error loading vehicle details: {str(e)}')
            return self.vehicle_list_view(request)
    
    def analytics_view(self, request):
        """Display vehicle analytics dashboard."""
        from django.shortcuts import render
        from geofence_app.cosmos_service import cosmos_service
        
        try:
            # Get recent events for analysis
            recent_events = cosmos_service.get_recent_events(limit=5000)
            
            # Analyze data
            vehicle_stats = {}
            zone_stats = {}
            hourly_stats = {}
            
            for event in recent_events:
                vehicle_id = event['vehicle_id']
                event_type = event['event_type']
                
                # Vehicle statistics
                if vehicle_id not in vehicle_stats:
                    vehicle_stats[vehicle_id] = {
                        'total_events': 0,
                        'location_updates': 0,
                        'zone_events': 0
                    }
                
                vehicle_stats[vehicle_id]['total_events'] += 1
                
                if event_type == 'location_update':
                    vehicle_stats[vehicle_id]['location_updates'] += 1
                elif event_type in ['zone_entry', 'zone_exit']:
                    vehicle_stats[vehicle_id]['zone_events'] += 1
                    
                    # Zone statistics
                    zone_id = event.get('zone_id')
                    if zone_id:
                        if zone_id not in zone_stats:
                            zone_stats[zone_id] = {'entries': 0, 'exits': 0}
                        
                        if event_type == 'zone_entry':
                            zone_stats[zone_id]['entries'] += 1
                        else:
                            zone_stats[zone_id]['exits'] += 1
                
                # Hourly statistics
                try:
                    from datetime import datetime
                    timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                    hour = timestamp.hour
                    
                    if hour not in hourly_stats:
                        hourly_stats[hour] = 0
                    hourly_stats[hour] += 1
                except:
                    pass
            
            context = {
                'title': 'Vehicle Analytics',
                'vehicle_stats': dict(list(vehicle_stats.items())[:20]),  # Top 20 vehicles
                'zone_stats': zone_stats,
                'hourly_stats': dict(sorted(hourly_stats.items())),
                'total_vehicles': len(vehicle_stats),
                'total_events': len(recent_events)
            }
            
            return render(request, 'admin/vehicle_tracking/analytics.html', context)
            
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error loading analytics: {str(e)}')
            return render(request, 'admin/vehicle_tracking/analytics.html', {
                'title': 'Vehicle Analytics',
                'vehicle_stats': {},
                'zone_stats': {},
                'hourly_stats': {},
                'total_vehicles': 0,
                'total_events': 0
            })


# Register the custom admin
vehicle_tracking_admin = VehicleTrackingAdmin()

# Custom admin site registration
def register_vehicle_tracking_admin(admin_site):
    """Register vehicle tracking admin views with the admin site."""
    # This would be called from the main admin configuration
    pass
