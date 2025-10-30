# Google Find My Device REST API Service

A REST API service that exposes Google Find My Device functionality using the [GoogleFindMyTools](https://github.com/leonboe1/GoogleFindMyTools) library.

## Features

- **List all devices**: Get a list of all devices registered in Google Find My Device
- **Device details**: Get detailed information for a specific device including location, battery level, and status
- **Automatic API documentation**: Interactive API docs at `/docs` (Swagger UI) and `/redoc` (ReDoc)
- **Health checks**: Built-in health check endpoint for monitoring
- **Caching**: Intelligent caching to reduce API calls
- **Docker support**: Easy deployment with Docker and docker-compose

## API Endpoints

### Core Endpoints

- `GET /` - API information and available endpoints
- `GET /health` - Health check endpoint
- `GET /api/v1/devices` - List all devices
- `GET /api/v1/devices/{device_id}` - Get detailed information for a specific device

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

   **Note**: This method uses headless Chrome inside Docker, which may have limitations with certain authentication flows (e.g., CAPTCHA, advanced 2FA). If you encounter issues, use Method 1 instead.

   The authentication data will be saved in `./auth_data/secrets.json`.

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
    "device_id": "abc123def456",
    "name": "My Tracker",
    "device_type": "TRACKER",
    "last_seen": "2024-01-15T10:30:00Z",
    "status": "ACTIVE"
  },
  {
    "device_id": "xyz789ghi012",
    "name": "My Phone",
    "device_type": "PHONE",
    "last_seen": "2024-01-15T11:00:00Z",
    "status": "ACTIVE"
  }
]
```

### Device Detail Response

```json
{
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
```

## Configuration

### Environment Variables

You can configure the service using environment variables:

- `LOG_LEVEL`: Logging level (default: INFO)
- `CACHE_TTL`: Cache time-to-live in seconds (default: 60)

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
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Security Considerations

- This service is designed for **local-only** deployment
- No authentication is implemented (add authentication for production use)
- The `secrets.json` file contains sensitive authentication data - keep it secure
- Consider using environment variables for sensitive configuration

## License

This project uses the GoogleFindMyTools library which is licensed under GPL-3.0.

## Credits

- [GoogleFindMyTools](https://github.com/leonboe1/GoogleFindMyTools) by leonboe1
- Built with [FastAPI](https://fastapi.tiangolo.com/)
