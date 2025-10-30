"""
Device service for interacting with GoogleFindMyTools
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
import sys
import os

# Add GoogleFindMyTools to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'GoogleFindMyTools'))

from app.models import Device, DeviceDetail, Location

logger = logging.getLogger(__name__)


class DeviceService:
    """Service for managing device operations"""
    
    def __init__(self):
        self.initialized = False
        self._devices_cache: Optional[List[Dict[str, Any]]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 60  # Cache TTL in seconds
        self._lock = asyncio.Lock()
        
    async def initialize(self):
        """Initialize the device service"""
        try:
            # Import GoogleFindMyTools modules
            from NovaApi.ListDevices import nbe_list_devices
            from Auth import auth
            
            # Store references to the modules
            self.nbe_list_devices = nbe_list_devices
            self.auth = auth
            
            # Verify authentication
            logger.info("Verifying authentication...")
            # The auth module should have already been set up with secrets.json
            
            self.initialized = True
            logger.info("Device service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize device service: {e}", exc_info=True)
            raise
    
    async def cleanup(self):
        """Cleanup resources"""
        self.initialized = False
        self._devices_cache = None
        logger.info("Device service cleaned up")
    
    async def health_check(self) -> bool:
        """Check if the service is healthy"""
        return self.initialized
    
    async def _fetch_devices_from_api(self) -> List[Dict[str, Any]]:
        """Fetch devices from GoogleFindMyTools API"""
        try:
            # Run the blocking call in a thread pool
            loop = asyncio.get_event_loop()
            
            # Import the necessary functions
            from NovaApi.ListDevices.nbe_list_devices import get_devices_data
            
            # Execute in thread pool to avoid blocking
            devices_data = await loop.run_in_executor(None, get_devices_data)
            
            return devices_data if devices_data else []
            
        except Exception as e:
            logger.error(f"Error fetching devices from API: {e}", exc_info=True)
            raise
    
    async def _get_cached_devices(self) -> List[Dict[str, Any]]:
        """Get devices from cache or fetch if cache is stale"""
        async with self._lock:
            now = datetime.now()
            
            # Check if cache is valid
            if (self._devices_cache is not None and 
                self._cache_timestamp is not None and
                (now - self._cache_timestamp).total_seconds() < self._cache_ttl):
                logger.debug("Returning cached devices")
                return self._devices_cache
            
            # Fetch fresh data
            logger.info("Fetching fresh device data...")
            devices_data = await self._fetch_devices_from_api()
            
            # Update cache
            self._devices_cache = devices_data
            self._cache_timestamp = now
            
            return devices_data
    
    def _parse_device_basic(self, device_data: Dict[str, Any]) -> Device:
        """Parse basic device information"""
        try:
            # Extract basic information from device data
            device_id = device_data.get('id', device_data.get('deviceId', 'unknown'))
            name = device_data.get('name', device_data.get('deviceName', 'Unknown Device'))
            device_type = device_data.get('type', device_data.get('deviceType', 'UNKNOWN'))
            
            # Parse last seen timestamp
            last_seen = None
            last_seen_str = device_data.get('lastSeenTimestamp', device_data.get('lastSeen'))
            if last_seen_str:
                try:
                    if isinstance(last_seen_str, (int, float)):
                        # Unix timestamp in milliseconds
                        last_seen = datetime.fromtimestamp(last_seen_str / 1000)
                    else:
                        last_seen = datetime.fromisoformat(str(last_seen_str).replace('Z', '+00:00'))
                except Exception as e:
                    logger.warning(f"Failed to parse last_seen timestamp: {e}")
            
            status = device_data.get('status', 'UNKNOWN')
            
            return Device(
                device_id=str(device_id),
                name=name,
                device_type=device_type,
                last_seen=last_seen,
                status=status
            )
        except Exception as e:
            logger.error(f"Error parsing device basic info: {e}", exc_info=True)
            raise
    
    def _parse_device_detail(self, device_data: Dict[str, Any]) -> DeviceDetail:
        """Parse detailed device information"""
        try:
            # Extract basic information
            device_id = device_data.get('id', device_data.get('deviceId', 'unknown'))
            name = device_data.get('name', device_data.get('deviceName', 'Unknown Device'))
            device_type = device_data.get('type', device_data.get('deviceType', 'UNKNOWN'))
            model = device_data.get('model', device_data.get('deviceModel'))
            
            # Extract battery level
            battery_level = None
            battery_data = device_data.get('battery', device_data.get('batteryLevel'))
            if battery_data is not None:
                try:
                    battery_level = int(battery_data)
                except (ValueError, TypeError):
                    pass
            
            # Extract location information
            location = None
            location_data = device_data.get('location', device_data.get('lastLocation'))
            if location_data:
                try:
                    lat = location_data.get('latitude', location_data.get('lat'))
                    lon = location_data.get('longitude', location_data.get('lon', location_data.get('lng')))
                    accuracy = location_data.get('accuracy')
                    
                    # Parse location timestamp
                    loc_timestamp = None
                    loc_time_str = location_data.get('timestamp', location_data.get('time'))
                    if loc_time_str:
                        try:
                            if isinstance(loc_time_str, (int, float)):
                                loc_timestamp = datetime.fromtimestamp(loc_time_str / 1000)
                            else:
                                loc_timestamp = datetime.fromisoformat(str(loc_time_str).replace('Z', '+00:00'))
                        except Exception:
                            pass
                    
                    if lat is not None and lon is not None:
                        location = Location(
                            latitude=float(lat),
                            longitude=float(lon),
                            accuracy=float(accuracy) if accuracy is not None else None,
                            timestamp=loc_timestamp
                        )
                except Exception as e:
                    logger.warning(f"Failed to parse location data: {e}")
            
            # Parse last seen timestamp
            last_seen = None
            last_seen_str = device_data.get('lastSeenTimestamp', device_data.get('lastSeen'))
            if last_seen_str:
                try:
                    if isinstance(last_seen_str, (int, float)):
                        last_seen = datetime.fromtimestamp(last_seen_str / 1000)
                    else:
                        last_seen = datetime.fromisoformat(str(last_seen_str).replace('Z', '+00:00'))
                except Exception as e:
                    logger.warning(f"Failed to parse last_seen timestamp: {e}")
            
            status = device_data.get('status', 'UNKNOWN')
            
            # Store additional info
            additional_info = {
                k: v for k, v in device_data.items()
                if k not in ['id', 'deviceId', 'name', 'deviceName', 'type', 'deviceType',
                           'model', 'deviceModel', 'battery', 'batteryLevel', 'location',
                           'lastLocation', 'lastSeenTimestamp', 'lastSeen', 'status']
            }
            
            return DeviceDetail(
                device_id=str(device_id),
                name=name,
                device_type=device_type,
                model=model,
                battery_level=battery_level,
                location=location,
                last_seen=last_seen,
                status=status,
                additional_info=additional_info if additional_info else None
            )
        except Exception as e:
            logger.error(f"Error parsing device detail: {e}", exc_info=True)
            raise
    
    async def get_all_devices(self) -> List[Device]:
        """Get all devices"""
        if not self.initialized:
            raise RuntimeError("Device service not initialized")
        
        try:
            devices_data = await self._get_cached_devices()
            devices = [self._parse_device_basic(device_data) for device_data in devices_data]
            logger.info(f"Retrieved {len(devices)} devices")
            return devices
        except Exception as e:
            logger.error(f"Error getting all devices: {e}", exc_info=True)
            raise
    
    async def get_device_detail(self, device_id: str) -> Optional[DeviceDetail]:
        """Get detailed information for a specific device"""
        if not self.initialized:
            raise RuntimeError("Device service not initialized")
        
        try:
            devices_data = await self._get_cached_devices()
            
            # Find the device by ID
            device_data = None
            for data in devices_data:
                data_id = str(data.get('id', data.get('deviceId', '')))
                if data_id == device_id:
                    device_data = data
                    break
            
            if device_data is None:
                logger.warning(f"Device with ID {device_id} not found")
                return None
            
            device_detail = self._parse_device_detail(device_data)
            logger.info(f"Retrieved detail for device {device_id}")
            return device_detail
            
        except Exception as e:
            logger.error(f"Error getting device detail: {e}", exc_info=True)
            raise

