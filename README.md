# Google Find My Device REST API Service

A REST API service that exposes Google Find My Device functionality using the [GoogleFindMyTools](https://github.com/leonboe1/GoogleFindMyTools) library.

> Deploying a pre-built image via Portainer, or cutting a new release? See [RELEASING.md](RELEASING.md).

## Features

- **List all devices**: Get a list of all devices registered in Google Find My Device with last seen timestamps
- **Device details**: Get detailed information for a specific device including:
  - Real-time location data (latitude, longitude, accuracy)
  - Device metadata (model, image URL, identifier type)
  - Last seen timestamp
  - Device status
- **Automatic location updates**: Background task that fetches device locations every 5 minutes (can be disabled)
- **Automatic API documentation**: Interactive API docs at `/docs` (Swagger UI) and `/redoc` (ReDoc)
- **Health checks**: Built-in health check endpoint for monitoring
- **Intelligent caching**: 60-second cache for device list, 5-minute cache for locations
- **Docker support**: Easy deployment with Docker and docker-compose
- **Synology NAS compatible**: Works on Synology NAS with Container Manager

## API Endpoints

### Core Endpoints

- `GET /` - API information and available endpoints
- `GET /health` - Health check endpoint. Returns `200` with
  `{"status":"healthy","message":"Service is running normally"}` when initialized
  correctly, or `503` with `{"status":"unhealthy","message":"<specific reason>"}`
  when it isn't (e.g. `secrets.json` missing/invalid) - the message names the actual
  cause, not just "unhealthy". The container itself stays up either way, so this is
  safe to check without risking a crash-loop.
- `GET /api/v1/devices` - List all devices
- `GET /api/v1/devices/{device_id}` - Get detailed information for a specific device
- `POST /auth/vnc/start` / `GET /auth/vnc/status` / `POST /auth/vnc/stop` -
  In-browser authentication (no local Chrome needed) via noVNC - see
  [AUTHENTICATION.md](../AUTHENTICATION.md#method-3-authenticate-via-browser-vnc---no-local-chrome-needed)

### Documentation

- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

## Prerequisites

### For Docker Deployment (Recommended)

- Docker
- Docker Compose
- Google Account with Find My Device enabled
- **Note**: Chromium browser is included in the Docker image (works on both ARM64 and AMD64)

### For Local Development

- Python 3.11+
- Chromium or Google Chrome (required for authentication)
- Google Account with Find My Device enabled

## Setup and Installation

### Option 1: Docker Deployment (Recommended)

1. **Clone this repository**:

   ```bash
   cd rest-api
   ```

2. **Create auth data directory**:

   ```bash
   mkdir -p auth_data
   ```

3. **First-time authentication** (required before running the service):

   Since the service needs to authenticate with Google, you need to run the authentication process first. Choose one of the following methods:

   #### Method 1: Authenticate Outside Docker (Recommended)

   This method is easier and more reliable as it allows you to use your system's Chrome browser for authentication:

   ```bash
   # Navigate to the project root
   cd ..

   # Install Python dependencies (one-time setup)
   pip3 install -r GoogleFindMyTools/requirements.txt

   # Run authentication script (will open Chrome on your system)
   cd GoogleFindMyTools
   python3 main.py
   ```

   Follow the on-screen instructions:

   - Press Enter when prompted
   - Chrome will open automatically
   - Log in to your Google account
   - Grant permissions to the application
   - Complete any 2FA if enabled
   - Wait for the script to complete

   After successful authentication, copy the secrets file to the Docker volume:

   ```bash
   # Copy authentication file to Docker volume
   cp Auth/secrets.json ../rest-api/auth_data/

   # Return to rest-api directory
   cd ../rest-api
   ```

   #### Method 2: Authenticate Inside Docker (Advanced)

   This method runs authentication in a headless browser inside Docker:

   ```bash
   # Build the image
   docker-compose build

   # Run authentication in interactive mode
   docker compose run --rm -w /app/GoogleFindMyTools google-findmy-api python main.py
   ```

   **Note**: This method uses headless Chrome inside Docker, which may have limitations with certain authentication flows (e.g., CAPTCHA, advanced 2FA). If you encounter issues, use Method 1 or Method 3 instead.

   The authentication data will be saved in `./auth_data/secrets.json`.

   #### Method 3: Authenticate via Browser (VNC) - No Local Chrome Needed

   Full CAPTCHA/2FA support like Method 1, but entirely through the container -
   nothing to install locally, nothing to copy over. See
   [AUTHENTICATION.md](../AUTHENTICATION.md#method-3-authenticate-via-browser-vnc---no-local-chrome-needed)
   for the full walkthrough; the short version:

   ```bash
   docker compose up -d
   curl -X POST http://localhost:8000/auth/vnc/start   # returns a vnc_url + password
   # open vnc_url in a browser, log in, then:
   curl http://localhost:8000/auth/vnc/status           # watch for "succeeded" - no restart needed
   ```

4. **Start the service**:

   ```bash
   docker-compose up -d
   ```

5. **Check service status**:

   ```bash
   docker-compose ps
   docker-compose logs -f google-findmy-api
   ```

6. **Access the API**:
   - API: http://localhost:8000
   - Interactive docs: http://localhost:8000/docs
   - Health check: http://localhost:8000/health

### Option 2: Local Development

1. **Clone GoogleFindMyTools**:

   ```bash
   cd rest-api
   git clone https://github.com/leonboe1/GoogleFindMyTools.git
   ```

2. **Create virtual environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Authenticate with Google** (first time only):

   ```bash
   cd GoogleFindMyTools
   python main.py
   ```

   Follow the authentication process. This will create `GoogleFindMyTools/Auth/secrets.json`.

5. **Run the API service**:

   ```bash
   cd ..
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

6. **Access the API**:
   - API: http://localhost:8000
   - Interactive docs: http://localhost:8000/docs

## Usage Examples

### Using curl

**List all devices**:

```bash
curl http://localhost:8000/api/v1/devices
```

**Get device details**:

```bash
curl http://localhost:8000/api/v1/devices/{device_id}
```

**Health check**:

```bash
curl http://localhost:8000/health
```

### Using Python

```python
import requests

# List all devices
response = requests.get('http://localhost:8000/api/v1/devices')
devices = response.json()
print(f"Found {len(devices)} devices")

# Get device details
device_id = devices[0]['device_id']
response = requests.get(f'http://localhost:8000/api/v1/devices/{device_id}')
device_detail = response.json()
print(f"Device: {device_detail['name']}")
print(f"Location: {device_detail['location']}")
print(f"Battery: {device_detail['battery_level']}%")
```

### Using JavaScript/Node.js

```javascript
// List all devices
fetch("http://localhost:8000/api/v1/devices")
  .then((response) => response.json())
  .then((devices) => {
    console.log(`Found ${devices.length} devices`);

    // Get details for first device
    const deviceId = devices[0].device_id;
    return fetch(`http://localhost:8000/api/v1/devices/${deviceId}`);
  })
  .then((response) => response.json())
  .then((device) => {
    console.log(`Device: ${device.name}`);
    console.log(`Location: ${device.location}`);
    console.log(`Battery: ${device.battery_level}%`);
  });
```

## Response Examples

### List Devices Response

```json
[
  {
    "device_id": "689a0735-0000-2f84-82f1-f403043a0b70",
    "name": "My Tracker",
    "device_type": "SPOT_DEVICE",
    "last_seen": "2024-01-15T10:30:00Z",
    "status": "ACTIVE"
  },
  {
    "device_id": "66664988-0000-2b56-9aee-14c14ef7a9f8",
    "name": "My Phone",
    "device_type": "SPOT_DEVICE",
    "last_seen": "2024-01-15T11:00:00Z",
    "status": "ACTIVE"
  }
]
```

`device_type` is currently always `SPOT_DEVICE` regardless of the actual underlying
device (phone or tracker) - the API doesn't yet distinguish them.

### Device Detail Response

```json
{
  "device_id": "689a0735-0000-2f84-82f1-f403043a0b70",
  "name": "My Tracker",
  "device_type": "SPOT_DEVICE",
  "model": "Fast Pair Model bbe0d0",
  "battery_level": null,
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
```

`battery_level` is currently always `null`: Google's Find My Device network doesn't
expose a battery percentage for `SPOT_DEVICE` trackers in the reverse-engineered
protocol this project uses.

## Configuration

### Environment Variables

You can configure the service using environment variables in `docker-compose.yml`:

#### Core Settings

- `LOG_LEVEL`: Logging level (default: `INFO`, options: `DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `PYTHONUNBUFFERED`: Set to `1` to see logs in real-time

#### Device Service Settings

- **`DEVICE_CACHE_TTL`**: Cache time-to-live for device list in seconds (default: `60`)

  - How long to cache the list of devices before fetching fresh data
  - Lower values = more API calls but fresher data
  - Recommended: 30-120 seconds

- **`LOCATION_UPDATE_INTERVAL`**: Background location update interval in seconds (default: `300` = 5 minutes)

  - How often to automatically fetch fresh location data for all devices
  - Lower values = more frequent updates but more API calls and battery drain
  - Recommended: 180-600 seconds (3-10 minutes)
  - **Note**: This is independent of Home Assistant's polling interval

- **`ENABLE_LOCATION_UPDATES`**: Enable/disable background location updates (default: `true`)
  - Set to `false` to disable automatic location fetching
  - When disabled, locations are only fetched on-demand when you call the API
  - Useful for reducing network usage or battery drain

#### Example Configuration

```yaml
environment:
  - LOG_LEVEL=DEBUG
  - DEVICE_CACHE_TTL=60
  - LOCATION_UPDATE_INTERVAL=180 # Update every 3 minutes
  - ENABLE_LOCATION_UPDATES=true
```

### How Location Updates Work

The service uses a two-tier caching system:

1. **Device List Cache** (`DEVICE_CACHE_TTL`):

   - Caches the list of devices (names, IDs, basic info)
   - Default: 60 seconds
   - Lightweight, can be refreshed frequently

2. **Location Cache** (`LOCATION_UPDATE_INTERVAL`):
   - Background task that fetches actual GPS coordinates
   - Default: 300 seconds (5 minutes)
   - More resource-intensive, should be refreshed less frequently

**Example Scenario:**

- `DEVICE_CACHE_TTL=60` and `LOCATION_UPDATE_INTERVAL=300`
- Device list refreshes every 60 seconds
- Locations update every 5 minutes in the background
- Home Assistant polls every 60 seconds and gets the latest cached location

**For Faster Updates:**

```yaml
environment:
  - DEVICE_CACHE_TTL=30
  - LOCATION_UPDATE_INTERVAL=120 # Update every 2 minutes
```

**For Battery Conservation:**

```yaml
environment:
  - DEVICE_CACHE_TTL=120
  - LOCATION_UPDATE_INTERVAL=600 # Update every 10 minutes
```

### Docker Compose Configuration

Edit `docker-compose.yml` to customize:

- Port mapping (default: 8000:8000)
- Volume mounts
- Environment variables
- Resource limits

## Troubleshooting

### Authentication Issues

**Authentication fails in Docker (headless mode)**:

- **Solution**: Use Method 1 (authenticate outside Docker) instead
- The headless browser in Docker may not support all authentication flows
- CAPTCHA and advanced 2FA may not work in headless mode

**"ModuleNotFoundError" when running authentication outside Docker**:

```bash
# Install required dependencies
pip3 install -r GoogleFindMyTools/requirements.txt

# Or install specific packages
pip3 install selenium undetected-chromedriver gpsoauth requests beautifulsoup4 pyscrypt cryptography
```

**Chrome/Chromium not found when running outside Docker**:

- **macOS**: Install Chrome from https://www.google.com/chrome/
- **Linux**: Install Chromium: `sudo apt-get install chromium-browser`
- Ensure Chrome/Chromium is in your PATH

**Authentication completes but secrets.json not created**:

- Check the `GoogleFindMyTools/Auth/` directory for `secrets.json`
- Ensure you have write permissions in the directory
- Look for error messages in the terminal output

**"Your encryption data is locked on your device"**:

1. Login to an Android device with your Google Account
2. Go to Settings > Google > All Services > Find My Device
3. Enable "Find your offline devices"
4. If the option is not available, install the Find My Device app from Play Store

### Service Not Starting

Check the logs:

```bash
docker-compose logs -f google-findmy-api
```

Common issues:

- Missing `auth_data/secrets.json` file - complete authentication first
- Port 8000 already in use - change port in docker-compose.yml
- Docker daemon not running - start Docker Desktop

### Connection Refused

Ensure the service is running:

```bash
docker-compose ps
curl http://localhost:8000/health
```

If the service is running but not responding:

- Check firewall settings
- Verify port mapping in docker-compose.yml
- Check container logs for errors

## Development

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

### Code Structure

```
rest-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── models.py            # Pydantic models
│   └── services/
│       ├── __init__.py
│       └── device_service.py # Device service logic
├── patch_chrome_driver.py   # Patch for Chrome driver compatibility
├── patch_fcm_receiver.py    # Patch for FCM async compatibility
├── Dockerfile                        # Also accepts an APP_VERSION build-arg (see RELEASING.md)
├── docker-compose.yml                # Local dev: builds the image from source
├── docker-compose.portainer.yml      # Production: pulls the published image
├── RELEASING.md                      # How the Docker image gets published (GitHub Actions)
├── requirements.txt
└── README.md
```

Publishing the Docker image is handled entirely by
[`.github/workflows/docker-publish.yml`](../.github/workflows/docker-publish.yml) -
there's no local build/push script; see [RELEASING.md](RELEASING.md).

### Technical Implementation Details

**FCM Receiver Async Compatibility Fix**

The GoogleFindMyTools library's `fcm_receiver.py` originally used synchronous methods with `asyncio.get_event_loop().run_until_complete()`, which caused nested event loop errors in Docker environments. This service includes an automatic patch (`patch_fcm_receiver.py`) that:

1. Converts `register_for_location_updates()` from sync to async
2. Converts `stop_listening()` from sync to async
3. Converts `get_android_id()` from sync to async
4. Replaces `asyncio.get_event_loop().run_until_complete()` with proper `await` statements

The patch is automatically applied during Docker build, ensuring compatibility with all environments including Synology NAS.

**Background Task Implementation**

The service uses FastAPI's lifespan events to manage a background asyncio task that:

1. Waits 30 seconds after startup
2. Fetches device list from Google API
3. For each device, registers for FCM notifications and requests location update
4. Caches location data with 5-minute TTL
5. Repeats every 5 minutes

This approach ensures location data is always fresh while minimizing API calls and network usage.

## Synology NAS Deployment

Two ways to run this on a Synology NAS:

- **Build it yourself with Container Manager's "Project" feature** - covered below
  and in [SYNOLOGY_SETUP.md](SYNOLOGY_SETUP.md). Builds the image on the NAS itself
  from this repo's `Dockerfile`.
- **Pull a pre-built image via Portainer** - faster (no build on the NAS), works with
  a private Docker Hub image published by CI. See [RELEASING.md](RELEASING.md) and
  [`docker-compose.portainer.yml`](docker-compose.portainer.yml). Note: Synology's
  own Container Manager "check for update" badge doesn't reliably track images
  managed this way - see RELEASING.md for how to actually redeploy a new version.

### ⚠️ Important: Authentication

**If using Method 1 or 2, you must authenticate on your Mac/PC before deploying
to Synology NAS** - those methods can't do an interactive login inside the
container. **This isn't required with Method 3**: authenticate directly on
the NAS through a browser instead - see
[AUTHENTICATION.md, Method 3](../AUTHENTICATION.md#method-3-authenticate-via-browser-vnc---no-local-chrome-needed).

### Quick Start

1. **Authenticate on your Mac/PC** (see "Setup and Installation" section above)
2. **Copy `secrets.json`** to `rest-api/auth_data/` directory
3. **Upload entire `rest-api` folder** to your Synology NAS
4. **Deploy using Container Manager**

### 📖 Detailed Setup Guide

For complete step-by-step instructions, troubleshooting, and common errors, see:

**[SYNOLOGY_SETUP.md](SYNOLOGY_SETUP.md)** - Comprehensive Synology deployment guide

### Common Error: "EOFError: EOF when reading a line"

If you see this error in Container Manager logs, it means the `secrets.json` file is missing or not properly mounted. See [SYNOLOGY_SETUP.md](SYNOLOGY_SETUP.md) for the solution.

### Quick Deployment Steps

1. **Authenticate on your computer**:

   ```bash
   cd GoogleFindMyTools
   python3 main.py
   cp Auth/secrets.json ../rest-api/auth_data/
   ```

2. **Upload to Synology**:

   - Upload entire `rest-api` folder to `/docker/google-findmy-api/`
   - Verify `secrets.json` is in `/docker/google-findmy-api/rest-api/auth_data/`

3. **Deploy using Container Manager**:

   - Open Container Manager → Project tab
   - Create new project from `/docker/google-findmy-api/rest-api/docker-compose.yml`
   - Build and start

4. **Access the API**:
   - API: `http://YOUR_NAS_IP:8000`
   - Docs: `http://YOUR_NAS_IP:8000/docs`
   - All features including automatic location updates work out of the box!

### Technical Details

**Fixed: Event Loop Compatibility Issue**

Previous versions had issues with FCM (Firebase Cloud Messaging) in Docker environments due to nested event loop problems in the GoogleFindMyTools library. This has been **permanently fixed** by patching the library during Docker build to use proper async/await patterns.

The service now includes:

- ✅ Automatic FCM receiver patching during build
- ✅ Proper async/await implementation
- ✅ Full compatibility with Synology NAS and other Docker environments
- ✅ Automatic location updates working in all environments

**Backward Compatibility**: The `ENABLE_LOCATION_UPDATES` environment variable is still available if you need to disable location updates for any reason, but it's no longer necessary for stability.

## Configuration Options

### Environment Variables

You can configure the service using environment variables in `docker-compose.yml`:

| Variable                  | Default | Description                                          |
| ------------------------- | ------- | ---------------------------------------------------- |
| `PYTHONUNBUFFERED`        | `1`     | Enable Python unbuffered output for better logging   |
| `LOG_LEVEL`               | `INFO`  | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)  |
| `ENABLE_LOCATION_UPDATES` | `true`  | Enable/disable automatic background location updates |

### Location Updates

The service includes automatic background location updates that fetch device locations every 5 minutes using FCM (Firebase Cloud Messaging).

**Features:**

- ✅ Automatic updates every 5 minutes
- ✅ Cached location data for fast API responses
- ✅ Real-time location accuracy with latitude, longitude, and accuracy
- ✅ Works with all Google Find My Device trackers
- ✅ **Now works in all Docker environments** (including Synology NAS)
- ✅ Proper async/await implementation (no more event loop errors)

**How it works:**

1. Service starts and waits 30 seconds before first update
2. Background task fetches location for each device sequentially
3. Locations are cached for 5 minutes
4. Updates repeat every 5 minutes automatically
5. API responses use cached data for fast performance

**Requirements:**

- ⚠️ Requires stable network connection
- ⚠️ First location update takes 30 seconds after service start
- ⚠️ Each device location fetch takes ~2-3 seconds

**Optional: Disable location updates**

If you want to disable automatic location updates (e.g., to reduce network usage), set `ENABLE_LOCATION_UPDATES=false` in `docker-compose.yml`. The API will still work for:

- Listing all devices
- Getting device details (name, ID, type, status)
- Device metadata (model, image URL, etc.)

Location data will not be automatically fetched, but the service will remain stable.

## Security Considerations

- This service is designed for **local-only** deployment
- No authentication is implemented (add authentication for production use)
- The `secrets.json` file contains sensitive authentication data - keep it secure
- Consider using environment variables for sensitive configuration

## License

GPL-3.0 - see the [root LICENSE](../LICENSE) for the full text and why (this
service imports the GPL-3.0-licensed GoogleFindMyTools directly).

## Credits

- [GoogleFindMyTools](https://github.com/leonboe1/GoogleFindMyTools) by leonboe1
- Built with [FastAPI](https://fastapi.tiangolo.com/)
