"""
Azure Cosmos DB service for geofence event processing.
Provides high-level interface for storing and retrieving geofence data.
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


class CosmosDBService:
    """Service class for Azure Cosmos DB operations."""
    
    def __init__(self):
        """Initialize Cosmos DB client and containers."""
        self.client = CosmosClient(settings.COSMOS_ENDPOINT, settings.COSMOS_KEY)
        self.database_name = settings.COSMOS_DATABASE_NAME
        self.container_name = settings.COSMOS_CONTAINER_NAME
        
        # Initialize database and container
        self._initialize_database()
        
    def _initialize_database(self):
        """Initialize database and container if they don't exist."""
        try:
            # Create database if it doesn't exist
            self.database = self.client.create_database_if_not_exists(
                id=self.database_name
            )
            
            # Create container if it doesn't exist
            # Note: No offer_throughput for serverless Cosmos DB accounts
            self.container = self.database.create_container_if_not_exists(
                id=self.container_name,
                partition_key=PartitionKey(path="/vehicle_id")
            )
            
            logger.info(f"Initialized Cosmos DB: {self.database_name}/{self.container_name}")
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to initialize Cosmos DB: {e}")
            raise
    
    def get_all_recent_vehicles(self, hours: int = 1) -> List[Dict]:
        """Get all vehicles that have been active in the last N hours."""
        try:
            # Calculate cutoff time
            cutoff_time = datetime.now(timezone.utc).replace(microsecond=0)
            cutoff_time = cutoff_time.replace(hour=cutoff_time.hour - hours)
            cutoff_iso = cutoff_time.isoformat() + 'Z'
            
            # Query for recent vehicle locations
            query = """
                SELECT DISTINCT c.vehicle_id, c.latitude, c.longitude, c.timestamp, c.metadata
                FROM c 
                WHERE c.timestamp >= @cutoff_time 
                AND c.event_type = 'location_update'
                ORDER BY c.timestamp DESC
            """
            
            items = list(self.container.query_items(
                query=query,
                parameters=[{"name": "@cutoff_time", "value": cutoff_iso}],
                enable_cross_partition_query=True
            ))
            
            # Group by vehicle_id and get the most recent location for each
            vehicle_locations = {}
            for item in items:
                vehicle_id = item['vehicle_id']
                if vehicle_id not in vehicle_locations:
                    vehicle_locations[vehicle_id] = item
                else:
                    # Keep the most recent timestamp
                    if item['timestamp'] > vehicle_locations[vehicle_id]['timestamp']:
                        vehicle_locations[vehicle_id] = item
            
            return list(vehicle_locations.values())
            
        except Exception as e:
            logger.error(f"Error getting recent vehicles: {e}")
            return []
    
    def get_vehicle_zone_events(self, vehicle_id: str, limit: int = 10) -> List[Dict]:
        """Get recent zone events for a specific vehicle."""
        try:
            query = """
                SELECT * FROM c 
                WHERE c.vehicle_id = @vehicle_id 
                AND (c.event_type = 'zone_entry' OR c.event_type = 'zone_exit')
                ORDER BY c.timestamp DESC
                OFFSET 0 LIMIT @limit
            """
            
            items = list(self.container.query_items(
                query=query,
                parameters=[
                    {"name": "@vehicle_id", "value": vehicle_id},
                    {"name": "@limit", "value": limit}
                ],
                partition_key=vehicle_id
            ))
            
            return items
            
        except Exception as e:
            logger.error(f"Error getting vehicle zone events: {e}")
            return []
    
    def get_recent_trace_events(self, limit: int = 10, max_retries: int = 2) -> List[Dict]:
        """Get recent zone entry/exit events across all vehicles with retry logic."""
        for attempt in range(max_retries + 1):
            try:
                # Query for trace events (zone_entry/zone_exit) or by ID prefix
                query = """
                    SELECT * FROM c 
                    WHERE c.event_type = 'zone_entry' 
                       OR c.event_type = 'zone_exit'
                       OR STARTSWITH(c.id, 'trace_')
                    ORDER BY c.timestamp DESC
                    OFFSET 0 LIMIT @limit
                """
                
                items = list(self.container.query_items(
                    query=query,
                    parameters=[
                        {"name": "@limit", "value": limit}
                    ],
                    enable_cross_partition_query=True
                ))
                
                return items
                
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Retry {attempt + 1}/{max_retries} for trace events: {e}")
                    import time
                    time.sleep(0.5)  # Brief delay before retry
                else:
                    logger.error(f"Error getting recent trace events after {max_retries + 1} attempts: {e}")
                    return []
        return []
    
    def store_trace_event(self, vehicle_id: str, zone_name: str, event_type: str, 
                         latitude: float, longitude: float, timestamp: str = None) -> str:
        """
        Store a trace event (zone entry/exit) in Cosmos DB.
        
        Args:
            vehicle_id: Unique identifier for the vehicle
            zone_name: Name of the zone (state)
            event_type: 'entry' or 'exit'
            latitude: GPS latitude coordinate
            longitude: GPS longitude coordinate
            timestamp: Event timestamp
            
        Returns:
            Document ID of the stored event
        """
        try:
            if timestamp is None:
                timestamp = datetime.now(timezone.utc).isoformat()
            
            event_id = f"trace_{vehicle_id}_{event_type}_{int(datetime.now().timestamp() * 1000)}"
            
            document = {
                'id': event_id,
                'vehicle_id': vehicle_id,
                'zone_name': zone_name,
                'event_type': f'zone_{event_type}',
                'trace_type': event_type,  # 'entry' or 'exit'
                'latitude': latitude,
                'longitude': longitude,
                'timestamp': timestamp,
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            self.container.create_item(body=document)
            logger.debug(f"Stored trace event: {vehicle_id} {event_type} {zone_name}")
            
            return event_id
            
        except Exception as e:
            logger.error(f"Error storing trace event: {e}")
            return None
    
    def store_location_event(self, vehicle_id: str, latitude: float, longitude: float, 
                           timestamp: Optional[datetime] = None, metadata: Optional[Dict] = None) -> str:
        """
        Store a location event in Cosmos DB.
        
        Args:
            vehicle_id: Unique identifier for the vehicle
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
            'id': f"{vehicle_id}_{int(timestamp.timestamp() * 1000)}",
            'vehicle_id': vehicle_id,
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': timestamp.isoformat(),
            'event_type': 'location_update',
            'metadata': metadata or {},
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            result = self.container.create_item(body=document)
            # logger.info(f"Stored location event for vehicle {vehicle_id}")  # Reduced logging
            
            # Invalidate cache for this vehicle
            cache.delete(f"vehicle_status_{vehicle_id}")
            
            return result['id']
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to store location event: {e}")
            raise
    
    def store_zone_event(self, vehicle_id: str, zone_id: str, event_type: str,
                        latitude: float, longitude: float, h3_index: str,
                        timestamp: Optional[datetime] = None, metadata: Optional[Dict] = None) -> str:
        """
        Store a zone entry/exit event in Cosmos DB.
        
        Args:
            vehicle_id: Unique identifier for the vehicle
            zone_id: Identifier for the geofence zone
            event_type: 'zone_entry' or 'zone_exit'
            latitude: GPS latitude coordinate
            longitude: GPS longitude coordinate
            h3_index: H3 hexagon index
            timestamp: Event timestamp (defaults to current time)
            metadata: Additional metadata for the event
            
        Returns:
            Document ID of the stored event
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
            
        document = {
            'id': f"{vehicle_id}_{zone_id}_{event_type}_{int(timestamp.timestamp() * 1000)}",
            'vehicle_id': vehicle_id,
            'zone_id': zone_id,
            'event_type': event_type,
            'latitude': latitude,
            'longitude': longitude,
            'h3_index': h3_index,
            'timestamp': timestamp.isoformat(),
            'metadata': metadata or {},
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            result = self.container.create_item(body=document)
            # logger.info(f"Stored {event_type} event for vehicle {vehicle_id} in zone {zone_id}")  # Reduced logging
            
            # Invalidate related caches
            cache.delete(f"vehicle_status_{vehicle_id}")
            cache.delete(f"zone_events_{zone_id}")
            
            return result['id']
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to store zone event: {e}")
            raise
    
    def get_vehicle_events(self, vehicle_id: str, limit: int = 100, 
                          event_type: Optional[str] = None) -> List[Dict]:
        """
        Retrieve events for a specific vehicle.
        
        Args:
            vehicle_id: Unique identifier for the vehicle
            limit: Maximum number of events to return
            event_type: Filter by event type (optional)
            
        Returns:
            List of event documents
        """
        cache_key = f"vehicle_events_{vehicle_id}_{event_type}_{limit}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        try:
            query = "SELECT * FROM c WHERE c.vehicle_id = @vehicle_id"
            parameters = [{"name": "@vehicle_id", "value": vehicle_id}]
            
            if event_type:
                query += " AND c.event_type = @event_type"
                parameters.append({"name": "@event_type", "value": event_type})
            
            query += " ORDER BY c.timestamp DESC"
            
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                max_item_count=limit,
                partition_key=vehicle_id
            ))
            
            # Cache for 5 minutes
            cache.set(cache_key, items, 300)
            
            return items
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to retrieve vehicle events: {e}")
            raise
    
    def get_zone_events(self, zone_id: str, limit: int = 100) -> List[Dict]:
        """
        Retrieve events for a specific zone.
        
        Args:
            zone_id: Identifier for the geofence zone
            limit: Maximum number of events to return
            
        Returns:
            List of event documents
        """
        cache_key = f"zone_events_{zone_id}_{limit}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        try:
            query = """
            SELECT * FROM c 
            WHERE c.zone_id = @zone_id 
            AND c.event_type IN ('zone_entry', 'zone_exit')
            ORDER BY c.timestamp DESC
            """
            
            items = list(self.container.query_items(
                query=query,
                parameters=[{"name": "@zone_id", "value": zone_id}],
                max_item_count=limit,
                enable_cross_partition_query=True
            ))
            
            # Cache for 10 minutes
            cache.set(cache_key, items, 600)
            
            return items
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to retrieve zone events: {e}")
            raise
    
    def get_vehicle_current_status(self, vehicle_id: str) -> Optional[Dict]:
        """
        Get the current status of a vehicle including its latest location and zones.
        
        Args:
            vehicle_id: Unique identifier for the vehicle
            
        Returns:
            Dictionary with vehicle status information
        """
        cache_key = f"vehicle_status_{vehicle_id}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        try:
            # Get latest location event
            location_query = """
            SELECT TOP 1 * FROM c 
            WHERE c.vehicle_id = @vehicle_id 
            AND c.event_type = 'location_update'
            ORDER BY c.timestamp DESC
            """
            
            location_events = list(self.container.query_items(
                query=location_query,
                parameters=[{"name": "@vehicle_id", "value": vehicle_id}],
                max_item_count=1,
                partition_key=vehicle_id
            ))
            
            if not location_events:
                return None
            
            latest_location = location_events[0]
            
            # Get current zones (zones entered but not exited)
            zones_query = """
            SELECT c.zone_id, c.event_type, c.timestamp FROM c 
            WHERE c.vehicle_id = @vehicle_id 
            AND c.event_type IN ('zone_entry', 'zone_exit')
            ORDER BY c.zone_id, c.timestamp DESC
            """
            
            zone_events = list(self.container.query_items(
                query=zones_query,
                parameters=[{"name": "@vehicle_id", "value": vehicle_id}],
                partition_key=vehicle_id
            ))
            
            # Determine current zones
            current_zones = []
            zone_status = {}
            
            for event in zone_events:
                zone_id = event['zone_id']
                if zone_id not in zone_status:
                    zone_status[zone_id] = event['event_type']
            
            current_zones = [zone_id for zone_id, status in zone_status.items() 
                           if status == 'zone_entry']
            
            status = {
                'vehicle_id': vehicle_id,
                'latest_location': {
                    'latitude': latest_location['latitude'],
                    'longitude': latest_location['longitude'],
                    'timestamp': latest_location['timestamp']
                },
                'current_zones': current_zones,
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            
            # Cache for 5 minutes
            cache.set(cache_key, status, settings.VEHICLE_STATUS_CACHE_TIMEOUT)
            
            return status
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to get vehicle status: {e}")
            raise
    
    def get_recent_events(self, limit: int = 100, event_type: Optional[str] = None) -> List[Dict]:
        """
        Get recent events from Cosmos DB.
        
        Args:
            limit: Maximum number of events to return
            event_type: Optional filter by event type
            
        Returns:
            List of event documents
        """
        try:
            # Build query
            if event_type:
                query = "SELECT * FROM c WHERE c.event_type = @event_type ORDER BY c._ts DESC"
                parameters = [{"name": "@event_type", "value": event_type}]
            else:
                query = "SELECT * FROM c ORDER BY c._ts DESC"
                parameters = []
            
            # Execute query with caching
            cache_key = f"recent_events_{limit}_{event_type or 'all'}"
            cached_result = cache.get(cache_key)
            
            if cached_result is not None:
                return cached_result
            
            # Query Cosmos DB with cross-partition enabled
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                max_item_count=limit,
                enable_cross_partition_query=True
            ))
            
            # Cache the result for 5 minutes
            cache.set(cache_key, items, 300)
            
            return items
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to retrieve recent events: {e}")
            raise


# Global instance
cosmos_service = CosmosDBService()
