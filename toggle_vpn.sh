#!/bin/bash
# Quick VPN toggle script for UniFi UCG Ultra
# This script checks the current VPN status and toggles it

# Configuration - modify these variables as needed
VPN_NAME=""  # Leave empty to use the first VPN found, or specify a name like "ExpressVPN"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/unifi_vpn_manager.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    print_error "Python script not found: $PYTHON_SCRIPT"
    exit 1
fi

# Build command arguments
CMD_ARGS="--action status"
if [ -n "$VPN_NAME" ]; then
    CMD_ARGS="$CMD_ARGS --vpn-name \"$VPN_NAME\""
fi

print_status "Checking current VPN status..."

# Get current status
if [ -n "$VPN_NAME" ]; then
    STATUS_OUTPUT=$(python3 "$PYTHON_SCRIPT" --action status --vpn-name "$VPN_NAME" 2>/dev/null)
else
    STATUS_OUTPUT=$(python3 "$PYTHON_SCRIPT" --action status 2>/dev/null)
fi

# Check if command was successful
if [ $? -ne 0 ]; then
    print_error "Failed to get VPN status. Check your configuration and network connection."
    exit 1
fi

# Parse JSON output to determine current status
if echo "$STATUS_OUTPUT" | grep -q '"error"'; then
    print_error "VPN client not found or error occurred:"
    echo "$STATUS_OUTPUT"
    exit 1
fi

# Check if VPN is currently enabled
if echo "$STATUS_OUTPUT" | grep -q '"enabled": true'; then
    CURRENT_STATUS="enabled"
elif echo "$STATUS_OUTPUT" | grep -q '"enabled": false'; then
    CURRENT_STATUS="disabled"
else
    # Handle multiple VPN clients case
    if echo "$STATUS_OUTPUT" | grep -q '"vpn_clients"'; then
        print_warning "Multiple VPN clients found. Using the first one or specify --vpn-name"
        if echo "$STATUS_OUTPUT" | head -20 | grep -q '"enabled": true'; then
            CURRENT_STATUS="enabled"
        else
            CURRENT_STATUS="disabled"
        fi
    else
        print_error "Could not determine VPN status from output:"
        echo "$STATUS_OUTPUT"
        exit 1
    fi
fi

# Toggle VPN based on current status
if [ "$CURRENT_STATUS" = "enabled" ]; then
    print_status "VPN is currently enabled. Pausing..."
    if [ -n "$VPN_NAME" ]; then
        python3 "$PYTHON_SCRIPT" --action pause --vpn-name "$VPN_NAME"
    else
        python3 "$PYTHON_SCRIPT" --action pause
    fi
    
    if [ $? -eq 0 ]; then
        print_status "VPN successfully paused!"
    else
        print_error "Failed to pause VPN"
        exit 1
    fi
    
elif [ "$CURRENT_STATUS" = "disabled" ]; then
    print_status "VPN is currently disabled. Resuming..."
    if [ -n "$VPN_NAME" ]; then
        python3 "$PYTHON_SCRIPT" --action resume --vpn-name "$VPN_NAME"
    else
        python3 "$PYTHON_SCRIPT" --action resume
    fi
    
    if [ $? -eq 0 ]; then
        print_status "VPN successfully resumed!"
    else
        print_error "Failed to resume VPN"
        exit 1
    fi
else
    print_error "Unknown VPN status: $CURRENT_STATUS"
    exit 1
fi

print_status "VPN toggle operation completed successfully!" 