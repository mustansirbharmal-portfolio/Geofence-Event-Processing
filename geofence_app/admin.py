"""
Django admin configuration for the main geofence application.
Provides admin interface for system monitoring and management.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from django.shortcuts import render
from django.http import JsonResponse
import json


class GeofenceSystemAdmin:
    """Custom admin interface for the geofence system."""
    
    def __init__(self):
        self.app_label = 'geofence_app'
    
    def get_urls(self):
        """Define custom admin URLs."""
        return [
            path('dashboard/', self.dashboard_view, name='geofence_dashboard'),
            path('system-status/', self.system_status_view, name='system_status'),
            path('recent-events/', self.recent_events_view, name='recent_events'),
            path('api-test/', self.api_test_view, name='api_test'),
        ]
    
    def dashboard_view(self, request):
        """Main dashboard view for system overview."""
        from .cosmos_service import cosmos_service
        from .h3_geofence_service import h3_geofence_service
        from datetime import datetime, timezone, timedelta
        
        try:
            # Get system statistics
            recent_events = cosmos_service.get_recent_events(limit=1000)
            
            # Calculate stats
            now = datetime.now(timezone.utc)
            one_hour_ago = now - timedelta(hours=1)
            twenty_four_hours_ago = now - timedelta(hours=24)
            
            events_1h = 0
            events_24h = 0
            vehicles_1h = set()
            vehicles_24h = set()
            zone_events_1h = 0
            zone_events_24h = 0
            
            for event in recent_events:
                try:
                    event_time = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                    vehicle_id = event['vehicle_id']
                    event_type = event['event_type']
                    
                    if event_time >= twenty_four_hours_ago:
                        events_24h += 1
                        vehicles_24h.add(vehicle_id)
                        
                        if event_type in ['zone_entry', 'zone_exit']:
                            zone_events_24h += 1
                        
                        if event_time >= one_hour_ago:
                            events_1h += 1
                            vehicles_1h.add(vehicle_id)
                            
                            if event_type in ['zone_entry', 'zone_exit']:
                                zone_events_1h += 1
                except:
                    pass
            
            # Get zone information
            zones = h3_geofence_service.get_all_zones()
            
            # System health check
            try:
                from monitoring import get_health_status
                health_status = get_health_status()
                system_healthy = health_status['overall_status'] == 'healthy'
            except:
                system_healthy = None
            
            context = {
                'title': 'Geofence System Dashboard',
                'stats': {
                    'total_zones': len(zones),
                    'active_vehicles_1h': len(vehicles_1h),
                    'active_vehicles_24h': len(vehicles_24h),
                    'events_1h': events_1h,
                    'events_24h': events_24h,
                    'zone_events_1h': zone_events_1h,
                    'zone_events_24h': zone_events_24h,
                },
                'system_healthy': system_healthy,
                'zones': zones[:5],  # Show first 5 zones
                'recent_events': recent_events[:10]  # Show last 10 events
            }
            
            return render(request, 'admin/geofence_app/dashboard.html', context)
            
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error loading dashboard: {str(e)}')
            return render(request, 'admin/geofence_app/dashboard.html', {
                'title': 'Geofence System Dashboard',
                'stats': {},
                'system_healthy': False,
                'zones': [],
                'recent_events': []
            })
    
    def system_status_view(self, request):
        """System status and health monitoring view."""
        try:
            from monitoring import get_health_status, get_current_metrics
            
            # Get health status
            health_status = get_health_status()
            
            # Get current metrics
            metrics = get_current_metrics()
            
            context = {
                'title': 'System Status',
                'health_status': health_status,
                'metrics': metrics,
                'timestamp': health_status.get('timestamp')
            }
            
            return render(request, 'admin/geofence_app/system_status.html', context)
            
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error loading system status: {str(e)}')
            return render(request, 'admin/geofence_app/system_status.html', {
                'title': 'System Status',
                'health_status': {'overall_status': 'error', 'error': str(e)},
                'metrics': {},
                'timestamp': None
            })
    
    def recent_events_view(self, request):
        """View recent events with filtering options."""
        from .cosmos_service import cosmos_service
        
        try:
            # Get query parameters
            event_type = request.GET.get('event_type', '')
            limit = int(request.GET.get('limit', 50))
            
            # Limit the maximum to prevent performance issues
            if limit > 500:
                limit = 500
            
            # Get events
            if event_type:
                events = cosmos_service.get_recent_events(limit=limit, event_type=event_type)
            else:
                events = cosmos_service.get_recent_events(limit=limit)
            
            # Get available event types for filter
            all_events = cosmos_service.get_recent_events(limit=1000)
            event_types = list(set(event.get('event_type', '') for event in all_events))
            event_types.sort()
            
            context = {
                'title': 'Recent Events',
                'events': events,
                'event_types': event_types,
                'current_filter': event_type,
                'current_limit': limit,
                'total_events': len(events)
            }
            
            return render(request, 'admin/geofence_app/recent_events.html', context)
            
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error loading recent events: {str(e)}')
            return render(request, 'admin/geofence_app/recent_events.html', {
                'title': 'Recent Events',
                'events': [],
                'event_types': [],
                'current_filter': '',
                'current_limit': 50,
                'total_events': 0
            })
    
    def api_test_view(self, request):
        """API testing interface."""
        if request.method == 'POST':
            try:
                import requests
                from django.conf import settings
                
                # Get form data
                endpoint = request.POST.get('endpoint')
                method = request.POST.get('method', 'GET')
                data = request.POST.get('data', '{}')
                
                # Build full URL
                base_url = request.build_absolute_uri('/api/v1/')
                full_url = f"{base_url}{endpoint.lstrip('/')}"
                
                # Parse JSON data if provided
                json_data = None
                if data.strip():
                    json_data = json.loads(data)
                
                # Make the request
                if method == 'GET':
                    response = requests.get(full_url, timeout=10)
                elif method == 'POST':
                    response = requests.post(full_url, json=json_data, timeout=10)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                # Format response
                try:
                    response_json = response.json()
                    formatted_response = json.dumps(response_json, indent=2)
                except:
                    formatted_response = response.text
                
                result = {
                    'success': True,
                    'status_code': response.status_code,
                    'response': formatted_response,
                    'url': full_url,
                    'method': method
                }
                
            except Exception as e:
                result = {
                    'success': False,
                    'error': str(e),
                    'url': full_url if 'full_url' in locals() else '',
                    'method': method
                }
        else:
            result = None
        
        # Sample API calls
        sample_calls = [
            {
                'name': 'Health Check',
                'endpoint': 'health/',
                'method': 'GET',
                'data': ''
            },
            {
                'name': 'List Zones',
                'endpoint': 'zones/',
                'method': 'GET',
                'data': ''
            },
            {
                'name': 'Recent Events',
                'endpoint': 'events/recent/?limit=10',
                'method': 'GET',
                'data': ''
            },
            {
                'name': 'Send Location Event',
                'endpoint': 'events/location/',
                'method': 'POST',
                'data': json.dumps({
                    "vehicle_id": "admin_test_vehicle",
                    "latitude": 40.7589,
                    "longitude": -73.7804
                }, indent=2)
            }
        ]
        
        context = {
            'title': 'API Testing',
            'result': result,
            'sample_calls': sample_calls
        }
        
        return render(request, 'admin/geofence_app/api_test.html', context)


# Register the custom admin
geofence_system_admin = GeofenceSystemAdmin()

# Standard Django admin registration for any models we might have
# (Currently we don't have Django models since we use Cosmos DB directly)

# Custom admin site registration
def register_geofence_admin(admin_site):
    """Register geofence admin views with the admin site."""
    # This would be called from the main admin configuration
    pass
