"""
GoogleFindMyTools REST API Service
A REST API service that exposes Google Find My Device functionality
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from typing import List, Optional

from app.models import Device, DeviceDetail, ErrorResponse, HealthResponse
from app.services.device_service import DeviceService

# Configure logging
import os
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global device service instance
device_service: Optional[DeviceService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    global device_service
    
    # Startup
    logger.info("Starting GoogleFindMyTools REST API Service...")
    try:
        device_service = DeviceService()
        await device_service.initialize()
        logger.info("Device service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize device service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down GoogleFindMyTools REST API Service...")
    if device_service:
        await device_service.cleanup()


# Create FastAPI app
app = FastAPI(
    title="GoogleFindMyTools REST API",
    description="REST API service for Google Find My Device functionality",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=dict)
async def root():
    """Root endpoint with API information"""
    return {
        "name": "GoogleFindMyTools REST API",
        "version": "1.0.0",
        "description": "REST API service for Google Find My Device functionality",
        "endpoints": {
            "health": "/health",
            "devices": "/api/v1/devices",
            "device_detail": "/api/v1/devices/{device_id}",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    if device_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not initialized"
        )
    
    is_healthy = await device_service.health_check()
    
    if not is_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is unhealthy"
        )
    
    return HealthResponse(
        status="healthy",
        message="Service is running normally"
    )


@app.get(
    "/api/v1/devices",
    response_model=List[Device],
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    }
)
async def get_devices():
    """
    Get a list of all devices
    
    Returns a list of all devices registered in Google Find My Device,
    including basic information like device ID, name, type, and last seen timestamp.
    """
    if device_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not initialized"
        )
    
    try:
        devices = await device_service.get_all_devices()
        return devices
    except Exception as e:
        logger.error(f"Error fetching devices: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch devices: {str(e)}"
        )


@app.get(
    "/api/v1/devices/{device_id}",
    response_model=DeviceDetail,
    responses={
        404: {"model": ErrorResponse, "description": "Device not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    }
)
async def get_device_detail(device_id: str):
    """
    Get detailed information for a specific device
    
    Returns detailed information about a specific device including:
    - Device ID and name
    - Device type and model
    - Battery level (if available)
    - Location coordinates (latitude, longitude)
    - Location accuracy
    - Last seen timestamp
    - Device status
    
    Args:
        device_id: The unique identifier of the device
    """
    if device_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not initialized"
        )
    
    try:
        device_detail = await device_service.get_device_detail(device_id)
        
        if device_detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device with ID '{device_id}' not found"
            )
        
        return device_detail
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching device detail for {device_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch device detail: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

