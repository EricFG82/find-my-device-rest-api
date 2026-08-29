"""
GoogleFindMyTools REST API Service
A REST API service that exposes Google Find My Device functionality
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from typing import List, Optional

from app.models import (
    Device,
    DeviceDetail,
    ErrorResponse,
    HealthResponse,
    VncAuthStartResponse,
    VncAuthStatusResponse,
)
from app.services.device_service import DeviceService
from app.services.vnc_auth_service import VncAuthService

# Configure logging
import os
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set via --build-arg APP_VERSION at image build time (see rest-api/RELEASING.md);
# defaults to "0.0.0-dev" for local, non-image runs (e.g. uvicorn --reload).
APP_VERSION = os.getenv("APP_VERSION", "0.0.0-dev")

# Global device service instance
device_service: Optional[DeviceService] = None


async def _reinitialize_device_service_after_vnc_auth():
    """Called once a VNC auth session succeeds, so the already-running app
    picks up the new secrets.json without needing a manual restart.

    Only actually re-initializes if device_service didn't already have working
    auth (e.g. the container started with no secrets.json at all) - if it was
    already initialized, re-running initialize() would start a second
    background location updater on top of the running one, reintroducing the
    exact FCM/MCS reconnect-storm bug fixed in v1.1.0.
    """
    global device_service
    if device_service is None or device_service.initialized:
        return

    logger.info("VNC authentication succeeded - re-initializing device service...")
    try:
        await device_service.initialize()
        logger.info("Device service re-initialized successfully after VNC authentication")
    except Exception as e:
        logger.error(f"Failed to re-initialize device service after VNC authentication: {e}")


# VNC auth service doesn't need async initialization, so it can be created
# eagerly - unlike device_service, there's no external dependency to verify
# at startup (the whole point is that it can run even without secrets.json).
vnc_auth_service = VncAuthService(on_success=_reinitialize_device_service_after_vnc_auth)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    global device_service
    
    # Startup
    logger.info("Starting GoogleFindMyTools REST API Service...")
    device_service = DeviceService()
    try:
        await device_service.initialize()
        logger.info("Device service initialized successfully")
    except Exception as e:
        # Don't crash the process here: keep serving so /health can report the
        # specific failure reason (e.g. missing secrets.json) instead of the
        # container just crash-looping with no visible status.
        logger.error(f"Failed to initialize device service: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down GoogleFindMyTools REST API Service...")
    if device_service:
        await device_service.cleanup()
    await vnc_auth_service.stop()


# Create FastAPI app
app = FastAPI(
    title="GoogleFindMyTools REST API",
    description="REST API service for Google Find My Device functionality",
    version=APP_VERSION,
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
        "version": APP_VERSION,
        "description": "REST API service for Google Find My Device functionality",
        "endpoints": {
            "health": "/health",
            "devices": "/api/v1/devices",
            "device_detail": "/api/v1/devices/{device_id}",
            "vnc_auth_start": "/auth/vnc/start",
            "vnc_auth_status": "/auth/vnc/status",
            "vnc_auth_stop": "/auth/vnc/stop",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    responses={
        503: {
            "model": HealthResponse,
            "description": "Service unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "message": "Authentication not configured: secrets.json is missing, empty, or invalid (no authenticated username found). Check the volume/file mount for secrets.json."
                    }
                }
            }
        }
    }
)
async def health_check():
    """Health check endpoint"""
    if device_service is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=HealthResponse(status="unhealthy", message="Service not initialized").model_dump()
        )

    is_healthy = await device_service.health_check()

    if not is_healthy:
        reason = device_service.init_error or "Service failed to initialize (unknown reason)"
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=HealthResponse(status="unhealthy", message=reason).model_dump()
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


@app.post(
    "/auth/vnc/start",
    response_model=VncAuthStartResponse,
    responses={409: {"model": ErrorResponse, "description": "A session is already running"}}
)
async def start_vnc_auth(request: Request):
    """
    Start an in-browser (VNC) authentication session.

    Spins up a virtual display and a real (non-headless) Chrome window, then
    triggers Google's OAuth login flow against it. Open the returned
    `vnc_url` in a browser to see and interact with that Chrome window
    (CAPTCHA/2FA included) and complete the login. See AUTHENTICATION.md.
    """
    try:
        result = await vnc_auth_service.start()
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start VNC auth session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start VNC auth session: {str(e)}"
        )

    host = request.url.hostname or "localhost"
    vnc_url = f"http://{host}:{result['novnc_port']}/vnc.html?autoconnect=true&password={result['password']}"

    return VncAuthStartResponse(
        vnc_url=vnc_url,
        password=result["password"],
        novnc_port=result["novnc_port"],
        expires_in_seconds=result["expires_in_seconds"],
    )


@app.get("/auth/vnc/status", response_model=VncAuthStatusResponse)
async def vnc_auth_status():
    """Current state of the VNC authentication session (idle/running/succeeded/failed)."""
    result = await vnc_auth_service.status()
    return VncAuthStatusResponse(**result)


@app.post("/auth/vnc/stop")
async def stop_vnc_auth():
    """Tear down the VNC authentication session, if one is running."""
    await vnc_auth_service.stop()
    return {"status": "stopped"}


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

