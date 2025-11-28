"""
ArcGIS-based geofence service for US state-level geofencing.
Replaces H3 indexing with ArcGIS API for real-time state boundary detection.
"""

import logging
import sys
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import json

# Try to import ArcGIS API, fallback to lightweight service if not available
try:
    import pandas as pd
    from arcgis.gis import GIS
    from arcgis.features import FeatureLayer
    from arcgis.geometry import Geometry
    from arcgis.geometry.functions import buffer
    ARCGIS_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("ArcGIS API imported successfully")
except ImportError as e:
    ARCGIS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"ArcGIS API not available: {e}")
    logger.info("Will use lightweight geofence service instead")

logger = logging.getLogger(__name__)


@dataclass
class StateZone:
    """Represents a US state geofence zone."""
    id: str
    name: str
    state_abbr: str
    description: str
    center_lat: float
    center_lng: float
    geometry: Optional[Dict] = None


class ArcGISGeofenceService:
    """Service for ArcGIS-based US state geofencing operations."""
    
    def __init__(self):
        """Initialize the ArcGIS geofence service."""
        self.state_zones: Dict[str, StateZone] = {}
        self.states_sdf = None
        self.gis = None
        self.states_layer = None
        
        if ARCGIS_AVAILABLE:
            try:
                # Use the ArcGIS Sample Server which supports spatial queries
                # This is a reliable public layer with US state boundaries
                self.states_layer_url = "https://sampleserver6.arcgisonline.com/arcgis/rest/services/USA/MapServer/2"
                self.states_layer = FeatureLayer(self.states_layer_url)
                
                # Initialize state zones from the layer
                self._initialize_state_zones()
                
                logger.info("ArcGIS Geofence Service initialized successfully")
                return
                
            except Exception as e:
                logger.error(f"Failed to initialize ArcGIS service: {e}")
        
        # Fallback initialization
        logger.info("Using fallback geofence service")
        self._initialize_fallback_zones()
    
    def _initialize_state_zones(self):
        """Initialize US state zones from ArcGIS Sample Server."""
        try:
            # Skip loading from ArcGIS layer - use fallback zones directly
            # This is more reliable and faster for state-level geofencing
            # The real-time spatial queries still use the ArcGIS REST API
            logger.info("Using predefined state zones for initialization")
            self._initialize_fallback_zones()
            
        except Exception as e:
            logger.error(f"Failed to initialize state zones: {e}")
            self._initialize_fallback_zones()
    
    def _initialize_fallback_zones(self):
        """Initialize fallback state zones with all 50 US states coordinates."""
        fallback_states = {
            # All 50 US States with their geographic centers
            'al': {'name': 'Alabama', 'lat': 32.318231, 'lng': -86.902298},
            'ak': {'name': 'Alaska', 'lat': 63.588753, 'lng': -154.493062},
            'az': {'name': 'Arizona', 'lat': 34.048928, 'lng': -111.093731},
            'ar': {'name': 'Arkansas', 'lat': 35.20105, 'lng': -91.831833},
            'ca': {'name': 'California', 'lat': 36.778261, 'lng': -119.417932},
            'co': {'name': 'Colorado', 'lat': 39.550051, 'lng': -105.782067},
            'ct': {'name': 'Connecticut', 'lat': 41.603221, 'lng': -73.087749},
            'de': {'name': 'Delaware', 'lat': 38.910832, 'lng': -75.52767},
            'fl': {'name': 'Florida', 'lat': 27.664827, 'lng': -81.515754},
            'ga': {'name': 'Georgia', 'lat': 32.157435, 'lng': -82.907123},
            'hi': {'name': 'Hawaii', 'lat': 19.898682, 'lng': -155.665857},
            'id': {'name': 'Idaho', 'lat': 44.068202, 'lng': -114.742041},
            'il': {'name': 'Illinois', 'lat': 40.633125, 'lng': -89.398528},
            'in': {'name': 'Indiana', 'lat': 40.551217, 'lng': -85.602364},
            'ia': {'name': 'Iowa', 'lat': 41.878003, 'lng': -93.097702},
            'ks': {'name': 'Kansas', 'lat': 39.011902, 'lng': -98.484246},
            'ky': {'name': 'Kentucky', 'lat': 37.839333, 'lng': -84.270018},
            'la': {'name': 'Louisiana', 'lat': 30.984298, 'lng': -91.962333},
            'me': {'name': 'Maine', 'lat': 45.253783, 'lng': -69.445469},
            'md': {'name': 'Maryland', 'lat': 39.045755, 'lng': -76.641271},
            'ma': {'name': 'Massachusetts', 'lat': 42.407211, 'lng': -71.382437},
            'mi': {'name': 'Michigan', 'lat': 44.314844, 'lng': -85.602364},
            'mn': {'name': 'Minnesota', 'lat': 46.729553, 'lng': -94.6859},
            'ms': {'name': 'Mississippi', 'lat': 32.354668, 'lng': -89.398528},
            'mo': {'name': 'Missouri', 'lat': 37.964253, 'lng': -91.831833},
            'mt': {'name': 'Montana', 'lat': 46.879682, 'lng': -110.362566},
            'ne': {'name': 'Nebraska', 'lat': 41.492537, 'lng': -99.901813},
            'nv': {'name': 'Nevada', 'lat': 38.80261, 'lng': -116.419389},
            'nh': {'name': 'New Hampshire', 'lat': 43.193852, 'lng': -71.572395},
            'nj': {'name': 'New Jersey', 'lat': 40.058324, 'lng': -74.405661},
            'nm': {'name': 'New Mexico', 'lat': 34.97273, 'lng': -105.032363},
            'ny': {'name': 'New York', 'lat': 43.299428, 'lng': -74.217933},
            'nc': {'name': 'North Carolina', 'lat': 35.759573, 'lng': -79.0193},
            'nd': {'name': 'North Dakota', 'lat': 47.551493, 'lng': -101.002012},
            'oh': {'name': 'Ohio', 'lat': 40.417287, 'lng': -82.907123},
            'ok': {'name': 'Oklahoma', 'lat': 35.007752, 'lng': -97.092877},
            'or': {'name': 'Oregon', 'lat': 43.804133, 'lng': -120.554201},
            'pa': {'name': 'Pennsylvania', 'lat': 41.203322, 'lng': -77.194525},
            'ri': {'name': 'Rhode Island', 'lat': 41.580095, 'lng': -71.477429},
            'sc': {'name': 'South Carolina', 'lat': 33.836081, 'lng': -81.163725},
            'sd': {'name': 'South Dakota', 'lat': 43.969515, 'lng': -99.901813},
            'tn': {'name': 'Tennessee', 'lat': 35.517491, 'lng': -86.580447},
            'tx': {'name': 'Texas', 'lat': 31.968599, 'lng': -99.901813},
            'ut': {'name': 'Utah', 'lat': 39.32098, 'lng': -111.093731},
            'vt': {'name': 'Vermont', 'lat': 44.558803, 'lng': -72.577841},
            'va': {'name': 'Virginia', 'lat': 37.431573, 'lng': -78.656894},
            'wa': {'name': 'Washington', 'lat': 47.751074, 'lng': -120.740139},
            'wv': {'name': 'West Virginia', 'lat': 38.597626, 'lng': -80.454903},
            'wi': {'name': 'Wisconsin', 'lat': 43.78444, 'lng': -88.787868},
            'wy': {'name': 'Wyoming', 'lat': 43.075968, 'lng': -107.290284},
            # DC
            'dc': {'name': 'District of Columbia', 'lat': 38.907192, 'lng': -77.036871},
        }
        
        for abbr, data in fallback_states.items():
            zone = StateZone(
                id=abbr,
                name=data['name'],
                state_abbr=abbr.upper(),
                description=f"{data['name']} state boundary",
                center_lat=data['lat'],
                center_lng=data['lng']
            )
            self.state_zones[abbr] = zone
            self.state_zones[data['name'].lower().replace(' ', '_')] = zone
        
        logger.info(f"Initialized {len(fallback_states)} fallback state zones")
    
    def classify_point_realtime(self, longitude: float, latitude: float) -> Optional[str]:
        """
        Classify a point in real-time using ArcGIS REST API spatial query.
        Returns the state name if found, None otherwise.
        """
        # Quick local fallback if ArcGIS layer is not available
        if not self.states_layer:
            return self._classify_point_fallback(longitude, latitude)

        try:
            import requests
            
            # Use direct REST API call for more reliable spatial queries
            url = f"{self.states_layer_url}/query"
            params = {
                'geometry': f'{longitude},{latitude}',
                'geometryType': 'esriGeometryPoint',
                'spatialRel': 'esriSpatialRelIntersects',
                'outFields': 'state_name,state_abbr',
                'f': 'json',
                'inSR': '4326'
            }
            
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if 'features' in data and len(data['features']) > 0:
                attr = data['features'][0].get('attributes', {})
                state_name = attr.get('state_name')
                state_abbr = attr.get('state_abbr')
                # Prefer a readable name when available
                return state_name or state_abbr

            # If server returns nothing, fall back to centroid heuristic
            return self._classify_point_fallback(longitude, latitude)

        except Exception as e:
            # Log at debug level to reduce noise, use fallback silently
            logger.debug(f"ArcGIS query failed, using fallback: {e}")
            # Fallback method (cheap centroid-based)
            return self._classify_point_fallback(longitude, latitude)
    
    def _classify_point_fallback(self, longitude: float, latitude: float) -> Optional[str]:
        """Fallback point classification using distance to state centroids."""
        min_distance = float('inf')
        closest_state = None
        
        for zone in self.state_zones.values():
            if hasattr(zone, 'center_lat') and hasattr(zone, 'center_lng'):
                # Simple distance calculation (not geodesic, but good enough for fallback)
                distance = ((latitude - zone.center_lat) ** 2 + (longitude - zone.center_lng) ** 2) ** 0.5
                if distance < min_distance:
                    min_distance = distance
                    closest_state = zone.name
        
        # Only return if reasonably close (within ~2 degrees)
        return closest_state if min_distance < 2.0 else None
    
    def batch_classify_points(self, points_df: pd.DataFrame) -> pd.DataFrame:
        """
        Batch classify multiple points using spatial join.
        points_df should have 'longitude' and 'latitude' columns.
        """
        try:
            if not self.states_sdf is not None:
                return self._batch_classify_fallback(points_df)
            
            # Convert points DataFrame to Spatially Enabled DataFrame
            points_sdf = pd.DataFrame.spatial.from_xy(
                points_df, 
                x_column="longitude", 
                y_column="latitude", 
                sr=4326
            )
            
            # Spatial join: attach state attributes to each point
            joined = points_sdf.spatial.join(
                self.states_sdf, 
                how="left", 
                op="intersects"
            )
            
            return joined
            
        except Exception as e:
            logger.error(f"Error in batch point classification: {e}")
            return self._batch_classify_fallback(points_df)
    
    def _batch_classify_fallback(self, points_df: pd.DataFrame) -> pd.DataFrame:
        """Fallback batch classification."""
        results = []
        for _, row in points_df.iterrows():
            state = self._classify_point_fallback(row['longitude'], row['latitude'])
            results.append(state)
        
        points_df['state'] = results
        return points_df
    
    def get_zone_by_id(self, zone_id: str) -> Optional[StateZone]:
        """Get a zone by its ID."""
        return self.state_zones.get(zone_id.lower())
    
    def get_all_zones(self) -> List[StateZone]:
        """Get all available zones."""
        # Return unique zones (avoid duplicates from different keys)
        seen_ids = set()
        unique_zones = []
        for zone in self.state_zones.values():
            if zone.id not in seen_ids:
                unique_zones.append(zone)
                seen_ids.add(zone.id)
        return unique_zones
    
    def create_buffer_zone(self, center_lat: float, center_lng: float, radius_km: float) -> Dict:
        """Create a circular buffer zone around a point."""
        try:
            if not self.gis:
                return None
            
            # Create point geometry
            point_geom = {"x": center_lng, "y": center_lat, "spatialReference": {"wkid": 4326}}
            
            # Create buffer (radius in meters)
            buffer_geom = buffer(
                geometries=[point_geom], 
                in_sr=4326, 
                distances=radius_km * 1000, 
                unit="meters", 
                geodesic=True
            )
            
            return buffer_geom[0] if buffer_geom else None
            
        except Exception as e:
            logger.error(f"Error creating buffer zone: {e}")
            return None


# Global service instance - use lightweight service if ArcGIS not available
if ARCGIS_AVAILABLE:
    try:
        arcgis_geofence_service = ArcGISGeofenceService()
    except Exception as e:
        logger.error(f"Failed to initialize ArcGIS service, using lightweight fallback: {e}")
        from lightweight_geofence_service import lightweight_geofence_service
        arcgis_geofence_service = lightweight_geofence_service
else:
    logger.info("ArcGIS not available, using lightweight geofence service")
    from lightweight_geofence_service import lightweight_geofence_service
    arcgis_geofence_service = lightweight_geofence_service
