# Synology NAS Setup Guide

> This guide covers **building the image on the NAS itself** via Container
> Manager's "Project" feature. If you'd rather pull a pre-built private image
> through Portainer instead (faster, no build step on the NAS), see
> [RELEASING.md](RELEASING.md) and [`docker-compose.portainer.yml`](docker-compose.portainer.yml).

## ⚠️ Common Error: "EOFError: EOF when reading a line"

If you see this error in your Synology Container Manager logs:

```
EOFError: EOF when reading a line
File "/app/app/services/../../GoogleFindMyTools/Auth/auth_flow.py", line 17, in request_oauth_account_token_flow
input("[AuthFlow] Press Enter to continue...")
```

**This means the `secrets.json` authentication file is missing or not properly mounted.**

## 📋 Prerequisites

Before deploying to Synology NAS, you **MUST** authenticate on your Mac/PC first. The Docker container cannot perform interactive authentication.

## 🔧 Step-by-Step Setup

### Step 1: Authenticate on Your Computer (Mac/PC)

1. **Clone GoogleFindMyTools on your Mac/PC**:

   ```bash
   git clone https://github.com/leonboe1/GoogleFindMyTools.git
   cd GoogleFindMyTools
   ```

2. **Install Python dependencies**:

   ```bash
   pip3 install -r requirements.txt
   ```

3. **Run authentication**:

   ```bash
   python3 main.py
   ```

4. **Follow the prompts**:

   - Press Enter when prompted
   - Chrome will open automatically
   - Log in to your Google account
   - Grant permissions
   - Complete 2FA if enabled
   - Wait for "Authentication successful" message

5. **Verify secrets.json was created**:

   ```bash
   ls -lh Auth/secrets.json
   ```

   You should see a file that's several KB in size.

### Step 2: Prepare Files for Synology

1. **Copy the secrets file to the rest-api directory**:

   ```bash
   # From the GoogleFindMyTools directory
   mkdir -p ../rest-api/auth_data
   cp Auth/secrets.json ../rest-api/auth_data/
   ```

2. **Verify the file was copied**:
   ```bash
   ls -lh ../rest-api/auth_data/secrets.json
   ```

### Step 3: Upload to Synology NAS

#### Option A: Using File Station (GUI)

1. Open **File Station** on your Synology
2. Create directory structure:

   ```
   /docker/google-findmy-api/
   ├── rest-api/
   │   ├── auth_data/
   │   │   └── secrets.json    ← IMPORTANT!
   │   ├── app/
   │   ├── Dockerfile
   │   ├── docker-compose.yml
   │   └── ... (other files)
   ```

3. Upload the entire `rest-api` folder to `/docker/google-findmy-api/`

4. **CRITICAL**: Verify `secrets.json` is in the correct location:
   - Path should be: `/docker/google-findmy-api/rest-api/auth_data/secrets.json`
   - File size should be several KB (not empty)
   - **Important**: The docker-compose.yml mounts only the `secrets.json` file (not the entire `auth_data` directory) to preserve the Python modules in the Auth directory

#### Option B: Using SSH/SCP

1. **Enable SSH** on your Synology (Control Panel → Terminal & SNMP)

2. **Upload files via SCP**:

   ```bash
   # From your Mac/PC
   scp -r rest-api your-username@synology-ip:/volume1/docker/google-findmy-api/
   ```

3. **SSH into Synology and verify**:
   ```bash
   ssh your-username@synology-ip
   ls -lh /volume1/docker/google-findmy-api/rest-api/auth_data/secrets.json
   ```

### Step 4: Deploy on Synology

1. **Open Container Manager** on your Synology

2. **Go to "Project" tab**

3. **Click "Create"**

4. **Set project settings**:

   - Project Name: `google-findmy-api`
   - Path: `/docker/google-findmy-api/rest-api`
   - Source: `docker-compose.yml`

5. **Click "Build"** to create the container

6. **Wait for build to complete** (may take 5-10 minutes first time)

### Step 5: Verify Deployment

1. **Check container status**:

   - Container should show "Running" with green status
   - No restart loops

2. **Check logs** (click on container → "Log" tab):

   - Should see: `Authentication verified for user: your-email@gmail.com`
   - Should see: `Device service initialized successfully`
   - Should NOT see: `EOFError` or `input()` errors

