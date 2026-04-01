#!/bin/sh
set -eu

if [ -z "${DEVICE_ID:-}" ]; then
  # Similar to simulator.py default: device-<random>
  DEVICE_ID="device-$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n' | cut -c1-6)"
  export DEVICE_ID
fi

# Keep env compatibility with the existing compose file.
if [ -n "${UPDATE_BASE_DIR:-}" ]; then
  export INSTALL_BASE="$UPDATE_BASE_DIR"
  export APP_LINK="${APP_LINK:-$INSTALL_BASE/unilog}"
fi

# Logging defaults
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export RUST_LOG="${RUST_LOG:-info}"
export OTA_UPDATER="${OTA_UPDATER:-rust}"

# Start the stats/registration simulator.

# Start the Rust OTA updater listener.
# /usr/local/bin/device-updater-rs listen &

python /app/simulator.py


