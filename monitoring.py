"""
Monitoring and metrics collection for the Geofence Event Processing System.
Provides performance metrics, health monitoring, and alerting capabilities.
"""

import time
import logging
import psutil
from datetime import datetime, timezone
from typing import Dict, Any, List
from django.core.cache import cache
from django.conf import settings
from dataclasses import dataclass, asdict

from geofence_app.cosmos_service import cosmos_service
from geofence_app.h3_geofence_service import h3_geofence_service

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """System performance metrics."""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_usage_percent: float
    active_connections: int
    cache_hit_ratio: float


@dataclass
class ApplicationMetrics:
    """Application-specific metrics."""
    timestamp: str
    total_vehicles: int
    active_vehicles_1h: int
    total_zones: int
    events_last_hour: int
    events_last_24h: int
    average_response_time_ms: float
    error_rate_percent: float


class MetricsCollector:
    """Collects and stores system and application metrics."""
    
    def __init__(self):
        self.response_times = []
        self.error_count = 0
        self.request_count = 0
        self.start_time = time.time()
    
    def record_request(self, response_time_ms: float, is_error: bool = False):
        """Record a request for metrics calculation."""
        self.response_times.append(response_time_ms)
        self.request_count += 1
        
        if is_error:
            self.error_count += 1
        
        # Keep only last 1000 response times
        if len(self.response_times) > 1000:
            self.response_times = self.response_times[-1000:]
    
    def get_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        try:
            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network connections
            connections = len(psutil.net_connections())
            
            # Cache hit ratio (approximate)
            cache_hit_ratio = self._calculate_cache_hit_ratio()
            
            return SystemMetrics(
                timestamp=datetime.now(timezone.utc).isoformat(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_available_mb=memory.available / (1024 * 1024),
                disk_usage_percent=disk.percent,
                active_connections=connections,
                cache_hit_ratio=cache_hit_ratio
            )
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return SystemMetrics(
                timestamp=datetime.now(timezone.utc).isoformat(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available_mb=0.0,
                disk_usage_percent=0.0,
                active_connections=0,
                cache_hit_ratio=0.0
            )
    
    def get_application_metrics(self) -> ApplicationMetrics:
        """Collect current application metrics."""
        try:
            # Get recent events for analysis
            recent_events_1h = cosmos_service.get_recent_events(limit=10000)
            recent_events_24h = cosmos_service.get_recent_events(limit=50000)
            
            # Count unique vehicles
            vehicles_1h = set()
            vehicles_24h = set()
            events_1h = 0
            events_24h = 0
            
            now = datetime.now(timezone.utc)
            one_hour_ago = now.timestamp() - 3600
            twenty_four_hours_ago = now.timestamp() - 86400
            
            for event in recent_events_24h:
                event_time = datetime.fromisoformat(
                    event['timestamp'].replace('Z', '+00:00')
                ).timestamp()
                
                vehicles_24h.add(event['vehicle_id'])
                events_24h += 1
                
                if event_time >= one_hour_ago:
                    vehicles_1h.add(event['vehicle_id'])
                    events_1h += 1
            
            # Calculate response time and error rate
            avg_response_time = (
                sum(self.response_times) / len(self.response_times)
                if self.response_times else 0.0
            )
            
            error_rate = (
                (self.error_count / self.request_count * 100)
                if self.request_count > 0 else 0.0
            )
            
            # Get total zones
            total_zones = len(h3_geofence_service.get_all_zones())
            
            return ApplicationMetrics(
                timestamp=datetime.now(timezone.utc).isoformat(),
                total_vehicles=len(vehicles_24h),
                active_vehicles_1h=len(vehicles_1h),
                total_zones=total_zones,
                events_last_hour=events_1h,
                events_last_24h=events_24h,
                average_response_time_ms=avg_response_time,
                error_rate_percent=error_rate
            )
            
        except Exception as e:
            logger.error(f"Error collecting application metrics: {e}")
            return ApplicationMetrics(
                timestamp=datetime.now(timezone.utc).isoformat(),
                total_vehicles=0,
                active_vehicles_1h=0,
                total_zones=0,
                events_last_hour=0,
                events_last_24h=0,
                average_response_time_ms=0.0,
                error_rate_percent=0.0
            )
    
    def _calculate_cache_hit_ratio(self) -> float:
        """Calculate approximate cache hit ratio."""
        try:
            # This is a simplified calculation
            # In production, you'd want more sophisticated cache metrics
            cache_stats = cache.get('cache_stats', {'hits': 0, 'misses': 0})
            total = cache_stats['hits'] + cache_stats['misses']
            
            if total == 0:
                return 0.0
            
            return (cache_stats['hits'] / total) * 100
            
        except Exception:
            return 0.0
    
    def store_metrics(self):
        """Store current metrics in cache for monitoring."""
        try:
            system_metrics = self.get_system_metrics()
            app_metrics = self.get_application_metrics()
            
            # Store in cache with 5-minute expiration
            cache.set('system_metrics', asdict(system_metrics), 300)
            cache.set('application_metrics', asdict(app_metrics), 300)
            
            # Store historical data (keep last 24 hours)
            historical_key = f"metrics_history_{int(time.time() // 300)}"  # 5-minute buckets
            historical_data = {
                'system': asdict(system_metrics),
                'application': asdict(app_metrics)
            }
            cache.set(historical_key, historical_data, 86400)  # 24 hours
            
            logger.info("Metrics stored successfully")
            
        except Exception as e:
            logger.error(f"Error storing metrics: {e}")


class HealthChecker:
    """Performs comprehensive health checks."""
    
    def __init__(self):
        self.checks = {
            'database': self._check_database,
            'cache': self._check_cache,
            'h3_service': self._check_h3_service,
            'disk_space': self._check_disk_space,
            'memory': self._check_memory,
        }
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks and return results."""
        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'overall_status': 'healthy',
            'checks': {}
        }
        
        for check_name, check_func in self.checks.items():
            try:
                check_result = check_func()
                results['checks'][check_name] = check_result
                
                if not check_result['healthy']:
                    results['overall_status'] = 'unhealthy'
                    
            except Exception as e:
                results['checks'][check_name] = {
                    'healthy': False,
                    'message': f'Check failed: {str(e)}',
                    'details': {}
                }
                results['overall_status'] = 'unhealthy'
        
        return results
    
    def _check_database(self) -> Dict[str, Any]:
        """Check Cosmos DB connectivity."""
        try:
            # Try to fetch a small amount of data
            cosmos_service.get_recent_events(limit=1)
            
            return {
                'healthy': True,
                'message': 'Cosmos DB is accessible',
                'details': {
                    'endpoint': settings.COSMOS_ENDPOINT,
                    'database': settings.COSMOS_DATABASE_NAME
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Cosmos DB connection failed: {str(e)}',
                'details': {}
            }
    
    def _check_cache(self) -> Dict[str, Any]:
        """Check Redis cache connectivity."""
        try:
            # Test cache operations
            test_key = 'health_check_test'
            test_value = 'test_value'
            
            cache.set(test_key, test_value, 60)
            retrieved_value = cache.get(test_key)
            cache.delete(test_key)
            
            if retrieved_value == test_value:
                return {
                    'healthy': True,
                    'message': 'Cache is working correctly',
                    'details': {}
                }
            else:
                return {
                    'healthy': False,
                    'message': 'Cache test failed',
                    'details': {}
                }
                
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Cache connection failed: {str(e)}',
                'details': {}
            }
    
    def _check_h3_service(self) -> Dict[str, Any]:
        """Check H3 geofence service."""
        try:
            zones = h3_geofence_service.get_all_zones()
            
            if len(zones) > 0:
                # Test zone detection
                test_zone = h3_geofence_service.get_zone_for_location(40.7589, -73.7804)
                
                return {
                    'healthy': True,
                    'message': 'H3 service is working',
                    'details': {
                        'total_zones': len(zones),
                        'test_location_has_zone': test_zone is not None
                    }
                }
            else:
                return {
                    'healthy': False,
                    'message': 'No zones configured',
                    'details': {}
                }
                
        except Exception as e:
            return {
                'healthy': False,
                'message': f'H3 service error: {str(e)}',
                'details': {}
            }
    
    def _check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space."""
        try:
            disk_usage = psutil.disk_usage('/')
            free_percent = (disk_usage.free / disk_usage.total) * 100
            
            if free_percent > 10:  # More than 10% free
                status = 'healthy'
                message = f'Sufficient disk space: {free_percent:.1f}% free'
            elif free_percent > 5:  # More than 5% free
                status = 'warning'
                message = f'Low disk space: {free_percent:.1f}% free'
            else:
                status = 'critical'
                message = f'Critical disk space: {free_percent:.1f}% free'
            
            return {
                'healthy': status == 'healthy',
                'message': message,
                'details': {
                    'free_percent': free_percent,
                    'free_gb': disk_usage.free / (1024**3),
                    'total_gb': disk_usage.total / (1024**3)
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Disk space check failed: {str(e)}',
                'details': {}
            }
    
    def _check_memory(self) -> Dict[str, Any]:
        """Check memory usage."""
        try:
            memory = psutil.virtual_memory()
            
            if memory.percent < 80:
                status = 'healthy'
                message = f'Memory usage normal: {memory.percent:.1f}%'
            elif memory.percent < 90:
                status = 'warning'
                message = f'High memory usage: {memory.percent:.1f}%'
            else:
                status = 'critical'
                message = f'Critical memory usage: {memory.percent:.1f}%'
            
            return {
                'healthy': status == 'healthy',
                'message': message,
                'details': {
                    'used_percent': memory.percent,
                    'available_gb': memory.available / (1024**3),
                    'total_gb': memory.total / (1024**3)
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Memory check failed: {str(e)}',
                'details': {}
            }


# Global instances
metrics_collector = MetricsCollector()
health_checker = HealthChecker()


def collect_and_store_metrics():
    """Collect and store current metrics."""
    metrics_collector.store_metrics()


def get_health_status() -> Dict[str, Any]:
    """Get current health status."""
    return health_checker.run_all_checks()


def get_current_metrics() -> Dict[str, Any]:
    """Get current system and application metrics."""
    return {
        'system': metrics_collector.get_system_metrics(),
        'application': metrics_collector.get_application_metrics()
    }
