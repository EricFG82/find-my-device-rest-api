# Find My Device - Authentication Guide

This guide explains how to authenticate with Google Find My Device for the REST API service.

## Overview

The REST API service requires authentication with your Google account to access Find My Device data. You need to complete this authentication **once** before starting the service. The authentication data is saved in `auth_data/secrets.json` and persists across container restarts.

### Understanding the Project Structure

```
Project Root: <path-to-your-clone>/
├── Dockerfile                     # Clones GoogleFindMyTools during build
├── docker-compose.yml
├── auth_data/                     # ← Docker volume (exposed folder)
│   └── secrets.json               # ← Authentication file goes here
│
└── GoogleFindMyTools/              # ← Git repo (cloned locally for Method 1, gitignored)
    ├── main.py                    # Authentication script
    ├── Auth/
    │   └── secrets.json           # ← Generated here, copy to ../auth_data/
    └── requirements.txt
```

**Note**: The `GoogleFindMyTools` directory is:

- The original Python library from https://github.com/leonboe1/GoogleFindMyTools
- Automatically cloned **inside** the Docker container during build
- Also cloned **locally, inside this repo** for Method 1 authentication (already gitignored)

## Prerequisites

- Google Account with Find My Device enabled
- Chrome or Chromium browser (for Method 1)
- Python 3.11+ (for Method 1)

## Authentication Methods

### Method 1: Authenticate Outside Docker (Recommended) ⭐

This is the **easiest and most reliable** method. It uses your system's Chrome browser for authentication, which supports all authentication flows including CAPTCHA and advanced 2FA.

#### Step-by-Step Instructions

