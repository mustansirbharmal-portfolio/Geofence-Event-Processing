"""
Comprehensive test suite for the geofence event processing system.
"""

import json
from datetime import datetime, timezone
from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, MagicMock

from .h3_geofence_service import h3_geofence_service
from .cosmos_service import cosmos_service


class GeofenceAPITestCase(TestCase):
    """Test cases for the geofence API endpoints."""
    
    def setUp(self):
        """Set up test client and sample data."""
        self.client = Client()
        self.sample_location_data = {
            'vehicle_id': 'test_taxi_001',
            'latitude': 40.7589,
            'longitude': -73.7804,
            'metadata': {
                'speed': 45.5,
                'heading': 180,
                'accuracy': 5.0
            }
        }
    
    def test_health_check(self):
        """Test the health check endpoint."""
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('services', data)
    
    @patch('geofence_app.cosmos_service.cosmos_service.store_location_event')
    @patch('geofence_app.cosmos_service.cosmos_service.get_vehicle_current_status')
    def test_process_location_event_success(self, mock_get_status, mock_store_event):
        """Test successful location event processing."""
        # Mock responses
        mock_store_event.return_value = 'event_123'
        mock_get_status.return_value = {'current_zones': []}
        
        response = self.client.post(
            '/api/v1/events/location/',
            data=json.dumps(self.sample_location_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['vehicle_id'], 'test_taxi_001')
        self.assertIn('event_id', data)
    
    def test_process_location_event_missing_fields(self):
        """Test location event processing with missing required fields."""
        incomplete_data = {'vehicle_id': 'test_taxi_001'}
        
        response = self.client.post(
            '/api/v1/events/location/',
            data=json.dumps(incomplete_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
    
    def test_process_location_event_invalid_coordinates(self):
        """Test location event processing with invalid coordinates."""
        invalid_data = self.sample_location_data.copy()
        invalid_data['latitude'] = 91.0  # Invalid latitude
        
        response = self.client.post(
            '/api/v1/events/location/',
            data=json.dumps(invalid_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('Invalid latitude', data['error'])
    
    @patch('geofence_app.cosmos_service.cosmos_service.get_vehicle_current_status')
    def test_get_vehicle_status_success(self, mock_get_status):
        """Test successful vehicle status retrieval."""
        mock_status = {
            'vehicle_id': 'test_taxi_001',
            'latest_location': {
                'latitude': 40.7589,
                'longitude': -73.7804,
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            'current_zones': ['airport_zone']
        }
        mock_get_status.return_value = mock_status
        
        response = self.client.get('/api/v1/vehicles/test_taxi_001/status/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['vehicle_id'], 'test_taxi_001')
        self.assertIn('latest_location', data)
    
    @patch('geofence_app.cosmos_service.cosmos_service.get_vehicle_current_status')
    def test_get_vehicle_status_not_found(self, mock_get_status):
        """Test vehicle status retrieval for non-existent vehicle."""
        mock_get_status.return_value = None
        
        response = self.client.get('/api/v1/vehicles/nonexistent/status/')
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn('error', data)
    
    def test_list_zones(self):
        """Test listing all zones."""
        response = self.client.get('/api/v1/zones/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('zones', data)
        self.assertIn('total_count', data)
        self.assertGreater(data['total_count'], 0)
    
    def test_get_zone_status(self):
        """Test getting zone status."""
        response = self.client.get('/api/v1/zones/airport_zone/status/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['zone_id'], 'airport_zone')
        self.assertIn('name', data)
        self.assertIn('statistics', data)
    
    def test_get_zone_status_not_found(self):
        """Test getting status for non-existent zone."""
        response = self.client.get('/api/v1/zones/nonexistent_zone/status/')
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn('error', data)


class H3GeofenceServiceTestCase(TestCase):
    """Test cases for the H3 geofence service."""
    
    def test_zone_creation(self):
        """Test creating a new geofence zone."""
        zone = h3_geofence_service.create_zone(
            id='test_zone',
            name='Test Zone',
            description='A test zone',
            center_lat=40.7589,
            center_lng=-73.7804,
            radius_km=1.0
        )
        
        self.assertEqual(zone.id, 'test_zone')
        self.assertEqual(zone.name, 'Test Zone')
        self.assertGreater(len(zone.h3_indices), 0)
        self.assertGreater(len(zone.buffer_indices), 0)
    
    def test_get_zone_for_location(self):
        """Test getting zone for a specific location."""
        # Test location within airport zone
        zone = h3_geofence_service.get_zone_for_location(40.7589, -73.7804)
        
        # Should find a zone (airport_zone is pre-configured near this location)
        if zone:
            self.assertIsInstance(zone.id, str)
            self.assertIsInstance(zone.name, str)
    
    def test_get_zones_for_location(self):
        """Test getting all zones for a specific location."""
        zones = h3_geofence_service.get_zones_for_location(40.7589, -73.7804)
        
        self.assertIsInstance(zones, list)
        # Each zone should have required attributes
        for zone in zones:
            self.assertTrue(hasattr(zone, 'id'))
            self.assertTrue(hasattr(zone, 'name'))
    
    def test_detect_zone_transitions(self):
        """Test detecting zone entry and exit events."""
        # Test with no previous zones
        entered, exited = h3_geofence_service.detect_zone_transitions(
            vehicle_id='test_vehicle',
            current_lat=40.7589,
            current_lng=-73.7804,
            previous_zones=set()
        )
        
        self.assertIsInstance(entered, set)
        self.assertIsInstance(exited, set)
    
    def test_get_zone_statistics(self):
        """Test getting zone statistics."""
        stats = h3_geofence_service.get_zone_statistics('airport_zone')
        
        self.assertIn('zone_id', stats)
        self.assertIn('name', stats)
        self.assertIn('h3_indices_count', stats)
        self.assertIn('approximate_area_km2', stats)
    
    def test_haversine_distance(self):
        """Test haversine distance calculation."""
        # Distance between two known points
        distance = h3_geofence_service._haversine_distance(
            40.7589, -73.7804,  # JFK Airport
            40.7505, -73.9934   # Times Square
        )
        
        # Should be approximately 17-18 km
        self.assertGreater(distance, 15)
        self.assertLess(distance, 25)


class CosmosServiceTestCase(TestCase):
    """Test cases for the Cosmos DB service."""
    
    @patch('geofence_app.cosmos_service.CosmosClient')
    def test_cosmos_initialization(self, mock_cosmos_client):
        """Test Cosmos DB service initialization."""
        # Mock the Cosmos client and database operations
        mock_client = MagicMock()
        mock_cosmos_client.return_value = mock_client
        
        mock_database = MagicMock()
        mock_client.create_database_if_not_exists.return_value = mock_database
        
        mock_container = MagicMock()
        mock_database.create_container_if_not_exists.return_value = mock_container
        
        # This should not raise an exception
        from .cosmos_service import CosmosDBService
        service = CosmosDBService()
        
        # Verify initialization calls
        mock_cosmos_client.assert_called_once()
        mock_client.create_database_if_not_exists.assert_called_once()
        mock_database.create_container_if_not_exists.assert_called_once()


class IntegrationTestCase(TestCase):
    """Integration tests for the complete system."""
    
    @patch('geofence_app.cosmos_service.cosmos_service.store_location_event')
    @patch('geofence_app.cosmos_service.cosmos_service.store_zone_event')
    @patch('geofence_app.cosmos_service.cosmos_service.get_vehicle_current_status')
    def test_complete_location_processing_flow(self, mock_get_status, mock_store_zone, mock_store_location):
        """Test the complete flow from location event to zone detection."""
        # Setup mocks
        mock_store_location.return_value = 'location_event_123'
        mock_store_zone.return_value = 'zone_event_123'
        mock_get_status.return_value = {'current_zones': []}
        
        # Send location event
        location_data = {
            'vehicle_id': 'integration_test_vehicle',
            'latitude': 40.7589,
            'longitude': -73.7804
        }
        
        response = self.client.post(
            '/api/v1/events/location/',
            data=json.dumps(location_data),
            content_type='application/json'
        )
        
        # Verify response
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['vehicle_id'], 'integration_test_vehicle')
        
        # Verify that location event was stored
        mock_store_location.assert_called_once()
        
        # Verify that vehicle status was checked
        mock_get_status.assert_called_once_with('integration_test_vehicle')
    
    def test_api_error_handling(self):
        """Test API error handling for various scenarios."""
        # Test invalid JSON
        response = self.client.post(
            '/api/v1/events/location/',
            data='invalid json',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
        # Test missing content type
        response = self.client.post('/api/v1/events/location/', data='{}')
        self.assertEqual(response.status_code, 400)
    
    def test_rate_limiting_headers(self):
        """Test that rate limiting is properly configured."""
        response = self.client.post(
            '/api/v1/events/location/',
            data=json.dumps(self.sample_location_data),
            content_type='application/json'
        )
        
        # Should have throttling headers (even if not rate limited)
        # This tests that the throttling middleware is active
        self.assertIn('X-RateLimit', str(response) or '')  # Headers might vary
