#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

export BUILD_DIR="${BUILD_DIR:-$REPO_DIR/build/nrf54l15-tag-motion-demo}"
export PUTTTRACK_APP_DIR="$REPO_DIR/firmware/nrf54l15_tag_motion_demo"
export PUTTTRACK_APP_IMAGE_NAME="nrf54l15_tag_motion_demo"

# Tee integration is the default demo: a complete NDEF read resets/arms the
# embedded motion engine, but it never grants gameplay authority by itself.
if [[ "${PUTTTRACK_MOTION_DEMO_NFC:-1}" != "0" ]]; then
  export PUTTTRACK_EXTRA_CONF_FILE="$REPO_DIR/firmware/nrf54l15_tag_ota/nfc_service.conf"
  export PUTTTRACK_EXTRA_DTC_OVERLAY_FILE="$REPO_DIR/firmware/nrf54l15_tag_ota/nfc_service.overlay"
fi

exec "$SCRIPT_DIR/build_tag_app.sh"
