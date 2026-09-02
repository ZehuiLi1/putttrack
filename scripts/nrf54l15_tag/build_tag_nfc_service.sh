#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

export BUILD_DIR="${BUILD_DIR:-$REPO_DIR/build/nrf54l15-tag-nfc-service}"
export PUTTTRACK_EXTRA_CONF_FILE="$REPO_DIR/firmware/nrf54l15_tag_ota/nfc_service.conf"
export PUTTTRACK_EXTRA_DTC_OVERLAY_FILE="$REPO_DIR/firmware/nrf54l15_tag_ota/nfc_service.overlay"

exec "$SCRIPT_DIR/build_tag_app.sh"
