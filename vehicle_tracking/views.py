"""
Vehicle tracking specific views.
Handles vehicle-centric operations and analytics.
"""

import logging
from datetime import datetime, timezone, timedelta
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

from geofence_app.cosmos_service import cosmos_service
from arcgis_geofence_service import arcgis_geofence_service

logger = logging.getLogger(__name__)


@api_view(['GET'])
def get_vehicle_history(request, vehicle_id):
    """
    Get historical location and zone events for a vehicle.
    """
    try:
        # Get query parameters
        limit = int(request.GET.get('limit', 100))
        hours = int(request.GET.get('hours', 24))  # Last 24 hours by default
        
        if limit > 500:
            limit = 500
        
        # Get vehicle events
        events = cosmos_service.get_vehicle_events(vehicle_id, limit=limit)
        
        # Filter by time if specified
        if hours > 0:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            events = [
                event for event in events 
                if datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')) >= cutoff_time
            ]
        
        # Separate location and zone events
        location_events = [e for e in events if e['event_type'] == 'location_update']
        zone_events = [e for e in events if e['event_type'] in ['zone_entry', 'zone_exit']]
        
        return JsonResponse({
            'vehicle_id': vehicle_id,
            'total_events': len(events),
            'location_events': len(location_events),
            'zone_events': len(zone_events),
            'time_range_hours': hours,
            'events': events
        })
        
    except ValueError:
        return JsonResponse({
            'error': 'Invalid query parameters'
        }, status=400)
    except Exception as e:
        logger.error(f"Error getting vehicle history: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)


@api_view(['GET'])
def get_vehicle_analytics(request, vehicle_id):
    """
    Get analytics for a specific vehicle.
    """
    try:
        # Get recent events for analysis
        events = cosmos_service.get_vehicle_events(vehicle_id, limit=1000)
        
        if not events:
            return JsonResponse({
                'error': 'No data available for this vehicle'
            }, status=404)
        
        # Analyze events
        location_events = [e for e in events if e['event_type'] == 'location_update']
        zone_events = [e for e in events if e['event_type'] in ['zone_entry', 'zone_exit']]
        
        # Calculate zone visit statistics
        zone_visits = {}
        for event in zone_events:
            zone_id = event.get('zone_id')
            if zone_id:
                if zone_id not in zone_visits:
                    zone_visits[zone_id] = {'entries': 0, 'exits': 0}
                
                if event['event_type'] == 'zone_entry':
                    zone_visits[zone_id]['entries'] += 1
                elif event['event_type'] == 'zone_exit':
                    zone_visits[zone_id]['exits'] += 1
        
        # Get zone details
        zone_details = {}
        for zone_id in zone_visits.keys():
            zone = arcgis_geofence_service.get_zone_by_id(zone_id)
            if zone:
                zone_details[zone_id] = {
                    'name': zone.name,
                    'description': zone.description
                }
        
        # Calculate time ranges
        if events:
            first_event = min(events, key=lambda x: x['timestamp'])
            last_event = max(events, key=lambda x: x['timestamp'])
            
            first_time = datetime.fromisoformat(first_event['timestamp'].replace('Z', '+00:00'))
            last_time = datetime.fromisoformat(last_event['timestamp'].replace('Z', '+00:00'))
            duration_hours = (last_time - first_time).total_seconds() / 3600
        else:
            duration_hours = 0
        
        analytics = {
            'vehicle_id': vehicle_id,
            'summary': {
                'total_events': len(events),
                'location_updates': len(location_events),
                'zone_events': len(zone_events),
                'unique_zones_visited': len(zone_visits),
                'tracking_duration_hours': round(duration_hours, 2)
            },
            'zone_visits': zone_visits,
            'zone_details': zone_details,
            'first_event': events[-1] if events else None,  # Events are ordered DESC
            'last_event': events[0] if events else None
        }
        
        return JsonResponse(analytics)
        
    except Exception as e:
        logger.error(f"Error getting vehicle analytics: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)


@api_view(['GET'])
def list_active_vehicles(request):
    """
    List vehicles that have been active recently.
    """
    try:
        hours = int(request.GET.get('hours', 1))  # Last hour by default
        
        # Get recent events
        recent_events = cosmos_service.get_recent_events(limit=1000, event_type='location_update')
        
        # Filter by time
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        active_events = [
            event for event in recent_events
            if datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')) >= cutoff_time
        ]
        
        # Group by vehicle
        vehicles = {}
        for event in active_events:
            vehicle_id = event['vehicle_id']
            if vehicle_id not in vehicles:
                vehicles[vehicle_id] = {
                    'vehicle_id': vehicle_id,
                    'last_update': event['timestamp'],
                    'latitude': event['latitude'],
                    'longitude': event['longitude'],
                    'event_count': 0
                }
            
            vehicles[vehicle_id]['event_count'] += 1
            
            # Keep the most recent location
            if event['timestamp'] > vehicles[vehicle_id]['last_update']:
                vehicles[vehicle_id].update({
                    'last_update': event['timestamp'],
                    'latitude': event['latitude'],
                    'longitude': event['longitude']
                })
        
        # Add current zone information
        for vehicle_data in vehicles.values():
            # Use point classification instead of get_zones_for_location
            current_state = arcgis_geofence_service.classify_point_realtime(
                vehicle_data['longitude'], vehicle_data['latitude']
            )
            if current_state:
                vehicle_data['current_zones'] = [{'id': current_state.lower().replace(' ', '_'), 'name': current_state}]
            else:
                vehicle_data['current_zones'] = []
        
        vehicles_list = list(vehicles.values())
        vehicles_list.sort(key=lambda x: x['last_update'], reverse=True)
        
        return JsonResponse({
            'active_vehicles': vehicles_list,
            'count': len(vehicles_list),
            'time_range_hours': hours
        })
        
    except ValueError:
        return JsonResponse({
            'error': 'Invalid hours parameter'
        }, status=400)
    except Exception as e:
        logger.error(f"Error listing active vehicles: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)
