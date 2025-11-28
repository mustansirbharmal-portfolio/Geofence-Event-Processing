"""
API views for NYC Taxi Simulation
Provides endpoints to control and monitor the taxi simulation system.
"""

import os
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from django.conf import settings
import logging

# Import the taxi simulator
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from taxi_simulation import initialize_simulator, taxi_simulator

logger = logging.getLogger(__name__)

@api_view(['POST'])
def start_simulation(request):
    """
    Start the NYC taxi simulation.
    
    POST /api/v1/simulation/start/
    """
    try:
        global taxi_simulator
        
        if taxi_simulator and taxi_simulator.simulation_running:
            return Response({
                'status': 'already_running',
                'message': 'Simulation is already running'
            }, status=status.HTTP_200_OK)
        
        # Initialize simulator if not already done
        if not taxi_simulator:
            csv_path = os.path.join(
                os.path.dirname(settings.BASE_DIR), 
                'yellow_tripdata_2015-01.csv'
            )
            
            if not os.path.exists(csv_path):
                return Response({
                    'status': 'error',
                    'message': f'CSV file not found: {csv_path}'
                }, status=status.HTTP_404_NOT_FOUND)
            
            logger.info(f"Initializing simulator with CSV: {csv_path}")
            taxi_simulator = initialize_simulator(csv_path)
        
        # Start the simulation
        taxi_simulator.start_simulation()
        
        return Response({
            'status': 'started',
            'message': 'NYC taxi simulation started successfully',
            'details': {
                'num_taxis': len(taxi_simulator.taxis),
                'num_trips': len(taxi_simulator.trip_data),
                'update_interval': taxi_simulator.update_interval
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to start simulation: {e}")
        return Response({
            'status': 'error',
            'message': f'Failed to start simulation: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def stop_simulation(request):
    """
    Stop the NYC taxi simulation.
    
    POST /api/v1/simulation/stop/
    """
    try:
        global taxi_simulator
        
        if not taxi_simulator or not taxi_simulator.simulation_running:
            return Response({
                'status': 'not_running',
                'message': 'Simulation is not currently running'
            }, status=status.HTTP_200_OK)
        
        taxi_simulator.stop_simulation()
        
        return Response({
            'status': 'stopped',
            'message': 'NYC taxi simulation stopped successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to stop simulation: {e}")
        return Response({
            'status': 'error',
            'message': f'Failed to stop simulation: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def simulation_status(request):
    """
    Get current simulation status and taxi positions.
    
    GET /api/v1/simulation/status/
    """
    try:
        global taxi_simulator
        
        if not taxi_simulator:
            return Response({
                'status': 'not_initialized',
                'message': 'Simulation not initialized',
                'simulation_running': False,
                'taxis': {}
            }, status=status.HTTP_200_OK)
        
        simulation_status = taxi_simulator.get_simulation_status()
        
        return Response({
            'status': 'success',
            'message': 'Simulation status retrieved',
            **simulation_status
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to get simulation status: {e}")
        return Response({
            'status': 'error',
            'message': f'Failed to get simulation status: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def taxi_details(request, taxi_id):
    """
    Get detailed information about a specific taxi.
    
    GET /api/v1/simulation/taxi/<taxi_id>/
    """
    try:
        global taxi_simulator
        
        if not taxi_simulator:
            return Response({
                'status': 'error',
                'message': 'Simulation not initialized'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if taxi_id not in taxi_simulator.taxis:
            return Response({
                'status': 'error',
                'message': f'Taxi {taxi_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        taxi = taxi_simulator.taxis[taxi_id]
        
        taxi_info = {
            'taxi_id': taxi.taxi_id,
            'status': taxi.status,
            'current_location': {
                'latitude': taxi.current_lat,
                'longitude': taxi.current_lng
            },
            'destination': {
                'latitude': taxi.destination_lat,
                'longitude': taxi.destination_lng
            },
            'speed_kmh': taxi.speed_kmh,
            'current_zones': taxi.current_zones,
            'trip_progress': taxi.trip_progress,
            'last_update': taxi.last_update.isoformat() if taxi.last_update else None
        }
        
        if taxi.current_trip:
            taxi_info['current_trip'] = {
                'pickup_location': {
                    'latitude': taxi.current_trip.pickup_latitude,
                    'longitude': taxi.current_trip.pickup_longitude
                },
                'dropoff_location': {
                    'latitude': taxi.current_trip.dropoff_latitude,
                    'longitude': taxi.current_trip.dropoff_longitude
                },
                'trip_distance': taxi.current_trip.trip_distance,
                'fare_amount': taxi.current_trip.fare_amount,
                'passenger_count': taxi.current_trip.passenger_count
            }
        
        return Response({
            'status': 'success',
            'taxi': taxi_info
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to get taxi details: {e}")
        return Response({
            'status': 'error',
            'message': f'Failed to get taxi details: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def simulation_metrics(request):
    """
    Get simulation performance metrics.
    
    GET /api/v1/simulation/metrics/
    """
    try:
        global taxi_simulator
        
        if not taxi_simulator:
            return Response({
                'status': 'error',
                'message': 'Simulation not initialized'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Calculate metrics
        total_taxis = len(taxi_simulator.taxis)
        active_taxis = sum(1 for taxi in taxi_simulator.taxis.values() 
                          if taxi.status in ['pickup', 'dropoff'])
        idle_taxis = sum(1 for taxi in taxi_simulator.taxis.values() 
                        if taxi.status == 'idle')
        
        # Zone distribution
        zone_counts = {}
        for taxi in taxi_simulator.taxis.values():
            for zone in taxi.current_zones:
                zone_counts[zone] = zone_counts.get(zone, 0) + 1
        
        metrics = {
            'simulation_running': taxi_simulator.simulation_running,
            'total_taxis': total_taxis,
            'active_taxis': active_taxis,
            'idle_taxis': idle_taxis,
            'trips_completed': taxi_simulator.trip_index,
            'total_trips_available': len(taxi_simulator.trip_data),
            'zone_distribution': zone_counts,
            'update_interval_seconds': taxi_simulator.update_interval
        }
        
        return Response({
            'status': 'success',
            'metrics': metrics
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to get simulation metrics: {e}")
        return Response({
            'status': 'error',
            'message': f'Failed to get simulation metrics: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def reset_simulation(request):
    """
    Reset the simulation to initial state.
    
    POST /api/v1/simulation/reset/
    """
    try:
        global taxi_simulator
        
        if taxi_simulator and taxi_simulator.simulation_running:
            taxi_simulator.stop_simulation()
        
        # Reinitialize
        csv_path = os.path.join(
            os.path.dirname(settings.BASE_DIR), 
            'yellow_tripdata_2015-01.csv'
        )
        
        if not os.path.exists(csv_path):
            return Response({
                'status': 'error',
                'message': f'CSV file not found: {csv_path}'
            }, status=status.HTTP_404_NOT_FOUND)
        
        taxi_simulator = initialize_simulator(csv_path)
        
        return Response({
            'status': 'reset',
            'message': 'Simulation reset successfully',
            'details': {
                'num_taxis': len(taxi_simulator.taxis),
                'num_trips': len(taxi_simulator.trip_data)
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to reset simulation: {e}")
        return Response({
            'status': 'error',
            'message': f'Failed to reset simulation: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
