#!/bin/bash

# Test script for Google Find My Device REST API
# This script tests all API endpoints and displays the results

set -e

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
VERBOSE="${VERBOSE:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    
    case $status in
        "success")
            echo -e "${GREEN}✓${NC} $message"
            ;;
        "error")
            echo -e "${RED}✗${NC} $message"
            ;;
        "info")
            echo -e "${BLUE}ℹ${NC} $message"
            ;;
        "warning")
            echo -e "${YELLOW}⚠${NC} $message"
            ;;
    esac
}

# Function to make API request
api_request() {
    local endpoint=$1
    local description=$2
    
    echo ""
    print_status "info" "Testing: $description"
    echo "Endpoint: $API_URL$endpoint"
    
    response=$(curl -s -w "\n%{http_code}" "$API_URL$endpoint")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -eq 200 ]; then
        print_status "success" "HTTP $http_code - Success"
        if [ "$VERBOSE" = "true" ]; then
            echo "$body" | jq '.' 2>/dev/null || echo "$body"
        fi
        return 0
    else
        print_status "error" "HTTP $http_code - Failed"
        echo "$body"
        return 1
    fi
}

# Main test sequence
main() {
    echo "======================================"
    echo "Google Find My Device REST API Tests"
    echo "======================================"
    echo "API URL: $API_URL"
    echo ""
    
    # Test 1: Root endpoint
    api_request "/" "Root endpoint"
    
    # Test 2: Health check
    if api_request "/health" "Health check"; then
        print_status "success" "API service is healthy"
    else
        print_status "error" "API service is not healthy"
        exit 1
    fi
    
    # Test 3: List devices
    echo ""
    print_status "info" "Fetching device list..."
    devices_response=$(curl -s "$API_URL/api/v1/devices")
    
    if [ $? -eq 0 ]; then
        device_count=$(echo "$devices_response" | jq '. | length' 2>/dev/null || echo "0")
        print_status "success" "Found $device_count device(s)"
        
        if [ "$VERBOSE" = "true" ]; then
            echo "$devices_response" | jq '.'
        fi
        
        # Test 4: Get device details for each device
        if [ "$device_count" -gt 0 ]; then
            echo ""
            print_status "info" "Testing device detail endpoints..."
            
            device_ids=$(echo "$devices_response" | jq -r '.[].device_id' 2>/dev/null)
            
            for device_id in $device_ids; do
                device_name=$(echo "$devices_response" | jq -r ".[] | select(.device_id==\"$device_id\") | .name" 2>/dev/null)
                api_request "/api/v1/devices/$device_id" "Device detail: $device_name ($device_id)"
            done
        else
            print_status "warning" "No devices found to test detail endpoint"
        fi
    else
        print_status "error" "Failed to fetch device list"
        exit 1
    fi
    
    # Test 5: Test invalid device ID
    echo ""
    print_status "info" "Testing error handling with invalid device ID..."
    response=$(curl -s -w "\n%{http_code}" "$API_URL/api/v1/devices/invalid_device_id_12345")
    http_code=$(echo "$response" | tail -n1)
    
    if [ "$http_code" -eq 404 ]; then
        print_status "success" "Error handling works correctly (404 for invalid device)"
    else
        print_status "warning" "Expected 404 for invalid device, got $http_code"
    fi
    
    # Summary
    echo ""
    echo "======================================"
    echo "Test Summary"
    echo "======================================"
    print_status "success" "All critical tests passed"
    echo ""
    echo "API Documentation: $API_URL/docs"
    echo "Alternative Docs: $API_URL/redoc"
    echo ""
}

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    print_status "warning" "jq is not installed. JSON output will not be formatted."
    print_status "info" "Install jq for better output: apt-get install jq (Debian/Ubuntu) or brew install jq (macOS)"
    echo ""
fi

# Check if curl is installed
if ! command -v curl &> /dev/null; then
    print_status "error" "curl is not installed. Please install curl to run this test."
    exit 1
fi

# Run tests
main

exit 0

