"""
Device service for interacting with GoogleFindMyTools
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import sys
import os

# Add GoogleFindMyTools to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'GoogleFindMyTools'))

from app.models import Device, DeviceDetail, Location

logger = logging.getLogger(__name__)


class DeviceService:
    """Service for managing device operations"""
    
    def __init__(self, vnc_auth_service=None):
        self.initialized = False
        self.init_error: Optional[str] = None
        # Optional reference to the VncAuthService instance, used to avoid
        # racing with it: an in-progress VNC session clears the cached
        # aas_token (see vnc_auth_entrypoint.py) so it can force a real login,
        # but any *other* concurrent auth attempt would see that same cleared
        # token and try to open its own (headless, unattended, un-completable)
        # OAuth flow - hanging for 5 minutes for nothing. Checking this first
        # turns that into an immediate, clear error instead.
        self._vnc_auth_service = vnc_auth_service
        self._devices_cache: Optional[List[Dict[str, Any]]] = None
        self._cache_timestamp: Optional[datetime] = None

        # Configurable cache TTL (default: 60 seconds)
        self._cache_ttl = int(os.getenv('DEVICE_CACHE_TTL', '60'))

        self._lock = asyncio.Lock()
        self._device_list_protobuf = None  # Store full protobuf for location fetching
        self._location_cache: Dict[str, Dict[str, Any]] = {}  # Cache locations by device_id
        self._location_cache_timestamp: Dict[str, datetime] = {}  # Track cache time per device
        self._background_task: Optional[asyncio.Task] = None  # Background location update task

        # Configurable location update interval (default: 300 seconds = 5 minutes)
        self._location_update_interval = int(os.getenv('LOCATION_UPDATE_INTERVAL', '300'))

        self._fcm_receiver = None  # Shared FCM receiver instance
        # Guards FcmReceiver creation + register_for_location_updates() only -
        # concurrent location fetches (see _background_location_updater) would
        # otherwise all see _listening=False and race to open their own MCS
        # connection (the exact bug fixed in TECHNICAL_FIX.md's follow-up
        # section). Registration itself is fast; the actual per-device wait
        # for a location response happens after releasing this lock, so this
        # doesn't serialize the slow part.
        self._fcm_registration_lock = asyncio.Lock()

        # Enable/disable background location updates (default: true)
        self._enable_location_updates = os.getenv('ENABLE_LOCATION_UPDATES', 'true').lower() == 'true'

        logger.info(f"DeviceService configuration:")
        logger.info(f"  - Device cache TTL: {self._cache_ttl} seconds")
        logger.info(f"  - Location update interval: {self._location_update_interval} seconds")
        logger.info(f"  - Background location updates: {'enabled' if self._enable_location_updates else 'disabled'}")
        
    async def initialize(self):
        """Initialize the device service"""
        try:
            # Import GoogleFindMyTools modules
            from NovaApi.ListDevices import nbe_list_devices
            from Auth.username_provider import get_username

            # Store references to the modules
            self.nbe_list_devices = nbe_list_devices
            self.get_username = get_username

            # Verify authentication by checking if secrets.json exists
            logger.info("Verifying authentication...")
            try:
                username = get_username()
                if not username:
                    # get_username() returns "" (does not raise) when secrets.json is
                    # missing, empty, or has no cached username - treat that as a failure.
                    raise RuntimeError(
                        "secrets.json is missing, empty, or invalid (no authenticated "
                        "username found). Start an in-browser login at POST /auth/vnc/start "
                        "(see AUTHENTICATION.md), or check the volume/file mount for secrets.json."
                    )
                logger.info(f"Authentication verified for user: {username}")
            except Exception as auth_error:
                logger.error(f"Authentication failed: {auth_error}")
                raise Exception(f"Authentication not configured: {auth_error}")

            self.initialized = True
            logger.info("Device service initialized successfully")

            # Start background location update task if enabled
            if self._enable_location_updates:
                self._background_task = asyncio.create_task(self._background_location_updater())
                logger.info("Background location updater started")
            else:
                logger.info("Background location updates disabled (ENABLE_LOCATION_UPDATES=false)")

        except Exception as e:
            logger.error(f"Failed to initialize device service: {e}", exc_info=True)
            self.init_error = str(e)
            raise

    async def cleanup(self):
        """Cleanup resources"""
        # Stop background task
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            logger.info("Background location updater stopped")

        # Stop FCM receiver if running
        if self._fcm_receiver:
            try:
                await self._fcm_receiver.stop_listening()
            except Exception as e:
                logger.warning(f"Error stopping FCM receiver: {e}")

        self.initialized = False
        self._devices_cache = None
        logger.info("Device service cleaned up")
    
    async def health_check(self) -> bool:
        """Check if the service is healthy"""
        return self.initialized
    
    async def _fetch_devices_from_api(self) -> List[Dict[str, Any]]:
        """Fetch devices from GoogleFindMyTools API"""
        if self._vnc_auth_service and self._vnc_auth_service.state == "running":
            raise RuntimeError(
                "A VNC authentication session is currently in progress (see GET "
                "/auth/vnc/status) - not fetching devices until it finishes, to avoid "
                "triggering a second, unattended login attempt that would just hang."
            )

        try:
            # Run the blocking call in a thread pool
            loop = asyncio.get_event_loop()

            # Import the necessary functions
            from NovaApi.ListDevices.nbe_list_devices import request_device_list
            from ProtoDecoders.decoder import parse_device_list_protobuf, get_canonic_ids

            # Execute in thread pool to avoid blocking
            try:
                result_hex = await loop.run_in_executor(None, request_device_list)
            except KeyError as e:
                # token_retrieval.py does auth_response['Auth'] (or similar) without
                # checking it's present. Google returns a response with no 'Auth' key
                # when it rejects the request outright (e.g. HTTP 403), which happens
                # right after a token gets revoked/expires - so this surfaces as a
                # bare "KeyError: 'Auth'" instead of a message pointing at the cause.
                raise RuntimeError(
                    f"Google rejected the authentication token (missing {e} key in its "
                    "response - usually means the token was revoked or expired). "
                    "Try re-authenticating (see AUTHENTICATION.md)."
                ) from e

            if not result_hex:
                # nova_request() returns None (instead of raising) when Google's Nova API
                # responds with a non-200 status, e.g. an expired/revoked auth token.
                raise RuntimeError(
                    "Nova API device list request failed (no response from Google). "
                    "This usually means the authentication token expired or was revoked - "
                    "try re-authenticating (see AUTHENTICATION.md)."
                )

            # Parse the protobuf response
            device_list = parse_device_list_protobuf(result_hex)

            # Get canonical IDs (device name and ID pairs)
            canonic_ids = get_canonic_ids(device_list)

            # Store the full device_list for location fetching
            self._device_list_protobuf = device_list

            # Create a mapping of canonic_id to device metadata
            device_metadata_map = {}
            for device in device_list.deviceMetadata:
                device_name = device.userDefinedDeviceName
                # Get canonic IDs for this device
                if device.identifierInformation.type == 1:  # IDENTIFIER_ANDROID
                    canonic_ids_list = device.identifierInformation.phoneInformation.canonicIds.canonicId
                else:
                    canonic_ids_list = device.identifierInformation.canonicIds.canonicId

                for canonic_id_obj in canonic_ids_list:
                    canonic_id = canonic_id_obj.id
                    device_metadata_map[canonic_id] = device

            # Convert to our format with additional metadata
            devices_data = []
            for device_name, canonic_id in canonic_ids:
                device_dict = {
                    'id': canonic_id,
                    'deviceId': canonic_id,
                    'name': device_name,
                    'deviceName': device_name,
                    'type': 'SPOT_DEVICE',
                    'deviceType': 'SPOT_DEVICE',
                    'status': 'ACTIVE'
                }

                # Add metadata if available
                if canonic_id in device_metadata_map:
                    device_meta = device_metadata_map[canonic_id]

                    # Add image URL if available
                    if device_meta.HasField('imageInformation') and device_meta.imageInformation.imageUrl:
                        device_dict['imageUrl'] = device_meta.imageInformation.imageUrl

                    # Add identifier type
                    if device_meta.HasField('identifierInformation'):
                        id_info = device_meta.identifierInformation
                        device_dict['identifierType'] = str(id_info.type)

                    # Add device information if available
                    if device_meta.HasField('information'):
                        info = device_meta.information

                        # Add device registration info
                        if info.HasField('deviceRegistration'):
                            reg = info.deviceRegistration
                            if reg.fastPairModelId:
                                device_dict['modelId'] = reg.fastPairModelId
                                device_dict['model'] = f"Fast Pair Model {reg.fastPairModelId}"

                            # Add owner key version
                            if reg.HasField('encryptedUserSecrets'):
                                device_dict['ownerKeyVersion'] = reg.encryptedUserSecrets.ownerKeyVersion

                        # Add location information if available (for additional_info)
                        if info.HasField('locationInformation'):
                            loc_info = info.locationInformation
                            if loc_info.HasField('reports'):
                                reports = loc_info.reports
                                if reports.HasField('recentLocationAndNetworkLocations'):
                                    device_dict['hasLocationReports'] = True

                devices_data.append(device_dict)

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

    async def _background_location_updater(self):
        """Background task that periodically updates location data for all devices"""
        logger.info("Background location updater task started")

        # Wait a bit before first update to let the service fully initialize
        await asyncio.sleep(30)

        while True:
            try:
                logger.info("Starting background location update cycle...")

                # Get all devices
                devices_data = await self._get_cached_devices()

                if not devices_data:
                    logger.warning("No devices found for location update")
                    await asyncio.sleep(self._location_update_interval)
                    continue

                # Update locations for all devices concurrently - these are
                # independent FCM round-trips (each with its own request_uuid),
                # so there's no need to wait for one device's up-to-30s timeout
                # before even starting the next. Sequentially, N devices could
                # take N * ~32s; concurrently, the whole cycle takes as long as
                # the single slowest device.
                async def _update_one(device_data: Dict[str, Any]) -> None:
                    device_id = device_data.get('id', device_data.get('deviceId'))
                    device_name = device_data.get('name', device_data.get('deviceName', 'Unknown'))
                    if not device_id:
                        return
                    try:
                        location_data = await self._fetch_location_for_device_internal(device_id, device_name)
                        if location_data:
                            logger.info(f"Updated location for device {device_name} ({device_id})")
                        else:
                            logger.debug(f"No location data available for device {device_name} ({device_id})")
                    except Exception as e:
                        logger.error(f"Error updating location for device {device_id}: {e}")

                await asyncio.gather(*(_update_one(d) for d in devices_data))

                logger.info(f"Background location update cycle complete. Next update in {self._location_update_interval} seconds")

            except asyncio.CancelledError:
                logger.info("Background location updater cancelled")
                break
            except Exception as e:
                logger.error(f"Error in background location updater: {e}", exc_info=True)

            # Wait before next update cycle
            await asyncio.sleep(self._location_update_interval)

    async def _fetch_location_for_device_internal(self, device_id: str, device_name: str, force: bool = False) -> Optional[Dict[str, Any]]:
        """Internal method to fetch location data for a specific device

        This runs in the background task and has access to the main event loop.

        Args:
            force: Skip the cache-freshness check below and always hit Google
                for a new location, even if a recent one is already cached.
        """
        if self._vnc_auth_service and self._vnc_auth_service.state == "running":
            logger.debug(f"Skipping location fetch for {device_id}: VNC auth session in progress")
            return None

        try:
            # Check location cache first (same TTL as the background update
            # interval - no point re-requesting more often than we naturally
            # refresh anyway) - unless the caller explicitly wants a forced,
            # guaranteed-fresh fetch.
            now = datetime.now()
            if (not force and
                device_id in self._location_cache and
                device_id in self._location_cache_timestamp and
                (now - self._location_cache_timestamp[device_id]).total_seconds() < self._location_update_interval):
                logger.debug(f"Returning cached location for device {device_id}")
                return self._location_cache[device_id]

            logger.info(f"Fetching fresh location data for device {device_id}...")

            # Import necessary modules
            from NovaApi.ExecuteAction.LocateTracker.location_request import create_location_request
            from NovaApi.ExecuteAction.LocateTracker.decrypt_locations import retrieve_identity_key, is_mcu_tracker
            from NovaApi.nova_request import nova_request
            from NovaApi.scopes import NOVA_ACTION_API_SCOPE
            from NovaApi.util import generate_random_uuid
            from Auth.fcm_receiver import FcmReceiver
            from ProtoDecoders.decoder import parse_device_update_protobuf
            from ProtoDecoders import DeviceUpdate_pb2, Common_pb2
            import hashlib
            from KeyBackup.cloud_key_decryptor import decrypt_aes_gcm
            from FMDNCrypto.foreign_tracker_cryptor import decrypt
            from Auth.token_cache import get_cached_value

            result = None
            request_uuid = generate_random_uuid()

            def handle_location_response(response):
                nonlocal result
                device_update = parse_device_update_protobuf(response)
                if device_update.fcmMetadata.requestUuid == request_uuid:
                    result = device_update

            # Initialize the FCM receiver and register for updates under a
            # lock - concurrent callers (parallel background-cycle fetches,
            # or a force-refresh landing mid-cycle) must not race each other
            # into opening duplicate MCS connections (see the lock's comment
            # in __init__). Only the connect+register is serialized; the
            # response wait below runs fully concurrently per caller.
            async with self._fcm_registration_lock:
                if self._fcm_receiver is None:
                    self._fcm_receiver = FcmReceiver()
                try:
                    fcm_token = await self._fcm_receiver.register_for_location_updates(handle_location_response)
                except Exception as e:
                    logger.error(f"FCM registration failed: {e}")
                    logger.info("Location fetching is not available")
                    return None

            # Create and send location request
            hex_payload = create_location_request(device_id, fcm_token, request_uuid)
            try:
                nova_request(NOVA_ACTION_API_SCOPE, hex_payload)
            except KeyError as e:
                # See the matching guard in _fetch_devices_from_api - same underlying
                # cause (Google rejected the token, response has no 'Auth' key).
                logger.warning(
                    f"Google rejected the authentication token while fetching location "
                    f"for device {device_id} (missing {e} key - token likely revoked or "
                    "expired). Try re-authenticating."
                )
                return None

            # Wait for response (with timeout)
            timeout = 30  # 30 seconds timeout
            elapsed = 0
            while result is None and elapsed < timeout:
                await asyncio.sleep(0.5)
                elapsed += 0.5

            if result is None:
                logger.warning(f"Timeout waiting for location response for device {device_id}")
                return None

            # Extract and decrypt location data
            device_registration = result.deviceMetadata.information.deviceRegistration

            # retrieve_identity_key() needs the "shared key" (see
            # KeyBackup/shared_key_retrieval.py) regardless of whether this
            # particular report turns out to be an own-report or a
            # network/other-phone report. That key is only ever obtained
            # through a real, visible Chrome window during the VNC login
            # flow (vnc_auth_entrypoint.py) - this process has no display to
            # show one. Check the cache directly rather than calling through
            # and letting it attempt (and fail, or worse, hang) a live login
            # attempt with nowhere to render it.
            if get_cached_value('shared_key') is None:
                logger.warning(
                    f"No location for device {device_id}: the shared key needed to decrypt "
                    "location reports hasn't been set up yet. Log in again via "
                    "POST /auth/vnc/start (see AUTHENTICATION.md) and complete both sign-in "
                    "steps shown in the browser."
                )
                return None

            identity_key = retrieve_identity_key(device_registration)
            locations_proto = result.deviceMetadata.information.locationInformation.reports.recentLocationAndNetworkLocations
            is_mcu = is_mcu_tracker(device_registration)

            # Check for battery information in device metadata
            logger.debug(f"Device metadata fields: {result.deviceMetadata.ListFields()}")
            if result.deviceMetadata.HasField('information'):
                logger.debug(f"Device information fields: {result.deviceMetadata.information.ListFields()}")

            # Get recent location
            recent_location = locations_proto.recentLocation
            recent_location_time = locations_proto.recentLocationTimestamp

            # Get network locations
            network_locations = list(locations_proto.networkLocations)
            network_locations_time = list(locations_proto.networkLocationTimestamps)

            if locations_proto.HasField("recentLocation"):
                network_locations.append(recent_location)
                network_locations_time.append(recent_location_time)

            # Pick the candidate with the newest timestamp, not just the first
            # one in the list - `networkLocations` (crowd-sourced reports from
            # other people's phones) isn't guaranteed to come back sorted
            # newest-first, and taking whatever happened to be first (with our
            # own `recentLocation` appended last, so effectively never reached
            # whenever any network location existed) is how a stale report kept
            # winning over a genuinely fresher one.
            location_data = None
            if network_locations:
                candidates = list(zip(network_locations, network_locations_time))
                logger.info(
                    "Device %s: %d location candidate(s) in Google's response: %s",
                    device_id,
                    len(candidates),
                    [
                        {
                            "timestamp": int(c_time.seconds),
                            "own_report": c_loc.geoLocation.encryptedReport.publicKeyRandom == b"",
                            "status": str(c_loc.status),
                        }
                        for c_loc, c_time in candidates
                    ],
                )
                loc, time = max(candidates, key=lambda candidate: candidate[1].seconds)
                logger.info(
                    "Device %s: picked candidate with timestamp %d",
                    device_id,
                    int(time.seconds),
                )

                if loc.status == Common_pb2.Status.SEMANTIC:
                    # Semantic location (named place)
                    location_data = {
                        'type': 'semantic',
                        'name': loc.semanticLocation.locationName,
                        'timestamp': int(time.seconds),
                        'status': 'SEMANTIC',
                        'is_own_report': True
                    }
                else:
                    # Encrypted geo location
                    encrypted_location = loc.geoLocation.encryptedReport.encryptedLocation
                    public_key_random = loc.geoLocation.encryptedReport.publicKeyRandom

                    if public_key_random == b"":  # Own Report
                        identity_key_hash = hashlib.sha256(identity_key).digest()
                        decrypted_location = decrypt_aes_gcm(identity_key_hash, encrypted_location)
                    else:
                        time_offset = 0 if is_mcu else loc.geoLocation.deviceTimeOffset
                        decrypted_location = decrypt(identity_key, encrypted_location, public_key_random, time_offset)

                    # Parse decrypted location
                    proto_loc = DeviceUpdate_pb2.Location()
                    proto_loc.ParseFromString(decrypted_location)

                    location_data = {
                        'type': 'geo',
                        'latitude': proto_loc.latitude / 1e7,
                        'longitude': proto_loc.longitude / 1e7,
                        'altitude': proto_loc.altitude,
                        'accuracy': loc.geoLocation.accuracy,
                        'timestamp': int(time.seconds),
                        'status': str(loc.status),
                        'is_own_report': loc.geoLocation.encryptedReport.isOwnReport
                    }

            # Cache the result
            if location_data:
                self._location_cache[device_id] = location_data
                self._location_cache_timestamp[device_id] = now

            return location_data

        except Exception as e:
            logger.error(f"Error fetching location for device {device_id}: {e}", exc_info=True)
            return None

    async def _fetch_location_for_device(self, device_id: str, device_name: str, force: bool = False) -> Optional[Dict[str, Any]]:
        """Get location data for a specific device

        Note: Locations are updated automatically by the background task every
        LOCATION_UPDATE_INTERVAL seconds. By default this method just returns
        whatever is cached from that and does not trigger a fresh location
        request - pass force=True to actively request one from Google instead
        (takes up to ~30s; only use this for an explicit, on-demand refresh,
        not for routine polling).
        """
        if force:
            return await self._fetch_location_for_device_internal(device_id, device_name, force=True)

        try:
            # Return cached location if available
            if device_id in self._location_cache:
                logger.debug(f"Returning cached location for device {device_id}")
                return self._location_cache[device_id]

            logger.debug(f"No cached location available for device {device_id}")
            return None

        except Exception as e:
            logger.error(f"Error getting cached location for device {device_id}: {e}", exc_info=True)
            return None

    def _parse_device_basic(self, device_data: Dict[str, Any]) -> Device:
        """Parse basic device information"""
        try:
            # Extract basic information from device data
            device_id = device_data.get('id', device_data.get('deviceId', 'unknown'))
            name = device_data.get('name', device_data.get('deviceName', 'Unknown Device'))
            device_type = device_data.get('type', device_data.get('deviceType', 'UNKNOWN'))

            # Parse last seen timestamp from device data or location cache
            last_seen = None
            last_seen_str = device_data.get('lastSeenTimestamp', device_data.get('lastSeen'))
            if last_seen_str:
                try:
                    if isinstance(last_seen_str, (int, float)):
                        # Check if timestamp is in seconds or milliseconds
                        # Timestamps > 10^10 are likely in milliseconds
                        if last_seen_str > 10000000000:
                            last_seen = datetime.fromtimestamp(last_seen_str / 1000, tz=timezone.utc)
                        else:
                            last_seen = datetime.fromtimestamp(last_seen_str, tz=timezone.utc)
                    else:
                        last_seen = datetime.fromisoformat(str(last_seen_str).replace('Z', '+00:00'))
                except Exception as e:
                    logger.warning(f"Failed to parse last_seen timestamp: {e}")

            # If no last_seen in device_data, check location cache
            if last_seen is None and device_id in self._location_cache:
                location_data = self._location_cache[device_id]
                if 'timestamp' in location_data:
                    try:
                        # Location cache stores timestamps in seconds
                        last_seen = datetime.fromtimestamp(location_data['timestamp'], tz=timezone.utc)
                    except Exception as e:
                        logger.warning(f"Failed to parse last_seen from location cache: {e}")

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
            logger.debug(f"Device {name}: battery_data = {battery_data}, device_data keys = {list(device_data.keys())}")
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
                                # Check if timestamp is in seconds or milliseconds
                                # Timestamps > 10^10 are likely in milliseconds
                                if loc_time_str > 10000000000:
                                    loc_timestamp = datetime.fromtimestamp(loc_time_str / 1000, tz=timezone.utc)
                                else:
                                    loc_timestamp = datetime.fromtimestamp(loc_time_str, tz=timezone.utc)
                            else:
                                loc_timestamp = datetime.fromisoformat(str(loc_time_str).replace('Z', '+00:00'))
                        except Exception as e:
                            logger.warning(f"Failed to parse location timestamp {loc_time_str}: {e}")
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
                        # Check if timestamp is in seconds or milliseconds
                        # Timestamps > 10^10 are likely in milliseconds
                        if last_seen_str > 10000000000:
                            last_seen = datetime.fromtimestamp(last_seen_str / 1000, tz=timezone.utc)
                        else:
                            last_seen = datetime.fromtimestamp(last_seen_str, tz=timezone.utc)
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
            raise RuntimeError(f"Device service not initialized: {self.init_error or 'unknown initialization error'}")
        
        try:
            devices_data = await self._get_cached_devices()
            devices = [self._parse_device_basic(device_data) for device_data in devices_data]
            logger.info(f"Retrieved {len(devices)} devices")
            return devices
        except Exception as e:
            logger.error(f"Error getting all devices: {e}", exc_info=True)
            raise
    
    async def get_device_detail(self, device_id: str, fetch_location: bool = True, force_refresh: bool = False) -> Optional[DeviceDetail]:
        """Get detailed information for a specific device

        Args:
            device_id: The device ID to fetch details for
            fetch_location: Whether to include location data at all (default: True)
            force_refresh: Actively request a fresh location from Google
                instead of using the background task's cache (default: False -
                adds up to ~30s to the request, so leave this off for routine
                polling and only set it for an explicit user-triggered refresh)
        """
        if not self.initialized:
            raise RuntimeError(f"Device service not initialized: {self.init_error or 'unknown initialization error'}")

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

            # Fetch location data if requested
            if fetch_location:
                device_name = device_data.get('name', device_data.get('deviceName', 'Unknown'))
                location_data = await self._fetch_location_for_device(device_id, device_name, force=force_refresh)

                if location_data:
                    # Add location data to device_data
                    if location_data['type'] == 'geo':
                        device_data['location'] = {
                            'latitude': location_data['latitude'],
                            'longitude': location_data['longitude'],
                            'accuracy': location_data.get('accuracy'),
                            'timestamp': location_data['timestamp']
                        }
                        device_data['lastSeenTimestamp'] = location_data['timestamp'] * 1000  # Convert to milliseconds

                        # Generate Google Maps link
                        lat = location_data['latitude']
                        lon = location_data['longitude']
                        device_data['google_maps_link'] = f"https://www.google.com/maps?q={lat},{lon}"
                    elif location_data['type'] == 'semantic':
                        device_data['location'] = {
                            'semantic_name': location_data['name'],
                            'timestamp': location_data['timestamp']
                        }
                        device_data['lastSeenTimestamp'] = location_data['timestamp'] * 1000

            device_detail = self._parse_device_detail(device_data)
            logger.info(f"Retrieved detail for device {device_id}")
            return device_detail

        except Exception as e:
            logger.error(f"Error getting device detail: {e}", exc_info=True)
            raise

