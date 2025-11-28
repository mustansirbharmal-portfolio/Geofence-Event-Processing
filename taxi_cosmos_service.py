"""
Azure Cosmos DB service specifically for taxi data storage.
Provides interface for storing and retrieving taxi simulation data.
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosResourceNotFoundError, CosmosHttpResponseError
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class TaxiCosmosService:
    """Service class for taxi-specific Azure Cosmos DB operations."""
    
    def __init__(self):
        """Initialize Cosmos DB client and taxi container."""
        self.client = CosmosClient(settings.COSMOS_ENDPOINT, settings.COSMOS_KEY)
        self.database_name = settings.COSMOS_DATABASE_NAME
        self.container_name = "taxi"  # Use existing taxi container
        
        # Initialize database and container
        self._initialize_database()
        
    def _initialize_database(self):
        """Initialize database and taxi container if they don't exist."""
        try:
            # Create database if it doesn't exist
            self.database = self.client.create_database_if_not_exists(
                id=self.database_name
            )
            
            # Create taxi container if it doesn't exist
            # Note: No offer_throughput for serverless Cosmos DB accounts
            self.container = self.database.create_container_if_not_exists(
                id=self.container_name,
                partition_key=PartitionKey(path="/taxi_id")
            )
            
            logger.info(f"Initialized Taxi Cosmos DB: {self.database_name}/{self.container_name}")
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to initialize Taxi Cosmos DB: {e}")
            raise
    
    def store_taxi_location(self, taxi_id: str, latitude: float, longitude: float, 
                           timestamp: Optional[datetime] = None, metadata: Optional[Dict] = None) -> str:
        """
        Store a taxi location update in the taxi-data container.
        
        Args:
            taxi_id: Unique identifier for the taxi
            latitude: GPS latitude coordinate
            longitude: GPS longitude coordinate
            timestamp: Event timestamp (defaults to current time)
            metadata: Additional metadata for the location
            
        Returns:
            Document ID of the stored location
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
            
        document = {
            'id': f"{taxi_id}_{int(timestamp.timestamp() * 1000)}",
            'taxi_id': taxi_id,
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': timestamp.isoformat(),
            'event_type': 'taxi_location',
            'metadata': metadata or {},
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            result = self.container.create_item(body=document)
            logger.debug(f"Stored taxi location for {taxi_id}")
            
            # Invalidate cache for this taxi
            cache.delete(f"taxi_status_{taxi_id}")
            
            return result['id']
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to store taxi location: {e}")
            raise
    
    def store_taxi_state_change(self, taxi_id: str, state_name: str, event_type: str,
                               latitude: float, longitude: float, 
                               timestamp: Optional[datetime] = None, metadata: Optional[Dict] = None) -> str:
        """
        Store a taxi state change event (entering/exiting a state).
        
        Args:
            taxi_id: Unique identifier for the taxi
            state_name: Name of the state
            event_type: 'state_entry' or 'state_exit'
            latitude: GPS latitude coordinate
            longitude: GPS longitude coordinate
            timestamp: Event timestamp (defaults to current time)
            metadata: Additional metadata for the event
            
        Returns:
            Document ID of the stored event
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
            
        document = {
            'id': f"{taxi_id}_{state_name}_{event_type}_{int(timestamp.timestamp() * 1000)}",
            'taxi_id': taxi_id,
            'state_name': state_name,
            'event_type': event_type,
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': timestamp.isoformat(),
            'metadata': metadata or {},
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            result = self.container.create_item(body=document)
            logger.debug(f"Stored {event_type} event for taxi {taxi_id} in state {state_name}")
            
            # Invalidate related caches
            cache.delete(f"taxi_status_{taxi_id}")
            cache.delete(f"state_events_{state_name}")
            
            return result['id']
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to store taxi state event: {e}")
            raise
    
    def get_taxi_current_status(self, taxi_id: str) -> Optional[Dict]:
        """
        Get the current status of a taxi including its latest location and state.
        
        Args:
            taxi_id: Unique identifier for the taxi
            
        Returns:
            Dictionary with taxi status information
        """
        cache_key = f"taxi_status_{taxi_id}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        try:
            # Get latest location event
            location_query = """
            SELECT TOP 1 * FROM c 
            WHERE c.taxi_id = @taxi_id 
            AND c.event_type = 'taxi_location'
            ORDER BY c.timestamp DESC
            """
            
            location_events = list(self.container.query_items(
                query=location_query,
                parameters=[{"name": "@taxi_id", "value": taxi_id}],
                max_item_count=1,
                partition_key=taxi_id
            ))
            
            if not location_events:
                return None
            
            latest_location = location_events[0]
            
            # Get current state (states entered but not exited)
            states_query = """
            SELECT c.state_name, c.event_type, c.timestamp FROM c 
            WHERE c.taxi_id = @taxi_id 
            AND c.event_type IN ('state_entry', 'state_exit')
            ORDER BY c.state_name, c.timestamp DESC
            """
            
            state_events = list(self.container.query_items(
                query=states_query,
                parameters=[{"name": "@taxi_id", "value": taxi_id}],
                partition_key=taxi_id
            ))
            
            # Determine current state
            current_states = []
            state_status = {}
            
            for event in state_events:
                state_name = event['state_name']
                if state_name not in state_status:
                    state_status[state_name] = event['event_type']
            
            current_states = [state_name for state_name, status in state_status.items() 
                           if status == 'state_entry']
            
            status = {
                'taxi_id': taxi_id,
                'latest_location': {
                    'latitude': latest_location['latitude'],
                    'longitude': latest_location['longitude'],
                    'timestamp': latest_location['timestamp']
                },
                'current_states': current_states,
                'metadata': latest_location.get('metadata', {}),
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            
            # Cache for 5 minutes
            cache.set(cache_key, status, 300)
            
            return status
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to get taxi status: {e}")
            raise
    
    def get_all_active_taxis(self, hours: int = 1) -> List[Dict]:
        """Get all taxis that have been active in the last N hours."""
        try:
            # Calculate cutoff time
            cutoff_time = datetime.now(timezone.utc).replace(microsecond=0)
            cutoff_time = cutoff_time.replace(hour=cutoff_time.hour - hours)
            cutoff_iso = cutoff_time.isoformat() + 'Z'
            
            # Query for recent taxi locations
            query = """
                SELECT DISTINCT c.taxi_id, c.latitude, c.longitude, c.timestamp, c.metadata
                FROM c 
                WHERE c.timestamp >= @cutoff_time 
                AND c.event_type = 'taxi_location'
                ORDER BY c.timestamp DESC
            """
            
            items = list(self.container.query_items(
                query=query,
                parameters=[{"name": "@cutoff_time", "value": cutoff_iso}],
                enable_cross_partition_query=True
            ))
            
            # Group by taxi_id and get the most recent location for each
            taxi_locations = {}
            for item in items:
                taxi_id = item['taxi_id']
                if taxi_id not in taxi_locations:
                    taxi_locations[taxi_id] = item
                else:
                    # Keep the most recent timestamp
                    if item['timestamp'] > taxi_locations[taxi_id]['timestamp']:
                        taxi_locations[taxi_id] = item
            
            return list(taxi_locations.values())
            
        except Exception as e:
            logger.error(f"Error getting active taxis: {e}")
            return []
    
    def get_taxi_events(self, taxi_id: str, limit: int = 100, 
                       event_type: Optional[str] = None) -> List[Dict]:
        """
        Retrieve events for a specific taxi.
        
        Args:
            taxi_id: Unique identifier for the taxi
            limit: Maximum number of events to return
            event_type: Filter by event type (optional)
            
        Returns:
            List of event documents
        """
        cache_key = f"taxi_events_{taxi_id}_{event_type}_{limit}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        try:
            query = "SELECT * FROM c WHERE c.taxi_id = @taxi_id"
            parameters = [{"name": "@taxi_id", "value": taxi_id}]
            
            if event_type:
                query += " AND c.event_type = @event_type"
                parameters.append({"name": "@event_type", "value": event_type})
            
            query += " ORDER BY c.timestamp DESC"
            
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                max_item_count=limit,
                partition_key=taxi_id
            ))
            
            # Cache for 5 minutes
            cache.set(cache_key, items, 300)
            
            return items
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to retrieve taxi events: {e}")
            raise
    
    def get_state_events(self, state_name: str, limit: int = 100) -> List[Dict]:
        """
        Retrieve events for a specific state.
        
        Args:
            state_name: Name of the state
            limit: Maximum number of events to return
            
        Returns:
            List of event documents
        """
        cache_key = f"state_events_{state_name}_{limit}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        try:
            query = """
            SELECT * FROM c 
            WHERE c.state_name = @state_name 
            AND c.event_type IN ('state_entry', 'state_exit')
            ORDER BY c.timestamp DESC
            """
            
            items = list(self.container.query_items(
                query=query,
                parameters=[{"name": "@state_name", "value": state_name}],
                max_item_count=limit,
                enable_cross_partition_query=True
            ))
            
            # Cache for 10 minutes
            cache.set(cache_key, items, 600)
            
            return items
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to retrieve state events: {e}")
            raise


# Global instance
taxi_cosmos_service = TaxiCosmosService()
