#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
export BOARD="xiao_nrf54l15/nrf54l15/cpuapp"
export BUILD_DIR="${BUILD_DIR:-$REPO_DIR/build/xiao-sense-tag}"
export PUTTTRACK_CONF_FILE="$REPO_DIR/firmware/nrf54l15_tag_app/xiao_sense.conf"
export PUTTTRACK_APP_OVERLAY="$REPO_DIR/firmware/nrf54l15_tag_app/xiao_sense.overlay"
exec "$SCRIPT_DIR/build_tag_app.sh"
