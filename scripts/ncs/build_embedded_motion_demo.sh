#!/usr/bin/env bash
set -euo pipefail

NCS_MANIFEST_REF="${NCS_MANIFEST_REF:-v3.4.0}"
NCS_REPO="${NCS_REPO:-https://github.com/nrfconnect/sdk-nrf.git}"
NCS_DIR="${NCS_DIR:-$PWD/.ncs-v3.4.0}"
BOARD="${BOARD:-nrf54l15tag/nrf54l15/cpuapp}"
OUT_DIR="${OUT_DIR:-$PWD/build/embedded-motion-demo}"
PUTTTRACK_ROOT="${PUTTTRACK_ROOT:-$PWD}"
APP="$PUTTTRACK_ROOT/firmware/nrf54l15_tag_motion_demo"
OTA="$PUTTTRACK_ROOT/firmware/nrf54l15_tag_ota"

command -v west >/dev/null 2>&1 || {
  echo "west is required; use Nordic's NCS v3.4.0 environment/container" >&2
  exit 2
}

if [ ! -d "$NCS_DIR/.west" ]; then
  rm -rf "$NCS_DIR"
  west init -m "$NCS_REPO" --mr "$NCS_MANIFEST_REF" "$NCS_DIR"
fi

pushd "$NCS_DIR" >/dev/null
west update --narrow -o=--depth=1
west zephyr-export
mkdir -p "$OUT_DIR"

build_variant() {
  local name="$1"
  local overlays="$2"
  local extra_conf="${3:-}"
  local args=(
    west build --sysbuild -p always
    -b "$BOARD"
    "$APP"
    -d "$OUT_DIR/$name"
    --
    "-DDTC_OVERLAY_FILE=$overlays"
  )
  if [[ -n "$extra_conf" ]]; then
    args+=("-Dnrf54l15_tag_motion_demo_EXTRA_CONF_FILE=$extra_conf")
  fi
  echo "==> ${name}"
  "${args[@]}"
}

build_variant raw_motion \
  "$OTA/nrf54l15tag_ota.overlay"

build_variant tee_nfc_motion \
  "$OTA/nrf54l15tag_ota.overlay;$OTA/nfc_service.overlay" \
  "$OTA/nfc_service.conf"

popd >/dev/null

echo "PASS: embedded motion demo compiles for raw and Tee-NFC variants"