3. **Test the API**:

   ```bash
   # From your Mac/PC or Synology SSH
   curl http://SYNOLOGY-IP:8000/health
   curl http://SYNOLOGY-IP:8000/api/v1/devices
   ```

4. **Open API docs in browser**:
   ```
   http://SYNOLOGY-IP:8000/docs
   ```

## 🔍 Troubleshooting

### Error: "EOFError: EOF when reading a line"

**Cause**: `secrets.json` file is missing or not mounted correctly.

**Solution**:

1. Verify `secrets.json` exists in `rest-api/auth_data/` on Synology
2. Check file is not empty: `ls -lh auth_data/secrets.json`
3. Verify volume mount in docker-compose.yml:
   ```yaml
   volumes:
     - ./auth_data:/app/auth_data
   ```
4. Rebuild container: Stop → Remove → Build again

### Error: "Authentication failed" or "Invalid credentials"

**Cause**: `secrets.json` is outdated or corrupted.

**Solution**:

1. Re-authenticate on your Mac/PC (Step 1)
2. Copy fresh `secrets.json` to Synology
3. Rebuild container

### Error: "Port 8000 already in use"

**Cause**: Another service is using port 8000.

**Solution**:

1. Edit `docker-compose.yml` and change port:
   ```yaml
   ports:
     - "8001:8000" # Use 8001 instead
   ```
2. Rebuild container

### Container keeps restarting

**Cause**: Check logs for specific error.

**Solution**:

1. Click on container → "Log" tab
2. Look for error messages
3. Common issues:
   - Missing `secrets.json` → Follow Step 1-3 again
   - Port conflict → Change port in docker-compose.yml
   - Memory limit → Increase container memory in Synology

### Location updates not working

**Cause**: This should work now with the async fix.

**Solution**:

1. Check logs for "Updated location for device..." messages
2. Wait 30 seconds after startup for first update
3. If still not working, check network connectivity
4. Verify FCM patch was applied (logs should show no event loop errors)

## 📝 Diagnostic Script

Run this script to check your setup:

```bash
cd /volume1/docker/google-findmy-api/rest-api
bash check_auth.sh
```

This will verify:

- ✓ auth_data directory exists
- ✓ secrets.json file exists and has content
- ✓ Docker container is running
- ✓ secrets.json is mounted inside container

## 🎯 Quick Checklist

Before deploying to Synology, verify:

- [ ] Authenticated on Mac/PC using `python3 main.py`
- [ ] `secrets.json` file exists and is not empty
- [ ] Copied `secrets.json` to `rest-api/auth_data/`
- [ ] Uploaded entire `rest-api` folder to Synology
- [ ] Verified file path: `/docker/google-findmy-api/rest-api/auth_data/secrets.json`
- [ ] Built container in Container Manager
- [ ] Container shows "Running" status
- [ ] Logs show "Authentication verified"
- [ ] API responds to health check

## 🚀 Success Indicators

When everything is working correctly, you should see:

**In Container Logs**:

```
INFO - Starting GoogleFindMyTools REST API Service...
INFO - Authentication verified for user: your-email@gmail.com
INFO - Device service initialized successfully
INFO - Background location updater started
INFO - Starting background location update cycle...
INFO - Updated location for device Device-Name
```

**API Response**:

```bash
$ curl http://SYNOLOGY-IP:8000/health
{"status":"healthy","message":"Service is running normally"}

$ curl http://SYNOLOGY-IP:8000/api/v1/devices
[
  {
    "device_id": "...",
    "name": "My Device",
    "device_type": "SPOT_DEVICE",
    "last_seen": "2025-10-31T10:30:00",
    "status": "ACTIVE"
  }
]
```

## 📞 Still Having Issues?

If you've followed all steps and still have problems:

1. Run the diagnostic script: `bash check_auth.sh`
2. Check container logs for specific errors
3. Verify network connectivity from Synology to Google APIs
4. Try rebuilding container with `--no-cache` option
5. Check Synology DSM version (should be DSM 7.0+)

The most common issue is missing or incorrectly placed `secrets.json` file. Double-check this first!
