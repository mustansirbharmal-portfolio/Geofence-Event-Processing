"""
API views specifically for taxi data and operations.
Uses the dedicated taxi-data Cosmos DB container.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from taxi_cosmos_service import taxi_cosmos_service
from arcgis_geofence_service import arcgis_geofence_service

logger = logging.getLogger(__name__)


@api_view(['GET'])
def get_all_taxis_status(request):
    """
    Get the current status of all active taxis.
    
    Returns current location and state for each taxi.
    """
    try:
        hours = int(request.GET.get('hours', 1))
        
        # Get all active taxis
        active_taxis = taxi_cosmos_service.get_all_active_taxis(hours=hours)
        
        # Enhance with current state information
        taxis_with_states = []
        for taxi in active_taxis:
            # Get current state using ArcGIS service
            current_state = arcgis_geofence_service.classify_point_realtime(
                taxi['longitude'], taxi['latitude']
            )
            
            taxi_info = {
                'taxi_id': taxi['taxi_id'],
                'latitude': taxi['latitude'],
                'longitude': taxi['longitude'],
                'timestamp': taxi['timestamp'],
                'current_state': current_state,
                'metadata': taxi.get('metadata', {})
            }
            taxis_with_states.append(taxi_info)
        
        return JsonResponse({
            'taxis': taxis_with_states,
            'count': len(taxis_with_states),
            'time_range_hours': hours
        })
        
    except ValueError:
        return JsonResponse({
            'error': 'Invalid hours parameter'
        }, status=400)
    except Exception as e:
        logger.error(f"Error getting all taxis status: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)


@api_view(['GET'])
def get_taxi_status(request, taxi_id):
    """
    Get the current status of a specific taxi.
    
    Returns current location, state, and recent activity.
    """
    try:
        # Get taxi status from taxi-data container
        status = taxi_cosmos_service.get_taxi_current_status(taxi_id)
        
        if not status:
            return JsonResponse({
                'error': 'Taxi not found or no location data available'
            }, status=404)
        
        # Enhance with current state information
        if status['latest_location']:
            current_state = arcgis_geofence_service.classify_point_realtime(
                status['latest_location']['longitude'], 
                status['latest_location']['latitude']
            )
            status['current_state'] = current_state
        
        # Get recent events
        recent_events = taxi_cosmos_service.get_taxi_events(taxi_id, limit=10)
        status['recent_events'] = recent_events
        
        return JsonResponse(status)
        
    except Exception as e:
        logger.error(f"Error getting taxi status: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)


@api_view(['GET'])
def get_taxis_by_state(request, state_name):
    """
    Get all taxis currently in a specific state.
    """
    try:
        hours = int(request.GET.get('hours', 1))
        
        # Get all active taxis
        active_taxis = taxi_cosmos_service.get_all_active_taxis(hours=hours)
        
        # Filter by state
        taxis_in_state = []
        for taxi in active_taxis:
            current_state = arcgis_geofence_service.classify_point_realtime(
                taxi['longitude'], taxi['latitude']
            )
            
            if current_state and current_state.lower().replace(' ', '_') == state_name.lower():
                taxi_info = {
                    'taxi_id': taxi['taxi_id'],
                    'latitude': taxi['latitude'],
                    'longitude': taxi['longitude'],
                    'timestamp': taxi['timestamp'],
                    'current_state': current_state,
                    'metadata': taxi.get('metadata', {})
                }
                taxis_in_state.append(taxi_info)
        
        return JsonResponse({
            'state_name': state_name,
            'taxis': taxis_in_state,
            'count': len(taxis_in_state),
            'time_range_hours': hours
        })
        
    except ValueError:
        return JsonResponse({
            'error': 'Invalid hours parameter'
        }, status=400)
    except Exception as e:
        logger.error(f"Error getting taxis by state: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)


@api_view(['GET'])
def get_taxi_route_history(request, taxi_id):
    """
    Get the route history for a specific taxi.
    """
    try:
        limit = int(request.GET.get('limit', 50))
        
        # Get taxi location events
        location_events = taxi_cosmos_service.get_taxi_events(
            taxi_id, 
            limit=limit, 
            event_type='taxi_location'
        )
        
        # Process into route points
        route_points = []
        for event in location_events:
            # Get state for this location
            current_state = arcgis_geofence_service.classify_point_realtime(
                event['longitude'], event['latitude']
            )
            
            route_point = {
                'latitude': event['latitude'],
                'longitude': event['longitude'],
                'timestamp': event['timestamp'],
                'state': current_state,
                'metadata': event.get('metadata', {})
            }
            route_points.append(route_point)
        
        return JsonResponse({
            'taxi_id': taxi_id,
            'route_points': route_points,
            'count': len(route_points),
            'limit': limit
        })
        
    except ValueError:
        return JsonResponse({
            'error': 'Invalid limit parameter'
        }, status=400)
    except Exception as e:
        logger.error(f"Error getting taxi route history: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)


@api_view(['GET'])
def get_state_taxi_activity(request, state_name):
    """
    Get taxi activity statistics for a specific state.
    """
    try:
        hours = int(request.GET.get('hours', 24))
        
        # Get state events from taxi-data container
        state_events = taxi_cosmos_service.get_state_events(state_name, limit=1000)
        
        # Filter by time if specified
        if hours > 0:
            from datetime import timedelta
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            state_events = [
                event for event in state_events
                if datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')) >= cutoff_time
            ]
        
        # Analyze events
        entries = [e for e in state_events if e['event_type'] == 'state_entry']
        exits = [e for e in state_events if e['event_type'] == 'state_exit']
        
        # Taxi activity
        unique_taxis = set()
        taxi_activity = {}
        
        for event in state_events:
            taxi_id = event['taxi_id']
            unique_taxis.add(taxi_id)
            
            if taxi_id not in taxi_activity:
                taxi_activity[taxi_id] = {'entries': 0, 'exits': 0}
            
            if event['event_type'] == 'state_entry':
                taxi_activity[taxi_id]['entries'] += 1
            elif event['event_type'] == 'state_exit':
                taxi_activity[taxi_id]['exits'] += 1
        
        # Current occupancy estimate
        current_taxis = set()
        for event in sorted(state_events, key=lambda x: x['timestamp']):
            taxi_id = event['taxi_id']
            if event['event_type'] == 'state_entry':
                current_taxis.add(taxi_id)
            elif event['event_type'] == 'state_exit':
                current_taxis.discard(taxi_id)
        
        analytics = {
            'state_name': state_name,
            'time_range_hours': hours,
            'summary': {
                'total_events': len(state_events),
                'total_entries': len(entries),
                'total_exits': len(exits),
                'unique_taxis': len(unique_taxis),
                'estimated_current_taxis': len(current_taxis)
            },
            'taxi_activity': taxi_activity,
            'current_taxis': list(current_taxis),
            'recent_events': state_events[:20]  # Last 20 events
        }
        
        return JsonResponse(analytics)
        
    except ValueError:
        return JsonResponse({
            'error': 'Invalid query parameters'
        }, status=400)
    except Exception as e:
        logger.error(f"Error getting state taxi activity: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)


@api_view(['GET'])
def taxi_health_check(request):
    """
    Health check endpoint for taxi services.
    """
    try:
        # Test taxi container connection
        taxi_cosmos_service.get_all_active_taxis(hours=1)
        
        # Test ArcGIS service
        states_count = len(arcgis_geofence_service.get_all_zones())
        
        return JsonResponse({
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'services': {
                'taxi_cosmos_db': 'connected',
                'arcgis_service': f'{states_count} states configured'
            }
        })
        
    except Exception as e:
        logger.error(f"Taxi health check failed: {e}")
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, status=503)
