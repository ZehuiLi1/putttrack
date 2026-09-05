#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PUTTTRACK_EXTRA_CONF_FILE="$ROOT/firmware/nrf54l15_tag_ota/stroke_pickup_v1_nfc.conf"
export PUTTTRACK_EXTRA_DTC_OVERLAY_FILE="$ROOT/firmware/nrf54l15_tag_ota/nfc_service.overlay"
export BUILD_DIR="${BUILD_DIR:-$ROOT/build/nrf54l15-stroke-pickup-v1}"
python3 "$ROOT/tools/generate_stroke_pickup_config.py" --check
bash "$ROOT/scripts/nrf54l15_tag/build_tag_app.sh"
echo 'Research 0.1.19: build does not authorize install or image-confirm.'
echo 'Use the existing device signing key, signed application BIN, and MCUboot test/rollback.'
