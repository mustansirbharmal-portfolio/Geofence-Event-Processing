"""
NYC Taxi Simulation System
Simulates 20 taxis moving through NYC using real taxi trip data
with geofence zone detection and real-time tracking.
"""

import csv
import json
import time
import random
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import math
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TripData:
    """Represents a single taxi trip from the CSV data."""
    vendor_id: int
    pickup_datetime: datetime
    dropoff_datetime: datetime
    passenger_count: int
    trip_distance: float
    pickup_longitude: float
    pickup_latitude: float
    dropoff_longitude: float
    dropoff_latitude: float
    fare_amount: float
    total_amount: float

@dataclass
class TaxiState:
    """Represents the current state of a taxi."""
    taxi_id: str
    current_lat: float
    current_lng: float
    destination_lat: float
    destination_lng: float
    speed_kmh: float
    status: str  # 'idle', 'pickup', 'dropoff', 'moving'
    current_trip: Optional[TripData]
    trip_progress: float  # 0.0 to 1.0
    last_update: datetime
    current_zones: List[str]

class NYCTaxiSimulator:
    """Main taxi simulation class."""
    
    def __init__(self, csv_file_path: str, api_base_url: str = "http://localhost:8000/api/v1"):
        self.csv_file_path = csv_file_path
        self.api_base_url = api_base_url
        self.trip_data: List[TripData] = []
        self.taxis: Dict[str, TaxiState] = {}
        self.simulation_running = False
        self.trip_index = 0
        
        # NYC area bounds for validation
        self.nyc_bounds = {
            'min_lat': 40.4774, 'max_lat': 40.9176,
            'min_lng': -74.2591, 'max_lng': -73.7004
        }
        
        # Simulation parameters
        self.update_interval = 2.0  # seconds between updates
        self.speed_variation = 0.3  # ±30% speed variation
        self.base_speed_kmh = 25.0  # average NYC taxi speed
        
    def load_trip_data(self, max_records: int = 1000) -> None:
        """Load trip data from CSV file."""
        logger.info(f"Loading trip data from {self.csv_file_path}")
        
        try:
            with open(self.csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                count = 0
                
                for row in reader:
                    if count >= max_records:
                        break
                        
                    try:
                        # Parse and validate coordinates
                        pickup_lng = float(row['pickup_longitude'])
                        pickup_lat = float(row['pickup_latitude'])
                        dropoff_lng = float(row['dropoff_longitude'])
                        dropoff_lat = float(row['dropoff_latitude'])
                        
                        # Skip invalid coordinates
                        if not self._is_valid_nyc_coordinate(pickup_lat, pickup_lng):
                            continue
                        if not self._is_valid_nyc_coordinate(dropoff_lat, dropoff_lng):
                            continue
                            
                        trip = TripData(
                            vendor_id=int(row['VendorID']),
                            pickup_datetime=datetime.strptime(row['tpep_pickup_datetime'], '%Y-%m-%d %H:%M:%S'),
                            dropoff_datetime=datetime.strptime(row['tpep_dropoff_datetime'], '%Y-%m-%d %H:%M:%S'),
                            passenger_count=int(row['passenger_count']),
                            trip_distance=float(row['trip_distance']),
                            pickup_longitude=pickup_lng,
                            pickup_latitude=pickup_lat,
                            dropoff_longitude=dropoff_lng,
                            dropoff_latitude=dropoff_lat,
                            fare_amount=float(row['fare_amount']),
                            total_amount=float(row['total_amount'])
                        )
                        
                        self.trip_data.append(trip)
                        count += 1
                        
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Skipping invalid row: {e}")
                        continue
                        
            logger.info(f"Loaded {len(self.trip_data)} valid trips")
            
        except FileNotFoundError:
            logger.error(f"CSV file not found: {self.csv_file_path}")
            raise
        except Exception as e:
            logger.error(f"Error loading trip data: {e}")
            raise
    
    def _is_valid_nyc_coordinate(self, lat: float, lng: float) -> bool:
        """Check if coordinates are within NYC bounds."""
        return (self.nyc_bounds['min_lat'] <= lat <= self.nyc_bounds['max_lat'] and
                self.nyc_bounds['min_lng'] <= lng <= self.nyc_bounds['max_lng'])
    
    def initialize_taxis(self, num_taxis: int = 20) -> None:
        """Initialize taxi fleet with random starting positions."""
        logger.info(f"Initializing {num_taxis} taxis")
        
        for i in range(num_taxis):
            taxi_id = f"taxi_{i+1:03d}"
            
            # Start at a random pickup location from the data
            random_trip = random.choice(self.trip_data)
            
            taxi = TaxiState(
                taxi_id=taxi_id,
                current_lat=random_trip.pickup_latitude,
                current_lng=random_trip.pickup_longitude,
                destination_lat=random_trip.pickup_latitude,
                destination_lng=random_trip.pickup_longitude,
                speed_kmh=self.base_speed_kmh * (1 + random.uniform(-self.speed_variation, self.speed_variation)),
                status='idle',
                current_trip=None,
                trip_progress=0.0,
                last_update=datetime.now(),
                current_zones=[]
            )
            
            self.taxis[taxi_id] = taxi
            
        logger.info(f"Initialized {len(self.taxis)} taxis")
    
    def assign_next_trip(self, taxi: TaxiState) -> None:
        """Assign the next trip to a taxi."""
        if not self.trip_data:
            return
            
        # Get next trip in rotation
        trip = self.trip_data[self.trip_index % len(self.trip_data)]
        self.trip_index += 1
        
        taxi.current_trip = trip
        taxi.destination_lat = trip.pickup_latitude
        taxi.destination_lng = trip.pickup_longitude
        taxi.status = 'pickup'
        taxi.trip_progress = 0.0
        
        logger.info(f"{taxi.taxi_id} assigned trip: pickup at ({trip.pickup_latitude:.4f}, {trip.pickup_longitude:.4f})")
    
    def calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance between two points using Haversine formula (in km)."""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def move_taxi_towards_destination(self, taxi: TaxiState) -> None:
        """Move taxi towards its destination."""
        distance_to_destination = self.calculate_distance(
            taxi.current_lat, taxi.current_lng,
            taxi.destination_lat, taxi.destination_lng
        )
        
        # If very close to destination, snap to it
        if distance_to_destination < 0.05:  # 50 meters
            taxi.current_lat = taxi.destination_lat
            taxi.current_lng = taxi.destination_lng
            self._handle_destination_reached(taxi)
            return
        
        # Calculate movement
        time_delta = (datetime.now() - taxi.last_update).total_seconds()
        distance_to_move = (taxi.speed_kmh / 3600) * time_delta  # km
        
        if distance_to_move >= distance_to_destination:
            # Will reach destination this update
            taxi.current_lat = taxi.destination_lat
            taxi.current_lng = taxi.destination_lng
            self._handle_destination_reached(taxi)
        else:
            # Move towards destination
            progress = distance_to_move / distance_to_destination
            
            lat_diff = taxi.destination_lat - taxi.current_lat
            lng_diff = taxi.destination_lng - taxi.current_lng
            
            taxi.current_lat += lat_diff * progress
            taxi.current_lng += lng_diff * progress
        
        taxi.last_update = datetime.now()
    
    def _handle_destination_reached(self, taxi: TaxiState) -> None:
        """Handle when taxi reaches its destination."""
        if taxi.status == 'pickup':
            # Reached pickup location, now go to dropoff
            taxi.destination_lat = taxi.current_trip.dropoff_latitude
            taxi.destination_lng = taxi.current_trip.dropoff_longitude
            taxi.status = 'dropoff'
            logger.info(f"{taxi.taxi_id} picked up passenger, heading to dropoff")
            
        elif taxi.status == 'dropoff':
            # Completed trip
            logger.info(f"{taxi.taxi_id} completed trip")
            taxi.status = 'idle'
            taxi.current_trip = None
            taxi.trip_progress = 0.0
            
            # Wait a bit before next trip
            threading.Timer(random.uniform(1, 5), lambda: self.assign_next_trip(taxi)).start()
    
    def send_location_update(self, taxi: TaxiState) -> None:
        """Send location update to the geofence API."""
        try:
            payload = {
                "vehicle_id": taxi.taxi_id,
                "latitude": taxi.current_lat,
                "longitude": taxi.current_lng,
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "status": taxi.status,
                    "speed_kmh": taxi.speed_kmh,
                    "trip_progress": taxi.trip_progress
                }
            }
            
            response = requests.post(
                f"{self.api_base_url}/events/location/",
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Update taxi's current zones
                taxi.current_zones = result.get('current_zones', [])
                
                # Log zone changes
                if result.get('zone_events'):
                    for event in result['zone_events']:
                        logger.info(f"{taxi.taxi_id} {event['type']}: {event['zone_name']}")
                        
            else:
                logger.warning(f"API error for {taxi.taxi_id}: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send location for {taxi.taxi_id}: {e}")
    
    def update_simulation(self) -> None:
        """Update all taxis in the simulation."""
        for taxi in self.taxis.values():
            if taxi.status == 'idle':
                # Assign new trip if idle
                self.assign_next_trip(taxi)
            elif taxi.status in ['pickup', 'dropoff']:
                # Move towards destination
                self.move_taxi_towards_destination(taxi)
                
            # Send location update to API
            self.send_location_update(taxi)
    
    def get_simulation_status(self) -> Dict:
        """Get current simulation status."""
        status = {
            'simulation_running': self.simulation_running,
            'total_trips_loaded': len(self.trip_data),
            'current_trip_index': self.trip_index,
            'taxis': {}
        }
        
        for taxi_id, taxi in self.taxis.items():
            status['taxis'][taxi_id] = {
                'status': taxi.status,
                'location': [taxi.current_lat, taxi.current_lng],
                'current_zones': taxi.current_zones,
                'speed_kmh': taxi.speed_kmh
            }
        
        return status
    
    def start_simulation(self) -> None:
        """Start the taxi simulation."""
        if self.simulation_running:
            logger.warning("Simulation is already running")
            return
            
        logger.info("Starting NYC taxi simulation...")
        self.simulation_running = True
        
        def simulation_loop():
            while self.simulation_running:
                try:
                    self.update_simulation()
                    time.sleep(self.update_interval)
                except Exception as e:
                    logger.error(f"Simulation error: {e}")
                    time.sleep(1)
        
        # Start simulation in background thread
        simulation_thread = threading.Thread(target=simulation_loop, daemon=True)
        simulation_thread.start()
        
        logger.info("Simulation started successfully")
    
    def stop_simulation(self) -> None:
        """Stop the taxi simulation."""
        logger.info("Stopping simulation...")
        self.simulation_running = False

# Global simulator instance
taxi_simulator = None

def initialize_simulator(csv_file_path: str) -> NYCTaxiSimulator:
    """Initialize the global taxi simulator."""
    global taxi_simulator
    
    taxi_simulator = NYCTaxiSimulator(csv_file_path)
    taxi_simulator.load_trip_data(max_records=1000)
    taxi_simulator.initialize_taxis(num_taxis=20)
    
    return taxi_simulator

if __name__ == "__main__":
    # Test the simulator
    csv_path = "d:/Geofence Event Processing Project/yellow_tripdata_2015-01.csv"
    simulator = initialize_simulator(csv_path)
    
    print("Starting simulation...")
    simulator.start_simulation()
    
    try:
        # Run for a while
        time.sleep(60)
    except KeyboardInterrupt:
        print("Stopping simulation...")
        simulator.stop_simulation()
