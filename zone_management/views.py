"""
Zone management specific views.
Handles zone analytics and management operations.
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
def get_zone_analytics(request, zone_id):
    """
    Get detailed analytics for a specific zone.
    """
    try:
        # Check if zone exists
        zone = arcgis_geofence_service.get_zone_by_id(zone_id)
        if not zone:
            return JsonResponse({
                'error': 'Zone not found'
            }, status=404)
        
        # Get query parameters
        hours = int(request.GET.get('hours', 24))
        
        # Get zone events
        zone_events = cosmos_service.get_zone_events(zone_id, limit=1000)
        
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
        
        # Vehicle activity
        unique_vehicles = set()
        vehicle_activity = {}
        
        for event in zone_events:
            vehicle_id = event['vehicle_id']
            unique_vehicles.add(vehicle_id)
            
            if vehicle_id not in vehicle_activity:
                vehicle_activity[vehicle_id] = {'entries': 0, 'exits': 0}
            
            if event['event_type'] == 'zone_entry':
                vehicle_activity[vehicle_id]['entries'] += 1
            elif event['event_type'] == 'zone_exit':
                vehicle_activity[vehicle_id]['exits'] += 1
        
        # Calculate hourly distribution
        hourly_stats = {}
        for event in zone_events:
            timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
            hour = timestamp.hour
            
            if hour not in hourly_stats:
                hourly_stats[hour] = {'entries': 0, 'exits': 0}
            
            if event['event_type'] == 'zone_entry':
                hourly_stats[hour]['entries'] += 1
            elif event['event_type'] == 'zone_exit':
                hourly_stats[hour]['exits'] += 1
        
        # Current occupancy estimate
        current_vehicles = set()
        for event in sorted(zone_events, key=lambda x: x['timestamp']):
            vehicle_id = event['vehicle_id']
            if event['event_type'] == 'zone_entry':
                current_vehicles.add(vehicle_id)
            elif event['event_type'] == 'zone_exit':
                current_vehicles.discard(vehicle_id)
        
        analytics = {
            'zone_id': zone_id,
            'zone_name': zone.name,
            'zone_description': zone.description,
            'time_range_hours': hours,
            'summary': {
                'total_events': len(zone_events),
                'total_entries': len(entries),
                'total_exits': len(exits),
                'unique_vehicles': len(unique_vehicles),
                'estimated_current_occupancy': len(current_vehicles)
            },
            'vehicle_activity': vehicle_activity,
            'hourly_distribution': hourly_stats,
            'current_vehicles': list(current_vehicles),
            'recent_events': zone_events[:20]  # Last 20 events
        }
        
        return JsonResponse(analytics)
        
    except ValueError:
        return JsonResponse({
            'error': 'Invalid query parameters'
        }, status=400)
    except Exception as e:
        logger.error(f"Error getting zone analytics: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)


@api_view(['GET'])
def get_zones_summary(request):
    """
    Get summary statistics for all zones.
    """
    try:
        hours = int(request.GET.get('hours', 24))
        
        zones = arcgis_geofence_service.get_all_zones()
        zones_summary = []
        
        for zone in zones:
            # Get recent events for this zone
            zone_events = cosmos_service.get_zone_events(zone.id, limit=500)
            
            # Filter by time
            if hours > 0:
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
                zone_events = [
                    event for event in zone_events
                    if datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')) >= cutoff_time
                ]
            
            # Calculate basic stats
            entries = len([e for e in zone_events if e['event_type'] == 'zone_entry'])
            exits = len([e for e in zone_events if e['event_type'] == 'zone_exit'])
            unique_vehicles = len(set(e['vehicle_id'] for e in zone_events))
            
            # Estimate current occupancy
            current_vehicles = set()
            for event in sorted(zone_events, key=lambda x: x['timestamp']):
                vehicle_id = event['vehicle_id']
                if event['event_type'] == 'zone_entry':
                    current_vehicles.add(vehicle_id)
                elif event['event_type'] == 'zone_exit':
                    current_vehicles.discard(vehicle_id)
            
            # ArcGIS service doesn't have zone statistics method, so we'll use empty dict
            zone_stats = {}
            
            zones_summary.append({
                'zone_id': zone.id,
                'name': zone.name,
                'description': zone.description,
                'center': {
                    'latitude': zone.center_lat,
                    'longitude': zone.center_lng
                },
                'radius_km': zone.radius_km,
                'arcgis_statistics': zone_stats,
                'activity_summary': {
                    'total_events': len(zone_events),
                    'entries': entries,
                    'exits': exits,
                    'unique_vehicles': unique_vehicles,
                    'estimated_current_occupancy': len(current_vehicles)
                }
            })
        
        # Sort by activity level
        zones_summary.sort(key=lambda x: x['activity_summary']['total_events'], reverse=True)
        
        return JsonResponse({
            'zones_summary': zones_summary,
            'total_zones': len(zones_summary),
            'time_range_hours': hours
        })
        
    except ValueError:
        return JsonResponse({
            'error': 'Invalid query parameters'
        }, status=400)
    except Exception as e:
        logger.error(f"Error getting zones summary: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)


@api_view(['GET'])
def get_zone_heatmap_data(request, zone_id):
    """
    Get heatmap data for a zone showing activity patterns.
    """
    try:
        # Check if zone exists
        zone = arcgis_geofence_service.get_zone_by_id(zone_id)
        if not zone:
            return JsonResponse({
                'error': 'Zone not found'
            }, status=404)
        
        hours = int(request.GET.get('hours', 24))
        
        # Get zone events
        zone_events = cosmos_service.get_zone_events(zone_id, limit=2000)
        
        # Filter by time
        if hours > 0:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            zone_events = [
                event for event in zone_events
                if datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')) >= cutoff_time
            ]
        
        # Create heatmap data points
        heatmap_points = []
        for event in zone_events:
            if 'latitude' in event and 'longitude' in event:
                intensity = 1.0 if event['event_type'] == 'zone_entry' else 0.5
                heatmap_points.append({
                    'lat': event['latitude'],
                    'lng': event['longitude'],
                    'intensity': intensity,
                    'timestamp': event['timestamp'],
                    'event_type': event['event_type'],
                    'vehicle_id': event['vehicle_id']
                })
        
        return JsonResponse({
            'zone_id': zone_id,
            'zone_name': zone.name,
            'heatmap_points': heatmap_points,
            'total_points': len(heatmap_points),
            'time_range_hours': hours,
            'zone_center': {
                'lat': zone.center_lat,
                'lng': zone.center_lng
            },
            'zone_radius_km': zone.radius_km
        })
        
    except ValueError:
        return JsonResponse({
            'error': 'Invalid query parameters'
        }, status=400)
    except Exception as e:
        logger.error(f"Error getting zone heatmap data: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)
