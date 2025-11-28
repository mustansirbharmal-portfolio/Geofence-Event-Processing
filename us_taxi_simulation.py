"""
US Multi-State Taxi Simulation System
Simulates 5 taxis moving through US states using provided pickup/dropoff points
with ArcGIS-based geofencing and real-time tracking.
"""

import json
import time
import random
import threading
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
import math
import requests
import logging
from arcgis_geofence_service import arcgis_geofence_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import cosmos_service for trace event storage
try:
    from geofence_app.cosmos_service import cosmos_service
    COSMOS_AVAILABLE = True
    logger.info("Cosmos DB service available for trace events")
except ImportError:
    COSMOS_AVAILABLE = False
    logger.warning("Cosmos DB service not available for trace events")


@dataclass
class RoutePoint:
    """Represents a pickup or dropoff point."""
    state_name: str
    state_abbr: str
    latitude: float
    longitude: float
    distance_km: float = 0.0


@dataclass
class TaxiRoute:
    """Represents a complete taxi route with pickup and dropoff."""
    pickup: RoutePoint
    dropoff: RoutePoint
    distance_km: float


@dataclass
class TaxiState:
    """Represents the current state of a taxi."""
    taxi_id: str
    current_lat: float
    current_lng: float
    destination_lat: float
    destination_lng: float
    speed_kmh: float
    status: str  # 'idle', 'pickup', 'enroute', 'dropoff'
    current_route: Optional[TaxiRoute]
    route_progress: float  # 0.0 to 1.0
    last_update: datetime
    current_zone: Optional[str] = None
    previous_zone: Optional[str] = None
    route_index: int = 0


