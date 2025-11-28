"""
API views for geofence event processing.
Handles location events, zone detection, and vehicle status queries.
"""

import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator

from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import AnonRateThrottle

from .cosmos_service import cosmos_service
# H3 geofence service REMOVED - we now use ArcGIS API for US state-level geofencing
try:
    from monitoring import get_current_metrics, get_health_status
except ImportError:
    # Fallback if monitoring module is not available
    def get_current_metrics():
        return {}
    def get_health_status():
        return {'status': 'ok'}

logger = logging.getLogger(__name__)


class LocationEventThrottle(AnonRateThrottle):
    """Custom throttle for location events."""
    rate = '100/minute'


@api_view(['POST'])
@throttle_classes([LocationEventThrottle])
@csrf_exempt
def process_location_event(request):
    """
    Process incoming GPS location events from vehicles.
    
    Expected payload:
    {
        "vehicle_id": "taxi_001",
        "latitude": 40.7589,
        "longitude": -73.7804,
        "timestamp": "2024-01-01T12:00:00Z",  // optional
        "metadata": {  // optional
            "speed": 45.5,
            "heading": 180,
            "accuracy": 5.0
        }
    }
    """
    try:
        # Parse request data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()
        
        # Validate required fields
        required_fields = ['vehicle_id', 'latitude', 'longitude']
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'error': f'Missing required field: {field}'
                }, status=400)
        
        vehicle_id = data['vehicle_id']
        latitude = float(data['latitude'])
        longitude = float(data['longitude'])
        
        # Validate coordinates
        if not (-90 <= latitude <= 90):
            return JsonResponse({
                'error': 'Invalid latitude. Must be between -90 and 90'
            }, status=400)
        
        if not (-180 <= longitude <= 180):
            return JsonResponse({
                'error': 'Invalid longitude. Must be between -180 and 180'
            }, status=400)
        
        # Parse optional timestamp
        timestamp = None
        if 'timestamp' in data:
            try:
                timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
            except ValueError:
                return JsonResponse({
                    'error': 'Invalid timestamp format. Use ISO 8601 format'
                }, status=400)
        
        metadata = data.get('metadata', {})
        
        # Get previous zones for this vehicle
        previous_status = cosmos_service.get_vehicle_current_status(vehicle_id)
        previous_zones = set()
        if previous_status and 'current_zones' in previous_status:
            previous_zones = set(previous_status['current_zones'])
        
        # Store location event
        event_id = cosmos_service.store_location_event(
            vehicle_id=vehicle_id,
            latitude=latitude,
            longitude=longitude,
            timestamp=timestamp,
            metadata=metadata
        )
        
        # Use ArcGIS service for state-level geofencing
        from arcgis_geofence_service import arcgis_geofence_service
        
        # Also store in taxi-specific container if this is a taxi
        if vehicle_id.startswith('taxi_'):
            try:
                from taxi_cosmos_service import taxi_cosmos_service
                taxi_cosmos_service.store_taxi_location(
                    taxi_id=vehicle_id,
                    latitude=latitude,
                    longitude=longitude,
                    timestamp=timestamp,
                    metadata=metadata
                )
            except Exception as e:
                logger.warning(f"Failed to store taxi data: {e}")
        
        # Get current state/zone
        current_state = arcgis_geofence_service.classify_point_realtime(longitude, latitude)
        
        # Store zone events (simplified for state-level)
        zone_events = []
        current_zone_info = []
        
        if current_state:
            # Create zone info for current state
            current_zone_info = [{
                'id': current_state.lower().replace(' ', '_'), 
                'name': current_state
            }]
            
            # For now, we'll skip complex zone transition detection
            # and just record the current state location
            # This can be enhanced later with state transition tracking
        
        response_data = {
            'success': True,
            'event_id': event_id,
            'vehicle_id': vehicle_id,
            'processed_at': datetime.now(timezone.utc).isoformat(),
            'current_zones': current_zone_info,
            'zone_events': zone_events,
            'current_state': current_state,
            'metadata': metadata
        }
        
        logger.info(f"Processed location event for vehicle {vehicle_id}")
        
        return JsonResponse(response_data, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON payload'
        }, status=400)
    except ValueError as e:
        return JsonResponse({
            'error': f'Invalid data: {str(e)}'
        }, status=400)
    except Exception as e:
        logger.error(f"Error processing location event: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)


@api_view(['GET'])
def get_vehicle_status(request, vehicle_id):
    """
    Get the current status of a specific vehicle.
    
    Returns current location, zones, and recent activity.
    """
    try:
        # Get vehicle status from Cosmos DB
        status = cosmos_service.get_vehicle_current_status(vehicle_id)
        
        if not status:
            return JsonResponse({
                'error': 'Vehicle not found or no location data available'
            }, status=404)
        
        # Enhance with zone information using ArcGIS service
        from arcgis_geofence_service import arcgis_geofence_service
        if status['current_zones']:
            zone_details = []
            for zone_id in status['current_zones']:
                zone = arcgis_geofence_service.get_zone_by_id(zone_id)
                if zone:
                    zone_details.append({
                        'id': zone.id,
                        'name': zone.name,
                        'description': zone.description
                    })
            status['zone_details'] = zone_details
        
        # Get recent events
        recent_events = cosmos_service.get_vehicle_events(vehicle_id, limit=10)
        status['recent_events'] = recent_events
        
        return JsonResponse(status)
        
    except Exception as e:
        logger.error(f"Error getting vehicle status: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)


@api_view(['GET'])
def get_zone_status(request, zone_id):
    """
    Get the current status of a specific geofence zone.
    
    Returns zone information and recent activity.
    """
    try:
        # Get zone information using ArcGIS service
        from arcgis_geofence_service import arcgis_geofence_service
        zone = arcgis_geofence_service.get_zone_by_id(zone_id)
        
        if not zone:
            return JsonResponse({
                'error': 'Zone not found'
            }, status=404)
        
        # ArcGIS service doesn't have zone statistics, use empty dict
        stats = {}
        
        # Get recent zone events
        recent_events = cosmos_service.get_zone_events(zone_id, limit=20)
        
        # Count current vehicles in zone
        current_vehicles = set()
        for event in recent_events:
            vehicle_id = event['vehicle_id']
            if event['event_type'] == 'zone_entry':
                current_vehicles.add(vehicle_id)
            elif event['event_type'] == 'zone_exit':
                current_vehicles.discard(vehicle_id)
        
        response_data = {
            'zone_id': zone.id,
            'name': zone.name,
            'description': zone.description,
            'center': {
                'latitude': zone.center_lat,
                'longitude': zone.center_lng
            },
            'radius_km': zone.radius_km,
            'statistics': stats,
            'current_vehicles_count': len(current_vehicles),
            'current_vehicles': list(current_vehicles),
            'recent_events': recent_events
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error getting zone status: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)


@api_view(['GET'])
def list_zones(request):
    """
    List all available geofence zones.
    """
    try:
        # Get zones using ArcGIS service
        from arcgis_geofence_service import arcgis_geofence_service
        zones = arcgis_geofence_service.get_all_zones()
        
        zones_data = []
        for zone in zones:
            zones_data.append({
                'id': zone.id,
                'name': zone.name,
                'description': zone.description,
                'center': {
                    'latitude': zone.center_lat,
                    'longitude': zone.center_lng
                },
                'radius_km': getattr(zone, 'radius_km', 100.0),  # Default radius for state zones
                'statistics': {}  # ArcGIS service doesn't have zone statistics
            })
        
        return JsonResponse({
            'zones': zones_data,
            'total_count': len(zones_data)
        })
        
    except Exception as e:
        logger.error(f"Error listing zones: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)


@api_view(['GET'])
def get_recent_events(request):
    """
    Get recent events across all vehicles and zones.
    """
    try:
        limit = int(request.GET.get('limit', 50))
        event_type = request.GET.get('type')
        
        # Validate limit
        if limit > 200:
            limit = 200
        
        events = cosmos_service.get_recent_events(limit=limit, event_type=event_type)
        
        return JsonResponse({
            'events': events,
            'count': len(events),
            'limit': limit,
            'event_type_filter': event_type
        })
        
    except ValueError:
        return JsonResponse({
            'error': 'Invalid limit parameter'
        }, status=400)
    except Exception as e:
        logger.error(f"Error getting recent events: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)


@api_view(['GET'])
def health_check(request):
    """
    Health check endpoint for monitoring.
    """
    try:
        # Test Cosmos DB connection
        cosmos_service.get_recent_events(limit=1)
        
        # Test ArcGIS service
        from arcgis_geofence_service import arcgis_geofence_service
        zones_count = len(arcgis_geofence_service.get_all_zones())
        
        # Test cache
        from django.core.cache import cache
        cache.set('health_check', 'ok', 60)
        cache_status = cache.get('health_check')
        
        return JsonResponse({
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'services': {
                'cosmos_db': 'connected',
                'arcgis_service': f'{zones_count} zones configured',
                'cache': 'working' if cache_status == 'ok' else 'error'
            }
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, status=503)


@api_view(['GET'])
def detailed_health_check(request):
    """
    Detailed health check endpoint with comprehensive system status.
    """
    try:
        health_status = get_health_status()
        
        status_code = 200 if health_status['overall_status'] == 'healthy' else 503
        return JsonResponse(health_status, status=status_code)
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, status=500)


@api_view(['GET'])
def get_metrics(request):
    """
    Get current system and application metrics.
    """
    try:
        metrics = get_current_metrics()
        
        return JsonResponse({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'metrics': metrics
        })
        
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        return JsonResponse({
            'error': 'Failed to retrieve metrics',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, status=500)


@api_view(['GET'])
def get_vehicle_events(request, vehicle_id):
    """
    Get events for a specific vehicle.
    """
    try:
        limit = int(request.GET.get('limit', 100))
        event_type = request.GET.get('event_type')
        
        events = cosmos_service.get_vehicle_events(vehicle_id, limit, event_type)
        
        return JsonResponse({
            'vehicle_id': vehicle_id,
            'events': events,
            'count': len(events)
        })
        
    except Exception as e:
        logger.error(f"Error getting vehicle events: {e}")
        return JsonResponse({
            'error': 'Failed to retrieve vehicle events'
        }, status=500)


@api_view(['GET'])
def get_zone_details(request, zone_id):
    """
    Get details for a specific zone.
    """
    try:
        zone = h3_geofence_service.get_zone_by_id(zone_id)
        if not zone:
            return JsonResponse({
                'error': 'Zone not found'
            }, status=404)
            
        zone_stats = h3_geofence_service.get_zone_statistics(zone_id)
        
        return JsonResponse({
            'zone': {
                'id': zone.id,
                'name': zone.name,
                'description': zone.description,
                'center': [zone.center_lat, zone.center_lng],
                'radius_km': zone.radius_km
            },
            'statistics': zone_stats
        })
        
    except Exception as e:
        logger.error(f"Error getting zone details: {e}")
        return JsonResponse({
            'error': 'Failed to retrieve zone details'
        }, status=500)


@api_view(['GET'])
def get_zone_events(request, zone_id):
    """
    Get events for a specific zone.
    """
    try:
        limit = int(request.GET.get('limit', 100))
        
        events = cosmos_service.get_zone_events(zone_id, limit)
        
        return JsonResponse({
            'zone_id': zone_id,
            'events': events,
            'count': len(events)
        })
        
    except Exception as e:
        logger.error(f"Error getting zone events: {e}")
        return JsonResponse({
            'error': 'Failed to retrieve zone events'
        }, status=500)


@api_view(['GET'])
def get_zones_summary(request):
    """
    Get summary of all zones with current vehicle counts.
    """
    try:
        zones = h3_geofence_service.get_all_zones()
        zones_summary = []
        
        for zone in zones:
            # Get recent events for this zone to count vehicles
            recent_events = cosmos_service.get_zone_events(zone.id, 50)
            
            # Count unique vehicles in the zone
            vehicles_in_zone = set()
            for event in recent_events:
                if event.get('event_type') == 'zone_entry':
                    vehicles_in_zone.add(event.get('vehicle_id'))
                elif event.get('event_type') == 'zone_exit':
                    vehicles_in_zone.discard(event.get('vehicle_id'))
            
            zones_summary.append({
                'id': zone.id,
                'name': zone.name,
                'description': zone.description,
                'center': [zone.center_lat, zone.center_lng],
                'radius_km': zone.radius_km,
                'vehicle_count': len(vehicles_in_zone),
                'h3_indices_count': len(zone.h3_indices)
            })
        
        return JsonResponse({
            'zones': zones_summary,
            'total_zones': len(zones_summary)
        })
        
    except Exception as e:
        logger.error(f"Error getting zones summary: {e}")
        return JsonResponse({
            'error': 'Failed to retrieve zones summary'
        }, status=500)


def taxi_dashboard(request):
    """
    Render the NYC Taxi Simulation Dashboard.
    """
    return render(request, 'taxi_dashboard.html')
