#!/bin/bash
# Diagnostic script to check authentication setup

echo "=== Google Find My Device - Authentication Diagnostic ==="
echo ""

echo "1. Checking local auth_data directory..."
if [ -d "./auth_data" ]; then
    echo "   ✓ auth_data directory exists"
    ls -la ./auth_data/
else
    echo "   ✗ auth_data directory NOT found"
    echo "   Creating auth_data directory..."
    mkdir -p ./auth_data
fi

echo ""
echo "2. Checking for secrets.json..."
if [ -f "./auth_data/secrets.json" ]; then
    echo "   ✓ secrets.json exists"
    echo "   File size: $(wc -c < ./auth_data/secrets.json) bytes"
else
    echo "   ✗ secrets.json NOT found"
    echo ""
    echo "   ACTION REQUIRED:"
    echo "   You need to authenticate first before running the Docker container."
    echo ""
    echo "   Follow these steps:"
    echo "   1. On your Mac/PC, clone GoogleFindMyTools:"
    echo "      git clone https://github.com/leonboe1/GoogleFindMyTools.git"
    echo ""
    echo "   2. Install dependencies:"
    echo "      cd GoogleFindMyTools"
    echo "      pip3 install -r requirements.txt"
    echo ""
    echo "   3. Run authentication:"
    echo "      python3 main.py"
    echo ""
    echo "   4. Copy the secrets file:"
    echo "      cp Auth/secrets.json /path/to/find-my-device-rest-api/auth_data/"
    echo ""
    echo "   5. Upload auth_data/secrets.json to your Synology NAS"
    exit 1
fi

echo ""
echo "3. Checking Docker container (if running)..."
if docker ps | grep -q find-my-device-rest-api; then
    echo "   ✓ Container is running"
    echo ""
    echo "4. Checking secrets.json inside container..."
    if docker exec find-my-device-rest-api test -f /app/auth_data/secrets.json; then
        echo "   ✓ secrets.json is mounted in container"
        docker exec find-my-device-rest-api ls -lh /app/auth_data/secrets.json
    else
        echo "   ✗ secrets.json NOT found in container"
        echo "   The volume mount may not be working correctly"
    fi
else
    echo "   ℹ Container is not running"
fi

echo ""
echo "=== Diagnostic Complete ==="

