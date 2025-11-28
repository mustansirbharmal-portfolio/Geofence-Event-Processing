"""
ArcGIS-based geofence views for US state-level tracking.
Handles location events with ArcGIS state boundary detection.
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
from arcgis_geofence_service import arcgis_geofence_service
from us_taxi_simulation import us_taxi_simulation

logger = logging.getLogger(__name__)


class ArcGISLocationEventThrottle(AnonRateThrottle):
    """Custom throttle for ArcGIS location events."""
    rate = '200/minute'


@api_view(['POST'])
@throttle_classes([ArcGISLocationEventThrottle])
@csrf_exempt
def process_arcgis_location_event(request):
    """
    Process incoming GPS location events using ArcGIS state detection.
    
    Expected payload:
    {
        "vehicle_id": "taxi_a",
        "latitude": 40.7589,
        "longitude": -73.7804,
        "timestamp": "2024-01-01T12:00:00Z",  // optional
        "metadata": {  // optional
            "speed": 45.5,
            "status": "enroute",
            "route_progress": 0.5
        }
    }
    """
    try:
        data = request.data if hasattr(request, 'data') else json.loads(request.body)
        
        # Validate required fields
        required_fields = ['vehicle_id', 'latitude', 'longitude']
        for field in required_fields:
            if field not in data:
                return Response({
                    'error': f'Missing required field: {field}'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        vehicle_id = data['vehicle_id']
        latitude = float(data['latitude'])
        longitude = float(data['longitude'])
        timestamp = data.get('timestamp', datetime.now(timezone.utc).isoformat())
        metadata = data.get('metadata', {})
        
        # Validate coordinates
        if not (-90 <= latitude <= 90):
            return Response({
                'error': 'Invalid latitude. Must be between -90 and 90'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not (-180 <= longitude <= 180):
            return Response({
                'error': 'Invalid longitude. Must be between -180 and 180'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Use ArcGIS to classify the point
        current_state = arcgis_geofence_service.classify_point_realtime(longitude, latitude)
        
        # Get previous location for zone transition detection
        previous_events = cosmos_service.get_vehicle_events(vehicle_id, limit=1)
        previous_state = None
        
        if previous_events:
            previous_metadata = previous_events[0].get('metadata', {})
            previous_state = previous_metadata.get('current_state')
        
        # Detect zone transitions
        zone_events = []
        transitions = {'entered': [], 'exited': []}
        
        if current_state != previous_state:
            if previous_state:
                # Zone exit event
                exit_event = {
                    'event_id': f"{vehicle_id}_exit_{int(datetime.now().timestamp() * 1000)}",
                    'type': 'zone_exit',
                    'zone_id': previous_state.lower().replace(' ', '_'),
                    'zone_name': previous_state,
                    'timestamp': timestamp
                }
                zone_events.append(exit_event)
                transitions['exited'].append(previous_state.lower().replace(' ', '_'))
                
                # Store exit event in Cosmos DB
                cosmos_service.store_zone_event({
                    'id': exit_event['event_id'],
                    'vehicle_id': vehicle_id,
                    'zone_id': exit_event['zone_id'],
                    'zone_name': previous_state,
                    'event_type': 'zone_exit',
                    'latitude': latitude,
                    'longitude': longitude,
                    'timestamp': timestamp,
                    'metadata': metadata
                })
            
            if current_state:
                # Zone entry event
                entry_event = {
                    'event_id': f"{vehicle_id}_entry_{int(datetime.now().timestamp() * 1000)}",
                    'type': 'zone_entry',
                    'zone_id': current_state.lower().replace(' ', '_'),
                    'zone_name': current_state,
                    'timestamp': timestamp
                }
                zone_events.append(entry_event)
                transitions['entered'].append(current_state.lower().replace(' ', '_'))
                
                # Store entry event in Cosmos DB
                cosmos_service.store_zone_event({
                    'id': entry_event['event_id'],
                    'vehicle_id': vehicle_id,
                    'zone_id': entry_event['zone_id'],
                    'zone_name': current_state,
                    'event_type': 'zone_entry',
                    'latitude': latitude,
                    'longitude': longitude,
                    'timestamp': timestamp,
                    'metadata': metadata
                })
        
        # Update metadata with current state
        metadata['current_state'] = current_state
        metadata['previous_state'] = previous_state
        
        # Store location event in Cosmos DB
        event_id = f"{vehicle_id}_{int(datetime.now().timestamp() * 1000)}"
        location_event = {
            'id': event_id,
            'vehicle_id': vehicle_id,
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': timestamp,
            'metadata': metadata,
            'event_type': 'location_update'
        }
        
        cosmos_service.store_location_event(location_event)
        
        # Prepare current zones response
        current_zones = []
        if current_state:
            current_zones.append({
                'id': current_state.lower().replace(' ', '_'),
                'name': current_state
            })
        
        # Return response
        response_data = {
            'success': True,
            'event_id': event_id,
            'vehicle_id': vehicle_id,
            'processed_at': datetime.now(timezone.utc).isoformat(),
            'current_zones': current_zones,
            'zone_events': zone_events,
            'transitions': transitions,
            'current_state': current_state,
            'coordinates': {
                'latitude': latitude,
                'longitude': longitude
            }
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except json.JSONDecodeError:
        return Response({
            'error': 'Invalid JSON in request body'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except ValueError as e:
        return Response({
            'error': f'Invalid coordinate values: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error processing ArcGIS location event: {e}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_vehicle_status_arcgis(request, vehicle_id):
    """Get current status of a vehicle using ArcGIS state detection."""
    try:
        # Get latest location from Cosmos DB
        recent_events = cosmos_service.get_vehicle_events(vehicle_id, limit=1)
        
        if not recent_events:
            return Response({
                'error': 'Vehicle not found or no location data available'
            }, status=status.HTTP_404_NOT_FOUND)
        
        latest_event = recent_events[0]
        
        # Get current state using ArcGIS
        current_state = arcgis_geofence_service.classify_point_realtime(
            latest_event['longitude'], 
            latest_event['latitude']
        )
        
        # Get recent zone events
        zone_events = cosmos_service.get_vehicle_zone_events(vehicle_id, limit=10)
        
        # Prepare response
        response_data = {
            'vehicle_id': vehicle_id,
            'latest_location': {
                'latitude': latest_event['latitude'],
                'longitude': latest_event['longitude'],
                'timestamp': latest_event['timestamp']
            },
            'current_state': current_state,
            'current_zones': [current_state] if current_state else [],
            'zone_details': [{
                'id': current_state.lower().replace(' ', '_') if current_state else None,
                'name': current_state,
                'description': f"{current_state} state boundary" if current_state else None
            }] if current_state else [],
            'recent_events': zone_events[:5],  # Last 5 zone events
            'metadata': latest_event.get('metadata', {}),
            'last_updated': latest_event['timestamp']
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting vehicle status: {e}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def search_vehicles_by_state(request):
    """Search for vehicles currently in a specific state."""
    try:
        state_name = request.GET.get('state', '').strip()
        
        if not state_name:
            return Response({
                'error': 'State parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get all recent vehicle locations
        all_vehicles = cosmos_service.get_all_recent_vehicles(hours=1)
        
        vehicles_in_state = []
        
        for vehicle_data in all_vehicles:
            # Classify current location
            current_state = arcgis_geofence_service.classify_point_realtime(
                vehicle_data['longitude'], 
                vehicle_data['latitude']
            )
            
            # Check if vehicle is in the requested state
            if current_state and state_name.lower() in current_state.lower():
                vehicles_in_state.append({
                    'vehicle_id': vehicle_data['vehicle_id'],
                    'current_state': current_state,
                    'location': {
                        'latitude': vehicle_data['latitude'],
                        'longitude': vehicle_data['longitude']
                    },
                    'last_update': vehicle_data['timestamp'],
                    'metadata': vehicle_data.get('metadata', {})
                })
        
        return Response({
            'state': state_name,
            'vehicles_found': len(vehicles_in_state),
            'vehicles': vehicles_in_state
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error searching vehicles by state: {e}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_all_states(request):
    """Get all available US states from ArcGIS."""
    try:
        states = arcgis_geofence_service.get_all_zones()
        
        states_data = []
        for state in states:
            states_data.append({
                'id': state.id,
                'name': state.name,
                'state_abbr': state.state_abbr,
                'description': state.description,
                'center': {
                    'latitude': state.center_lat,
                    'longitude': state.center_lng
                }
            })
        
        return Response({
            'states': states_data,
            'total_count': len(states_data)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting all states: {e}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@throttle_classes([])  # No throttling for simulation status polling
def get_simulation_status(request):
    """Get current status of the US taxi simulation."""
    try:
        if not us_taxi_simulation.running:
            return Response({
                'simulation_running': False,
                'message': 'Simulation is not running'
            }, status=status.HTTP_200_OK)
        
        # Get status of all taxis
        taxis_status = us_taxi_simulation.get_all_taxis_status()
        
        return Response({
            'simulation_running': True,
            'total_taxis': len(taxis_status),
            'taxis': taxis_status
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting simulation status: {e}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def start_simulation(request):
    """Start the US taxi simulation."""
    try:
        us_taxi_simulation.start_simulation()
        
        return Response({
            'success': True,
            'message': 'US taxi simulation started',
            'total_taxis': len(us_taxi_simulation.taxis)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error starting simulation: {e}")
        return Response({
            'error': 'Failed to start simulation'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def stop_simulation(request):
    """Stop the US taxi simulation."""
    try:
        us_taxi_simulation.stop_simulation()
        
        return Response({
            'success': True,
            'message': 'US taxi simulation stopped'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error stopping simulation: {e}")
        return Response({
            'error': 'Failed to stop simulation'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def search_taxis_by_zone(request):
    """Search for taxis currently in a specific zone using the simulation."""
    try:
        zone_name = request.GET.get('zone', '').strip()
        
        if not zone_name:
            return Response({
                'error': 'Zone parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Use simulation's search functionality
        taxis_in_zone = us_taxi_simulation.search_taxis_by_zone(zone_name)
        
        return Response({
            'zone': zone_name,
            'taxis_found': len(taxis_in_zone),
            'taxis': taxis_in_zone
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error searching taxis by zone: {e}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@throttle_classes([])  # No throttling for trace events polling
def get_trace_events(request):
    """Get recent trace events (zone entry/exit) from Cosmos DB."""
    try:
        limit = int(request.GET.get('limit', 10))
        limit = min(limit, 50)  # Cap at 50 events
        
        # Get trace events from Cosmos DB
        trace_events = cosmos_service.get_recent_trace_events(limit=limit)
        
        # Format events for frontend
        formatted_events = []
        for event in trace_events:
            formatted_events.append({
                'id': event.get('id'),
                'taxi_id': event.get('vehicle_id', '').upper(),
                'zone': event.get('zone_name'),
                'type': 'entry' if 'entry' in event.get('event_type', '') else 'exit',
                'timestamp': event.get('timestamp'),
                'latitude': event.get('latitude'),
                'longitude': event.get('longitude')
            })
        
        return Response({
            'trace_events': formatted_events,
            'total_count': len(formatted_events)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting trace events: {e}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