class USTaxiSimulation:
    """Simulates 5 taxis moving through US states with provided routes."""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        """Initialize the US taxi simulation."""
        self.api_base_url = api_base_url
        self.taxis: Dict[str, TaxiState] = {}
        self.running = False
        self.simulation_thread = None
        
        # Define the 5 taxi routes as provided
        self.taxi_routes = {
            'taxi_a': [
                TaxiRoute(
                    pickup=RoutePoint("Rhode Island", "RI", 41.580095, -71.477429),
                    dropoff=RoutePoint("Massachusetts", "MA", 42.407211, -71.382437),
                    distance_km=92.31
                ),
                TaxiRoute(
                    pickup=RoutePoint("Alabama", "AL", 32.318231, -86.902298),
                    dropoff=RoutePoint("US Virgin Islands", "VI", 34.297878, -83.824066),
                    distance_km=360.92
                ),
                TaxiRoute(
                    pickup=RoutePoint("Kentucky", "KY", 37.839333, -84.270018),
                    dropoff=RoutePoint("Ohio", "OH", 40.417287, -82.907123),
                    distance_km=309.81
                ),
                TaxiRoute(
                    pickup=RoutePoint("Illinois", "IL", 40.633125, -89.398528),
                    dropoff=RoutePoint("Indiana", "IN", 40.551217, -85.602364),
                    distance_km=320.64
                ),
                TaxiRoute(
                    pickup=RoutePoint("Vermont", "VT", 44.558803, -72.577841),
                    dropoff=RoutePoint("New Hampshire", "NH", 43.193852, -71.572395),
                    distance_km=171.84
                )
            ],
            'taxi_b': [
                TaxiRoute(
                    pickup=RoutePoint("Tennessee", "TN", 35.517491, -86.580447),
                    dropoff=RoutePoint("Alabama", "AL", 32.318231, -86.902298),
                    distance_km=356.98
                ),
                TaxiRoute(
                    pickup=RoutePoint("Palau", "PW", 7.51498, 134.58252),
                    dropoff=RoutePoint("Federated States of Micronesia", "FM", 6.9167, 158.1833),
                    distance_km=2604.04
                ),
                TaxiRoute(
                    pickup=RoutePoint("Colorado", "CO", 39.550051, -105.782067),
                    dropoff=RoutePoint("New Mexico", "NM", 34.97273, -105.032363),
                    distance_km=513.27
                ),
                TaxiRoute(
                    pickup=RoutePoint("North Carolina", "NC", 35.759573, -79.0193),
                    dropoff=RoutePoint("Virginia", "VA", 37.431573, -78.656894),
                    distance_km=188.71
                ),
                TaxiRoute(
                    pickup=RoutePoint("Alabama", "AL", 32.318231, -86.902298),
                    dropoff=RoutePoint("Mississippi", "MS", 32.354668, -89.398528),
                    distance_km=234.55
                )
            ],
            'taxi_c': [
                TaxiRoute(
                    pickup=RoutePoint("Idaho", "ID", 44.068202, -114.742041),
                    dropoff=RoutePoint("Montana", "MT", 46.879682, -110.362566),
                    distance_km=462.84
                ),
                TaxiRoute(
                    pickup=RoutePoint("New Mexico", "NM", 34.97273, -105.032363),
                    dropoff=RoutePoint("Texas", "TX", 31.968599, -99.901813),
                    distance_km=581.28
                ),
                TaxiRoute(
                    pickup=RoutePoint("Alabama", "AL", 32.318231, -86.902298),
                    dropoff=RoutePoint("US Virgin Islands", "VI", 34.297878, -83.824066),
                    distance_km=360.92
                ),
                TaxiRoute(
                    pickup=RoutePoint("Iowa", "IA", 41.878003, -93.097702),
                    dropoff=RoutePoint("Missouri", "MO", 37.964253, -91.831833),
                    distance_km=448.36
                ),
                TaxiRoute(
                    pickup=RoutePoint("South Carolina", "SC", 33.836081, -81.163725),
                    dropoff=RoutePoint("North Carolina", "NC", 35.759573, -79.0193),
                    distance_km=289.96
                )
            ],
            'taxi_d': [
                TaxiRoute(
                    pickup=RoutePoint("New York", "NY", 43.299428, -74.217933),
                    dropoff=RoutePoint("Connecticut", "CT", 41.603221, -73.087749),
                    distance_km=210.17
                ),
                TaxiRoute(
                    pickup=RoutePoint("Illinois", "IL", 40.633125, -89.398528),
                    dropoff=RoutePoint("Iowa", "IA", 41.878003, -93.097702),
                    distance_km=338.76
                ),
                TaxiRoute(
                    pickup=RoutePoint("Oregon", "OR", 43.804133, -120.554201),
                    dropoff=RoutePoint("Idaho", "ID", 44.068202, -114.742041),
                    distance_km=466.22
                ),
                TaxiRoute(
                    pickup=RoutePoint("Wyoming", "WY", 43.075968, -107.290284),
                    dropoff=RoutePoint("Colorado", "CO", 39.550051, -105.782067),
                    distance_km=411.78
                ),
                TaxiRoute(
                    pickup=RoutePoint("Washington", "WA", 47.751074, -120.740139),
                    dropoff=RoutePoint("Oregon", "OR", 43.804133, -120.554201),
                    distance_km=439.12
                )
            ],
            'taxi_e': [
                TaxiRoute(
                    pickup=RoutePoint("Texas", "TX", 31.968599, -99.901813),
                    dropoff=RoutePoint("New Mexico", "NM", 34.97273, -105.032363),
                    distance_km=581.28
                ),
                TaxiRoute(
                    pickup=RoutePoint("Maine", "ME", 45.253783, -69.445469),
                    dropoff=RoutePoint("New Hampshire", "NH", 43.193852, -71.572395),
                    distance_km=284.92
                ),
                TaxiRoute(
                    pickup=RoutePoint("Florida", "FL", 27.664827, -81.515754),
                    dropoff=RoutePoint("Georgia", "GA", 32.157435, -82.907123),
                    distance_km=517.22
                ),
                TaxiRoute(
                    pickup=RoutePoint("Washington", "WA", 47.751074, -120.740139),
                    dropoff=RoutePoint("Idaho", "ID", 44.068202, -114.742041),
                    distance_km=618.58
                ),
                TaxiRoute(
                    pickup=RoutePoint("Connecticut", "CT", 41.603221, -73.087749),
                    dropoff=RoutePoint("Rhode Island", "RI", 41.580095, -71.477429),
                    distance_km=133.94
                )
            ]
        }
        
        # Initialize taxis
        self._initialize_taxis()
    
    def _initialize_taxis(self):
        """Initialize all taxis with their starting positions."""
        for taxi_id, routes in self.taxi_routes.items():
            if routes:
                first_route = routes[0]
                taxi = TaxiState(
                    taxi_id=taxi_id,
                    current_lat=first_route.pickup.latitude,
                    current_lng=first_route.pickup.longitude,
                    destination_lat=first_route.dropoff.latitude,
                    destination_lng=first_route.dropoff.longitude,
                    speed_kmh=random.uniform(600, 1200),  # 10x speed: 600-1200 km/h for faster simulation
                    status='pickup',
                    current_route=first_route,
                    route_progress=0.0,
                    last_update=datetime.now(),
                    route_index=0
                )
                
                # Classify initial zone
                taxi.current_zone = arcgis_geofence_service.classify_point_realtime(
                    taxi.current_lng, taxi.current_lat
                )
                
                self.taxis[taxi_id] = taxi
                logger.info(f"Initialized {taxi_id} at {first_route.pickup.state_name}")
    
    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance between two points using Haversine formula."""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def _interpolate_position(self, start_lat: float, start_lng: float, 
                            end_lat: float, end_lng: float, progress: float) -> Tuple[float, float]:
        """Interpolate position between start and end points based on progress."""
        lat = start_lat + (end_lat - start_lat) * progress
        lng = start_lng + (end_lng - start_lng) * progress
        return lat, lng
    
    def _update_taxi_position(self, taxi: TaxiState, time_delta_seconds: float):
        """Update taxi position based on speed and time."""
        if not taxi.current_route:
            return
        
        # Calculate how far the taxi should move
        distance_per_second = taxi.speed_kmh / 3600  # km/s
        distance_to_move = distance_per_second * time_delta_seconds
        
        # Calculate total route distance
        total_distance = taxi.current_route.distance_km
        
        # Update progress
        progress_increment = distance_to_move / total_distance if total_distance > 0 else 0
        taxi.route_progress = min(1.0, taxi.route_progress + progress_increment)
        
        # Update position based on progress
        if taxi.status == 'pickup':
            # Moving from pickup to dropoff
            start_lat = taxi.current_route.pickup.latitude
            start_lng = taxi.current_route.pickup.longitude
            end_lat = taxi.current_route.dropoff.latitude
            end_lng = taxi.current_route.dropoff.longitude
        else:
            # At pickup or dropoff location
            start_lat = taxi.current_lat
            start_lng = taxi.current_lng
            end_lat = taxi.destination_lat
            end_lng = taxi.destination_lng
        
        taxi.current_lat, taxi.current_lng = self._interpolate_position(
            start_lat, start_lng, end_lat, end_lng, taxi.route_progress
        )
        
        # Check if route is completed
        if taxi.route_progress >= 1.0:
            self._complete_current_route(taxi)
    
    def _complete_current_route(self, taxi: TaxiState):
        """Complete the current route and move to the next one."""
        taxi.route_progress = 0.0
        taxi.route_index += 1
        
        # Get routes for this taxi
        routes = self.taxi_routes.get(taxi.taxi_id, [])
        
        if taxi.route_index < len(routes):
            # Move to next route
            next_route = routes[taxi.route_index]
            taxi.current_route = next_route
            taxi.current_lat = next_route.pickup.latitude
            taxi.current_lng = next_route.pickup.longitude
            taxi.destination_lat = next_route.dropoff.latitude
            taxi.destination_lng = next_route.dropoff.longitude
            taxi.status = 'pickup'
            taxi.speed_kmh = random.uniform(600, 1200)  # 10x speed for faster simulation
            logger.info(f"{taxi.taxi_id} starting route {taxi.route_index + 1}: {next_route.pickup.state_name} -> {next_route.dropoff.state_name}")
        else:
            # All routes completed, restart from beginning
            taxi.route_index = 0
            first_route = routes[0]
            taxi.current_route = first_route
            taxi.current_lat = first_route.pickup.latitude
            taxi.current_lng = first_route.pickup.longitude
            taxi.destination_lat = first_route.dropoff.latitude
            taxi.destination_lng = first_route.dropoff.longitude
            taxi.status = 'pickup'
            taxi.speed_kmh = random.uniform(600, 1200)  # 10x speed
            logger.info(f"{taxi.taxi_id} completed all routes, restarting from {first_route.pickup.state_name}")
    
    def _check_zone_transitions(self, taxi: TaxiState):
        """Check for zone entry/exit events."""
        # Get current zone
        current_zone = arcgis_geofence_service.classify_point_realtime(
            taxi.current_lng, taxi.current_lat
        )
        
        # Check for zone transition
        if current_zone != taxi.current_zone:
            # Zone transition detected
            if taxi.current_zone:
                logger.info(f"🚖 {taxi.taxi_id} EXITED {taxi.current_zone}")
                self._send_zone_event(taxi, 'zone_exit', taxi.current_zone)
                # Store trace event in Cosmos DB
                self._store_trace_event(taxi, 'exit', taxi.current_zone)
            
            if current_zone:
                logger.info(f"🚖 {taxi.taxi_id} ENTERED {current_zone}")
                self._send_zone_event(taxi, 'zone_entry', current_zone)
                # Store trace event in Cosmos DB
                self._store_trace_event(taxi, 'entry', current_zone)
            
            taxi.previous_zone = taxi.current_zone
            taxi.current_zone = current_zone
    
    def _store_trace_event(self, taxi: TaxiState, event_type: str, zone_name: str):
        """Store trace event in Cosmos DB."""
        if not COSMOS_AVAILABLE:
            return
        
        try:
            cosmos_service.store_trace_event(
                vehicle_id=taxi.taxi_id,
                zone_name=zone_name,
                event_type=event_type,
                latitude=taxi.current_lat,
                longitude=taxi.current_lng,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            logger.debug(f"Trace event stored: {taxi.taxi_id} {event_type} {zone_name}")
        except Exception as e:
            logger.error(f"Error storing trace event in Cosmos DB: {e}")
    
    def _send_zone_event(self, taxi: TaxiState, event_type: str, zone_name: str):
        """Zone events are stored via _store_trace_event - this is just for logging."""
        # No HTTP call needed - trace events are stored directly in Cosmos DB
        logger.debug(f"Zone event logged: {taxi.taxi_id} {event_type} {zone_name}")
    
    def _send_location_update(self, taxi: TaxiState):
        """Location updates are tracked in-memory - no HTTP call to avoid deadlock."""
        # The simulation status endpoint returns current taxi positions from memory
        # No need to make HTTP calls to ourselves which causes timeouts
        pass
    
    def _simulation_loop(self):
        """Main simulation loop."""
        logger.info("Starting US taxi simulation loop...")
        
        while self.running:
            try:
                current_time = datetime.now()
                
                for taxi in self.taxis.values():
                    # Calculate time delta
                    time_delta = (current_time - taxi.last_update).total_seconds()
                    
                    # Update taxi position
                    self._update_taxi_position(taxi, time_delta)
                    
                    # Check for zone transitions
                    self._check_zone_transitions(taxi)
                    
                    # Send location update
                    self._send_location_update(taxi)
                    
                    # Update last update time
                    taxi.last_update = current_time
                
                # Sleep for simulation interval (2 seconds)
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                time.sleep(5)  # Wait before retrying
    
    def start_simulation(self):
        """Start the taxi simulation."""
        if self.running:
            logger.warning("Simulation is already running")
            return
        
        self.running = True
        self.simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.simulation_thread.start()
        logger.info("US Taxi simulation started with 5 taxis")
    
    def stop_simulation(self):
        """Stop the taxi simulation."""
        if not self.running:
            logger.warning("Simulation is not running")
            return
        
        self.running = False
        if self.simulation_thread:
            self.simulation_thread.join(timeout=5)
        logger.info("US Taxi simulation stopped")
    
    def get_taxi_status(self, taxi_id: str) -> Optional[Dict]:
        """Get current status of a specific taxi."""
        taxi = self.taxis.get(taxi_id)
        if not taxi:
            return None
        
        return {
            'taxi_id': taxi.taxi_id,
            'current_position': {
                'latitude': taxi.current_lat,
                'longitude': taxi.current_lng
            },
            'destination': {
                'latitude': taxi.destination_lat,
                'longitude': taxi.destination_lng
            },
            'speed_kmh': taxi.speed_kmh,
            'status': taxi.status,
            'current_zone': taxi.current_zone,
            'previous_zone': taxi.previous_zone,
            'route_progress': taxi.route_progress,
            'current_route': {
                'pickup': {
                    'state': taxi.current_route.pickup.state_name,
                    'coordinates': [taxi.current_route.pickup.latitude, taxi.current_route.pickup.longitude]
                },
                'dropoff': {
                    'state': taxi.current_route.dropoff.state_name,
                    'coordinates': [taxi.current_route.dropoff.latitude, taxi.current_route.dropoff.longitude]
                },
                'distance_km': taxi.current_route.distance_km
            } if taxi.current_route else None,
            'route_index': taxi.route_index,
            'last_update': taxi.last_update.isoformat()
        }
    
    def get_all_taxis_status(self) -> Dict[str, Dict]:
        """Get status of all taxis."""
        return {taxi_id: self.get_taxi_status(taxi_id) for taxi_id in self.taxis.keys()}
    
    def search_taxis_by_zone(self, zone_name: str) -> List[Dict]:
        """Search for taxis currently in a specific zone."""
        taxis_in_zone = []
        for taxi in self.taxis.values():
            if taxi.current_zone and zone_name.lower() in taxi.current_zone.lower():
                taxis_in_zone.append(self.get_taxi_status(taxi.taxi_id))
        return taxis_in_zone


# Global simulation instance
us_taxi_simulation = USTaxiSimulation()


if __name__ == "__main__":
    # Test the simulation
    simulation = USTaxiSimulation()
    
    try:
        simulation.start_simulation()
        
        # Run for a while to see the simulation in action
        for i in range(30):  # Run for 1 minute
            time.sleep(2)
            
            # Print status every 10 seconds
            if i % 5 == 0:
                print(f"\n--- Simulation Status (t={i*2}s) ---")
                for taxi_id, status in simulation.get_all_taxis_status().items():
                    print(f"{taxi_id}: {status['current_zone']} -> {status['current_route']['dropoff']['state'] if status['current_route'] else 'N/A'} ({status['route_progress']:.1%})")
    
    except KeyboardInterrupt:
        print("\nStopping simulation...")
    finally:
        simulation.stop_simulation()
