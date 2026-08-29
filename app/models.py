"""
Data models for the REST API
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Device(BaseModel):
    """Basic device information"""
    device_id: str = Field(..., description="Unique device identifier")
    name: str = Field(..., description="Device name")
    device_type: str = Field(..., description="Type of device (currently always SPOT_DEVICE in practice)")
    last_seen: Optional[datetime] = Field(None, description="Last seen timestamp")
    status: Optional[str] = Field(None, description="Device status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "689a0735-0000-2f84-82f1-f403043a0b70",
                "name": "My Tracker",
                "device_type": "SPOT_DEVICE",
                "last_seen": "2024-01-15T10:30:00Z",
                "status": "ACTIVE"
            }
        }


class Location(BaseModel):
    """Location information"""
    latitude: Optional[float] = Field(None, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, description="Longitude coordinate")
    accuracy: Optional[float] = Field(None, description="Location accuracy in meters")
    timestamp: Optional[datetime] = Field(None, description="Location timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "latitude": 37.7749,
                "longitude": -122.4194,
                "accuracy": 10.5,
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


class DeviceDetail(BaseModel):
    """Detailed device information"""
    device_id: str = Field(..., description="Unique device identifier")
    name: str = Field(..., description="Device name")
    device_type: str = Field(..., description="Type of device")
    model: Optional[str] = Field(None, description="Device model")
    battery_level: Optional[int] = Field(None, description="Battery level percentage (0-100)")
    location: Optional[Location] = Field(None, description="Current location")
    last_seen: Optional[datetime] = Field(None, description="Last seen timestamp")
    status: Optional[str] = Field(None, description="Device status")
    additional_info: Optional[dict] = Field(None, description="Additional device information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "689a0735-0000-2f84-82f1-f403043a0b70",
                "name": "My Tracker",
                "device_type": "SPOT_DEVICE",
                "model": "Fast Pair Model bbe0d0",
                "battery_level": None,
                "location": {
                    "latitude": 37.7749,
                    "longitude": -122.4194,
                    "accuracy": 10.5,
                    "timestamp": "2024-01-15T10:30:00Z"
                },
                "last_seen": "2024-01-15T10:30:00Z",
                "status": "ACTIVE",
                "additional_info": {}
            }
        }


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error type")
    detail: str = Field(..., description="Error details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Not Found",
                "detail": "Device with ID 'abc123' not found"
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    message: str = Field(..., description="Status message")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "message": "Service is running normally"
            }
        }


class VncAuthStartResponse(BaseModel):
    """Response returned when a VNC authentication session is started"""
    vnc_url: str = Field(..., description="Open this URL in a browser to complete the login")
    password: str = Field(..., description="VNC password, also embedded in vnc_url")
    novnc_port: int = Field(..., description="Port the noVNC web UI is listening on")
    expires_in_seconds: int = Field(..., description="Session is torn down automatically after this many seconds if not completed")

    class Config:
        json_schema_extra = {
            "example": {
                "vnc_url": "http://192.168.1.100:6080/vnc.html?autoconnect=true&password=aB3xY9kQ",
                "password": "aB3xY9kQ",
                "novnc_port": 6080,
                "expires_in_seconds": 600
            }
        }


class VncAuthStatusResponse(BaseModel):
    """Current state of the VNC authentication session"""
    state: str = Field(..., description="idle, running, succeeded, or failed")
    error: Optional[str] = Field(None, description="Failure reason, if state is failed")
    authenticated: bool = Field(..., description="Whether secrets.json currently holds a valid, authenticated session")

    class Config:
        json_schema_extra = {
            "example": {
                "state": "succeeded",
                "error": None,
                "authenticated": True
            }
        }

