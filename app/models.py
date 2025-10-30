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
    device_type: str = Field(..., description="Type of device (e.g., TRACKER, PHONE)")
    last_seen: Optional[datetime] = Field(None, description="Last seen timestamp")
    status: Optional[str] = Field(None, description="Device status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "abc123def456",
                "name": "My Tracker",
                "device_type": "TRACKER",
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
                "device_id": "abc123def456",
                "name": "My Tracker",
                "device_type": "TRACKER",
                "model": "Custom ESP32",
                "battery_level": 85,
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