1. **Navigate to the project root** (this repo's clone):

   ```bash
   cd <path-to-your-clone>
   ```

2. **Clone the GoogleFindMyTools repository** (if not already cloned):

   ```bash
   # Check if already cloned
   if [ ! -d "GoogleFindMyTools" ]; then
       git clone https://github.com/leonboe1/GoogleFindMyTools.git
   fi
   ```

   **Note**: This clones the authentication library **locally** (not in Docker). The Docker container has its own copy that gets cloned during the build.

3. **Install Python dependencies** (one-time setup):

   ```bash
   pip3 install -r GoogleFindMyTools/requirements.txt
   ```

   This installs:

   - selenium
   - undetected-chromedriver
   - gpsoauth
   - requests
   - beautifulsoup4
   - pyscrypt
   - cryptography

4. **Run the authentication script**:

   ```bash
   cd GoogleFindMyTools
   python3 main.py
   ```

5. **Follow the on-screen instructions**:

   - Press **Enter** when prompted
   - Chrome will open automatically
   - Log in to your Google account
   - Grant permissions to the application
   - Complete any 2FA if enabled
   - Wait for the script to complete (you'll see a success message)

6. **Copy the authentication file to the Docker volume**:

   The `auth_data/` folder is already exposed as a Docker volume, making it easy to copy files:

   ```bash
   # Copy secrets.json to the Docker volume
   cp Auth/secrets.json ../auth_data/

   # Verify the file was copied
   ls -la ../auth_data/secrets.json
   ```

   **Alternative**: You can also copy the file using your file manager:

   - Source: `GoogleFindMyTools/Auth/secrets.json`
   - Destination: `auth_data/secrets.json`

7. **Return to the project root**:

   ```bash
   cd ..
   ```

8. **Start the service**:
   ```bash
   docker compose up -d
   ```

#### Advantages of Method 1

✅ Uses your system's Chrome browser (full GUI)  
✅ Supports all authentication flows (CAPTCHA, 2FA, etc.)  
✅ Easier to troubleshoot if issues occur  
✅ Can see exactly what's happening during authentication  
✅ More reliable for complex Google accounts

---

### Method 2: Authenticate Inside Docker (Advanced)

This method runs authentication in a headless browser inside the Docker container. It's more automated but has limitations.

#### Step-by-Step Instructions

1. **Build the Docker image**:

   ```bash
   docker compose build
   ```

2. **Run authentication in the container**:

   ```bash
   docker compose run --rm -w /app/GoogleFindMyTools find-my-device-rest-api python main.py
   ```

3. **Follow the on-screen instructions**:

   - Press **Enter** when prompted
   - The script will run in headless mode (no visible browser)
   - Wait for authentication to complete

4. **Start the service**:
   ```bash
   docker compose up -d
   ```

#### Limitations of Method 2

⚠️ Runs in headless mode (no visible browser)  
⚠️ May not support CAPTCHA challenges  
⚠️ May have issues with advanced 2FA methods  
⚠️ Harder to troubleshoot if authentication fails  
⚠️ Some Google accounts may block headless browsers

**Recommendation**: If Method 2 fails, use Method 1 instead.

---

### Method 3: Authenticate via Browser (VNC) - No Local Chrome Needed

This method runs a **real, visible** Chrome window inside the container (not
headless), and streams it to any browser via noVNC - so you get full CAPTCHA/2FA
support like Method 1, without installing anything locally or copying
`secrets.json` around. Works whether the container is running on your Mac, a NAS,
or anywhere else you can reach over the network.

#### Step-by-Step Instructions

1. **Start the container** (it runs fine with no `secrets.json` yet):

   ```bash
   docker compose up -d
   ```

2. **Start an authentication session**:

   ```bash
   curl -X POST http://localhost:8000/auth/vnc/start
   ```

   Response:

   ```json
   {
     "vnc_url": "http://localhost:6080/vnc.html?autoconnect=true&password=aB3xY9kQ",
     "password": "aB3xY9kQ",
     "novnc_port": 6080,
     "expires_in_seconds": 600
   }
   ```

   The password is generated fresh for this one session - it isn't logged or
   stored anywhere, so copy it from the response now.

3. **Open `vnc_url` in a browser** (replace `localhost` with the container's real
   IP/hostname if you're not on the same machine). You'll land straight in a live
   view of the Chrome window running inside the container, already on Google's
   login page.

4. **Log in normally** - click, type, solve any CAPTCHA, complete 2FA - exactly
   as if Chrome were running on your own screen.

5. **Check progress**:

   ```bash
   curl http://localhost:8000/auth/vnc/status
   ```

   `state` moves from `running` to `succeeded` (or `failed`, with a reason in
   `error`) once you finish. On success, `secrets.json` has been written, the VNC
   session/Chrome window are torn down automatically, and - unlike Methods 1 and
   2 - **the already-running service picks it up immediately, no restart
   needed**: if it started without valid credentials, it re-initializes itself
   right after a successful login and starts fetching devices/locations. `/health`
   should flip from `503 unhealthy` to `200 healthy` within a second or two of
   `state` becoming `succeeded`.

   (If the service was already authenticated before you started this session -
   e.g. you're just re-confirming access - it's left alone: nothing gets
   restarted or re-initialized, since it didn't need to be.)

If you close the browser tab or never finish logging in, the session tears itself
down automatically after `expires_in_seconds` (10 minutes) - or stop it explicitly:

```bash
curl -X POST http://localhost:8000/auth/vnc/stop
```

#### Security Note

Anyone who can reach `/auth/vnc/start` on the network can start a session and see
the returned password - and while a session is running, that password gates a live
browser someone else could also connect to. This fits the project's existing
"local network only, no auth" model (see [Security Considerations](README.md#security-considerations)),
but don't expose port 6080 (or 8000) beyond your local network.

---

## Docker Compose Configuration for auth_data Volume

The `docker-compose.yml` file already mounts `secrets.json` as a
single file (not the whole `auth_data` folder - the container needs the rest
of the `Auth/` directory's Python modules untouched), making it easy to copy
the `secrets.json` file in:

```yaml
services:
  find-my-device-rest-api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: find-my-device-rest-api
    ports:
      - "8000:8000"
      - "6080:6080" # noVNC web UI (in-browser auth)
    volumes:
      # Mount only the secrets.json file, not the whole Auth directory
      - ./auth_data/secrets.json:/app/GoogleFindMyTools/Auth/secrets.json
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=INFO
    restart: unless-stopped
    networks:
      - findmy-network

networks:
  findmy-network:
    driver: bridge
```

### How the Volume Works

1. **Host Path**: `./auth_data/secrets.json`
2. **Container Path**: `/app/GoogleFindMyTools/Auth/secrets.json`
3. **Bidirectional**: Changes on either side (e.g. a fresh login via Method 3) are visible on the other

**Note**: the host file must exist *before* the first `docker compose up`
(`touch auth_data/secrets.json` if you don't have one yet) - Docker creates an
empty *directory* at that path instead if the file doesn't already exist,
which breaks authentication.

### Easy File Copying

Because the file is exposed, you can copy `secrets.json` in multiple ways:

**Option 1: Command Line**

```bash
cp GoogleFindMyTools/Auth/secrets.json auth_data/
```

**Option 2: File Manager (Finder on Mac)**

- Navigate to the `auth_data/` folder
- Drag and drop `secrets.json` from `GoogleFindMyTools/Auth/`

**Option 3: Using Docker Compose**

```bash
# The volume is automatically mounted when you start the service
docker compose up -d

# The container can now read secrets.json from /app/GoogleFindMyTools/Auth/secrets.json
```

### Verifying the Volume

Check that the file is accessible:

```bash
# From your Mac
ls -la auth_data/secrets.json

# From inside the container
docker compose exec find-my-device-rest-api ls -la /app/GoogleFindMyTools/Auth/secrets.json
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. "ModuleNotFoundError" when running outside Docker

**Problem**: Python dependencies are not installed.

**Solution**:

```bash
pip3 install -r GoogleFindMyTools/requirements.txt
```

Or install packages individually:

```bash
pip3 install selenium undetected-chromedriver gpsoauth requests beautifulsoup4 pyscrypt cryptography
```

---

#### 2. Chrome/Chromium not found

**Problem**: Chrome or Chromium is not installed or not in PATH.

**Solution**:

- **macOS**: Install Chrome from https://www.google.com/chrome/
- **Linux**: `sudo apt-get install chromium-browser`
- **Windows**: Install Chrome from https://www.google.com/chrome/

Verify installation:

```bash
# macOS
which google-chrome
# or
which chromium

# Linux
which chromium-browser
```

---

#### 3. Authentication completes but secrets.json not created

**Problem**: File permissions or script error.

**Solution**:

1. Check if the file exists:

   ```bash
   ls -la GoogleFindMyTools/Auth/secrets.json
   ```

2. Check for error messages in the terminal output

3. Ensure you have write permissions:

   ```bash
   chmod +w GoogleFindMyTools/Auth/
   ```

4. Try running the script again

---

#### 4. "Your encryption data is locked on your device"

**Problem**: Find My Device offline tracking is not enabled.

**Solution**:

1. Login to an Android device with your Google Account
2. Go to **Settings** > **Google** > **All Services** > **Find My Device**
3. Enable **"Find your offline devices"**
4. If the option is not available, install the **Find My Device** app from Play Store
5. Try authentication again

---

#### 5. Authentication fails in Docker (headless mode)

**Problem**: Headless browser doesn't support your authentication flow.

**Solution**: Use **Method 1** (authenticate outside Docker) instead. This is the most common issue and Method 1 resolves it.

---

#### 6. "ChromeDriver failed" or "Status code was: -5"

**Problem**: ChromeDriver compatibility issue in Docker.

**Solution**: Use **Method 1** (authenticate outside Docker). The headless ChromeDriver in Docker may have compatibility issues with certain Google account configurations.

---

#### 7. CAPTCHA appears during authentication

**Problem**: Google requires CAPTCHA verification.

**Solution**:

- If using **Method 2** (Docker): Switch to **Method 1** - headless browsers cannot solve CAPTCHAs
- If using **Method 1**: Complete the CAPTCHA in the Chrome window that opens

---

## Verifying Authentication

After authentication, verify that the secrets file exists:

```bash
# Check if secrets.json exists
ls -la auth_data/secrets.json

# Check file size (should be > 0 bytes)
du -h auth_data/secrets.json
```

The file should contain JSON data with authentication tokens. **Do not share this file** as it contains sensitive credentials.

---

## Security Notes

🔒 **Important Security Information**:

- The `secrets.json` file contains sensitive authentication data
- Keep this file secure and never commit it to version control
- The file is already in `.gitignore` to prevent accidental commits
- If compromised, revoke access in your Google Account settings
- The authentication persists until you revoke it or change your Google password

---

## Re-authentication

You may need to re-authenticate if:

- You change your Google account password
- You revoke access in Google Account settings
- The authentication token expires (rare)
- You delete the `secrets.json` file

To re-authenticate, simply run the authentication process again using either method.

---

## Next Steps

After successful authentication:

1. **Start the REST API service**:

   ```bash
   docker compose up -d
   ```

2. **Verify the service is running**:

   ```bash
   curl http://localhost:8000/health
   ```

3. **Test the API**:

   ```bash
   curl http://localhost:8000/api/v1/devices
   ```

4. **View API documentation**:

   ```bash
   open http://localhost:8000/docs
   ```

---

## Getting Help

If you continue to have authentication issues:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Review the logs: `docker compose logs -f find-my-device-rest-api`
3. Try Method 1 if you were using Method 2
4. Ensure Find My Device is enabled on your Google account
5. Check that you have an Android device associated with your account

For more information, see:

- [Main README](README.md)
- [GoogleFindMyTools Repository](https://github.com/leonboe1/GoogleFindMyTools)
