"""
Django admin configuration for zone management.
Provides admin interface for geofence zone management and analytics.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.shortcuts import render
import json


class ZoneManagementAdmin:
    """Custom admin interface for zone management."""
    
    def __init__(self):
        self.app_label = 'zone_management'
    
    def get_urls(self):
        """Define custom admin URLs."""
        from django.urls import path
        return [
            path('zones/', self.zone_list_view, name='zone_list'),
            path('zones/<str:zone_id>/', self.zone_detail_view, name='zone_detail'),
            path('zones/<str:zone_id>/analytics/', self.zone_analytics_view, name='zone_analytics'),
            path('create-zone/', self.create_zone_view, name='create_zone'),
        ]
    
    def zone_list_view(self, request):
        """Display list of all geofence zones."""
        from geofence_app.h3_geofence_service import h3_geofence_service
        from geofence_app.cosmos_service import cosmos_service
        
        try:
            zones = h3_geofence_service.get_all_zones()
            
            # Enhance zones with recent activity data
            enhanced_zones = []
            for zone in zones:
                try:
                    # Get recent events for this zone
                    recent_events = cosmos_service.get_zone_events(zone.id, limit=100)
                    
                    # Calculate basic stats
                    entries = len([e for e in recent_events if e['event_type'] == 'zone_entry'])
                    exits = len([e for e in recent_events if e['event_type'] == 'zone_exit'])
                    unique_vehicles = len(set(e['vehicle_id'] for e in recent_events))
                    
                    # Get zone statistics
                    stats = h3_geofence_service.get_zone_statistics(zone.id)
                    
                    enhanced_zones.append({
                        'zone': zone,
                        'stats': stats,
                        'recent_activity': {
                            'entries': entries,
                            'exits': exits,
                            'unique_vehicles': unique_vehicles,
                            'total_events': len(recent_events)
                        }
                    })
                except Exception as e:
                    # If there's an error getting stats for this zone, still include it
                    enhanced_zones.append({
                        'zone': zone,
                        'stats': {'error': str(e)},
                        'recent_activity': {
                            'entries': 0,
                            'exits': 0,
                            'unique_vehicles': 0,
                            'total_events': 0
                        }
                    })
            
            context = {
                'title': 'Geofence Zones',
                'zones': enhanced_zones,
                'total_zones': len(zones)
            }
            
            return render(request, 'admin/zone_management/zone_list.html', context)
            
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error loading zones: {str(e)}')
            return render(request, 'admin/zone_management/zone_list.html', {
                'title': 'Geofence Zones',
                'zones': [],
                'total_zones': 0
            })
    
    def zone_detail_view(self, request, zone_id):
        """Display detailed view of a specific zone."""
        from geofence_app.h3_geofence_service import h3_geofence_service
        from geofence_app.cosmos_service import cosmos_service
        
        try:
            # Get zone information
            zone = h3_geofence_service.get_zone_by_id(zone_id)
            
            if not zone:
                from django.http import Http404
                raise Http404(f"Zone {zone_id} not found")
            
            # Get zone statistics
            stats = h3_geofence_service.get_zone_statistics(zone_id)
            
            # Get recent zone events
            recent_events = cosmos_service.get_zone_events(zone_id, limit=50)
            
            # Analyze events
            entries = [e for e in recent_events if e['event_type'] == 'zone_entry']
            exits = [e for e in recent_events if e['event_type'] == 'zone_exit']
            
            # Current occupancy estimate
            current_vehicles = set()
            for event in sorted(recent_events, key=lambda x: x['timestamp']):
                vehicle_id = event['vehicle_id']
                if event['event_type'] == 'zone_entry':
                    current_vehicles.add(vehicle_id)
                elif event['event_type'] == 'zone_exit':
                    current_vehicles.discard(vehicle_id)
            
            # Vehicle activity
            vehicle_activity = {}
            for event in recent_events:
                vehicle_id = event['vehicle_id']
                if vehicle_id not in vehicle_activity:
                    vehicle_activity[vehicle_id] = {'entries': 0, 'exits': 0}
                
                if event['event_type'] == 'zone_entry':
                    vehicle_activity[vehicle_id]['entries'] += 1
                elif event['event_type'] == 'zone_exit':
                    vehicle_activity[vehicle_id]['exits'] += 1
            
            context = {
                'title': f'Zone: {zone.name}',
                'zone': zone,
                'stats': stats,
                'activity': {
                    'total_entries': len(entries),
                    'total_exits': len(exits),
                    'current_occupancy': len(current_vehicles),
                    'unique_vehicles': len(vehicle_activity)
                },
                'current_vehicles': list(current_vehicles),
                'vehicle_activity': dict(list(vehicle_activity.items())[:10]),  # Top 10
                'recent_events': recent_events[:20]  # Last 20 events
            }
            
            return render(request, 'admin/zone_management/zone_detail.html', context)
            
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error loading zone details: {str(e)}')
            return self.zone_list_view(request)
    
    def zone_analytics_view(self, request, zone_id):
        """Display analytics for a specific zone."""
        from geofence_app.h3_geofence_service import h3_geofence_service
        from geofence_app.cosmos_service import cosmos_service
        from datetime import datetime, timezone, timedelta
        
        try:
            # Get zone information
            zone = h3_geofence_service.get_zone_by_id(zone_id)
            
            if not zone:
                from django.http import Http404
                raise Http404(f"Zone {zone_id} not found")
            
            # Get time range from query params
            hours = int(request.GET.get('hours', 24))
            
            # Get zone events
            zone_events = cosmos_service.get_zone_events(zone_id, limit=2000)
            
            # Filter by time if specified
            if hours > 0:
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
                zone_events = [
                    event for event in zone_events
                    if datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')) >= cutoff_time
                ]
            
            # Analyze events
            entries = [e for e in zone_events if e['event_type'] == 'zone_entry']
            exits = [e for e in zone_events if e['event_type'] == 'zone_exit']
            
            # Hourly distribution
            hourly_stats = {}
            for event in zone_events:
                try:
                    timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                    hour = timestamp.hour
                    
                    if hour not in hourly_stats:
                        hourly_stats[hour] = {'entries': 0, 'exits': 0}
                    
                    if event['event_type'] == 'zone_entry':
                        hourly_stats[hour]['entries'] += 1
                    elif event['event_type'] == 'zone_exit':
                        hourly_stats[hour]['exits'] += 1
                except:
                    pass
            
            # Daily distribution (if looking at more than 24 hours)
            daily_stats = {}
            if hours > 24:
                for event in zone_events:
                    try:
                        timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                        date = timestamp.date().isoformat()
                        
                        if date not in daily_stats:
                            daily_stats[date] = {'entries': 0, 'exits': 0}
                        
                        if event['event_type'] == 'zone_entry':
                            daily_stats[date]['entries'] += 1
                        elif event['event_type'] == 'zone_exit':
                            daily_stats[date]['exits'] += 1
                    except:
                        pass
            
            # Vehicle frequency
            vehicle_frequency = {}
            for event in zone_events:
                vehicle_id = event['vehicle_id']
                if vehicle_id not in vehicle_frequency:
                    vehicle_frequency[vehicle_id] = 0
                vehicle_frequency[vehicle_id] += 1
            
            # Sort by frequency
            top_vehicles = sorted(
                vehicle_frequency.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]
            
            context = {
                'title': f'Analytics: {zone.name}',
                'zone': zone,
                'time_range_hours': hours,
                'summary': {
                    'total_events': len(zone_events),
                    'total_entries': len(entries),
                    'total_exits': len(exits),
                    'unique_vehicles': len(vehicle_frequency)
                },
                'hourly_stats': dict(sorted(hourly_stats.items())),
                'daily_stats': dict(sorted(daily_stats.items())) if daily_stats else {},
                'top_vehicles': top_vehicles,
                'recent_events': zone_events[:50]
            }
            
            return render(request, 'admin/zone_management/zone_analytics.html', context)
            
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error loading zone analytics: {str(e)}')
            return self.zone_detail_view(request, zone_id)
    
    def create_zone_view(self, request):
        """Create a new geofence zone."""
        if request.method == 'POST':
            try:
                from geofence_app.h3_geofence_service import h3_geofence_service
                
                # Get form data
                zone_id = request.POST.get('zone_id')
                name = request.POST.get('name')
                description = request.POST.get('description')
                center_lat = float(request.POST.get('center_lat'))
                center_lng = float(request.POST.get('center_lng'))
                radius_km = float(request.POST.get('radius_km'))
                
                # Validate inputs
                if not all([zone_id, name, description]):
                    raise ValueError("All fields are required")
                
                if not (-90 <= center_lat <= 90):
                    raise ValueError("Invalid latitude")
                
                if not (-180 <= center_lng <= 180):
                    raise ValueError("Invalid longitude")
                
                if radius_km <= 0 or radius_km > 50:
                    raise ValueError("Radius must be between 0 and 50 km")
                
                # Create the zone
                zone = h3_geofence_service.create_zone(
                    id=zone_id,
                    name=name,
                    description=description,
                    center_lat=center_lat,
                    center_lng=center_lng,
                    radius_km=radius_km
                )
                
                from django.contrib import messages
                messages.success(request, f'Zone "{name}" created successfully!')
                
                # Redirect to zone detail
                from django.shortcuts import redirect
                return redirect('admin:zone_detail', zone_id=zone_id)
                
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f'Error creating zone: {str(e)}')
        
        context = {
            'title': 'Create New Zone'
        }
        
        return render(request, 'admin/zone_management/create_zone.html', context)


# Register the custom admin
zone_management_admin = ZoneManagementAdmin()

# Custom admin site registration
def register_zone_management_admin(admin_site):
    """Register zone management admin views with the admin site."""
    # This would be called from the main admin configuration
    pass
