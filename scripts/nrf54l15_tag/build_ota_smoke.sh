#!/usr/bin/env bash
set -euo pipefail

NCS_VERSION="${NCS_VERSION:-v3.4.0}"
NCS_DIR="${NCS_DIR:-/opt/nordic/ncs/v3.4.0}"
BOARD="${BOARD:-nrf54l15tag/nrf54l15/cpuapp}"
BUILD_DIR="${BUILD_DIR:-$PWD/build/nrf54l15-tag-ota-smoke}"
NRFUTIL="${NRFUTIL:-$HOME/.local/bin/nrfutil}"
SIGNING_KEY="${SIGNING_KEY:-}"
VARIANT_CONF="${VARIANT_CONF:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
OTA_DIR="$REPO_DIR/firmware/nrf54l15_tag_ota"
APP_OVERLAY="$OTA_DIR/nrf54l15tag_ota.overlay"
MCUBOOT_OVERLAY="$OTA_DIR/mcuboot.overlay"
MCUBOOT_CONF="$OTA_DIR/mcuboot.conf"
TAG_BLE_CONF="$OTA_DIR/tag_ble.conf"

[ -x "$NRFUTIL" ] || {
  echo "nrfutil not found at $NRFUTIL" >&2
  exit 2
}
[ -d "$NCS_DIR/.west" ] || {
  echo "NCS workspace not found at $NCS_DIR" >&2
  exit 2
}
for required_file in "$APP_OVERLAY" "$MCUBOOT_OVERLAY" "$MCUBOOT_CONF" "$TAG_BLE_CONF"; do
  [ -f "$required_file" ] || {
    echo "Required OTA configuration not found: $required_file" >&2
    exit 2
  }
done

APP_CONF_FILES="overlay-bt.conf;$TAG_BLE_CONF"
if [ -n "$VARIANT_CONF" ]; then
  [ -f "$VARIANT_CONF" ] || {
    echo "Variant configuration not found: $VARIANT_CONF" >&2
    exit 2
  }
  APP_CONF_FILES="$APP_CONF_FILES;$VARIANT_CONF"
fi

SIGNING_ARGS=()
if [ -n "$SIGNING_KEY" ]; then
  [ -f "$SIGNING_KEY" ] || {
    echo "Signing key not found: $SIGNING_KEY" >&2
    exit 2
  }
  SIGNING_ARGS+=("-DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE=\"$SIGNING_KEY\"")
else
  echo "WARNING: SIGNING_KEY is unset; the insecure Nordic debug key will be used." >&2
  echo "This output must not be flashed or distributed." >&2
fi

cd "$NCS_DIR"

"$NRFUTIL" sdk-manager toolchain launch \
  --ncs-version "$NCS_VERSION" \
  -- \
  west build --sysbuild -p always \
  -b "$BOARD" \
  nrf/samples/dfu/smp_svr \
  -d "$BUILD_DIR" \
  -- \
  "-DEXTRA_CONF_FILE=$APP_CONF_FILES" \
  "-DDTC_OVERLAY_FILE=$APP_OVERLAY" \
  "-Dmcuboot_DTC_OVERLAY_FILE=$APP_OVERLAY;$MCUBOOT_OVERLAY" \
  "-Dmcuboot_EXTRA_CONF_FILE=$MCUBOOT_CONF" \
  -DSB_CONFIG_BOOTLOADER_MCUBOOT=y \
  "${SIGNING_ARGS[@]}"

"$NRFUTIL" sdk-manager toolchain launch \
  --ncs-version "$NCS_VERSION" \
  -- \
  python3 "$NCS_DIR/zephyr/scripts/build/mergehex.py" \
  -o "$BUILD_DIR/first_install.hex" \
  "$BUILD_DIR/mcuboot/zephyr/zephyr.hex" \
  "$BUILD_DIR/smp_svr/zephyr/zephyr.signed.hex"

echo "Built signed BLE OTA image: $BUILD_DIR/smp_svr/zephyr/zephyr.signed.bin"
echo "Built DFU package: $BUILD_DIR/dfu_application.zip"
echo "Built first-install image: $BUILD_DIR/first_install.hex"
shasum -a 256 \
  "$BUILD_DIR/smp_svr/zephyr/zephyr.signed.bin" \
  "$BUILD_DIR/dfu_application.zip" \
  "$BUILD_DIR/first_install.hex"
