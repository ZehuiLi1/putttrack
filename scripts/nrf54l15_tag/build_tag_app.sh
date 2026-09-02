#!/usr/bin/env bash
set -euo pipefail

NCS_VERSION="${NCS_VERSION:-v3.4.0}"
NCS_DIR="${NCS_DIR:-/opt/nordic/ncs/v3.4.0}"
BOARD="${BOARD:-nrf54l15tag/nrf54l15/cpuapp}"
BUILD_DIR="${BUILD_DIR:-$PWD/build/nrf54l15-tag-app}"
NRFUTIL="${NRFUTIL:-$HOME/.local/bin/nrfutil}"
SIGNING_KEY="${SIGNING_KEY:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [[ "$BUILD_DIR" != /* ]]; then
  BUILD_DIR="$REPO_DIR/$BUILD_DIR"
fi
APP_DIR="$REPO_DIR/firmware/nrf54l15_tag_app"
APP_IMAGE_NAME="nrf54l15_tag_app"
OTA_DIR="$REPO_DIR/firmware/nrf54l15_tag_ota"
APP_OVERLAY="$OTA_DIR/nrf54l15tag_ota.overlay"
MCUBOOT_OVERLAY="$OTA_DIR/mcuboot.overlay"
MCUBOOT_CONF="$OTA_DIR/mcuboot.conf"
PUTTTRACK_EXTRA_CONF_FILE="${PUTTTRACK_EXTRA_CONF_FILE:-}"
PUTTTRACK_EXTRA_DTC_OVERLAY_FILE="${PUTTTRACK_EXTRA_DTC_OVERLAY_FILE:-}"

[ -x "$NRFUTIL" ] || {
  echo "nrfutil not found at $NRFUTIL" >&2
  exit 2
}
[ -d "$NCS_DIR/.west" ] || {
  echo "NCS workspace not found at $NCS_DIR" >&2
  exit 2
}
for required_file in "$APP_DIR/CMakeLists.txt" "$APP_DIR/prj.conf" \
  "$APP_OVERLAY" "$MCUBOOT_OVERLAY" "$MCUBOOT_CONF"; do
  [ -f "$required_file" ] || {
    echo "Required file not found: $required_file" >&2
    exit 2
  }
done
if [[ -n "$PUTTTRACK_EXTRA_CONF_FILE" && ! -f "$PUTTTRACK_EXTRA_CONF_FILE" ]]; then
  echo "Extra application config not found: $PUTTTRACK_EXTRA_CONF_FILE" >&2
  exit 2
fi
if [[ -n "$PUTTTRACK_EXTRA_DTC_OVERLAY_FILE" && ! -f "$PUTTTRACK_EXTRA_DTC_OVERLAY_FILE" ]]; then
  echo "Extra devicetree overlay not found: $PUTTTRACK_EXTRA_DTC_OVERLAY_FILE" >&2
  exit 2
fi
[ -n "$SIGNING_KEY" ] || {
  echo "SIGNING_KEY is required for the physical Tag application." >&2
  exit 2
}
[ -f "$SIGNING_KEY" ] || {
  echo "Signing key not found: $SIGNING_KEY" >&2
  exit 2
}

cd "$NCS_DIR"

APP_OVERLAYS="$APP_OVERLAY"
MCUBOOT_OVERLAYS="$APP_OVERLAY;$MCUBOOT_OVERLAY"
BUILD_CMAKE_ARGS=(
  "-DDTC_OVERLAY_FILE=$APP_OVERLAYS"
  "-Dmcuboot_DTC_OVERLAY_FILE=$MCUBOOT_OVERLAYS"
  "-Dmcuboot_EXTRA_CONF_FILE=$MCUBOOT_CONF"
  -DSB_CONFIG_BOOTLOADER_MCUBOOT=y
  "-DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE=\"$SIGNING_KEY\""
)
if [[ -n "$PUTTTRACK_EXTRA_DTC_OVERLAY_FILE" ]]; then
  APP_OVERLAYS="$APP_OVERLAYS;$PUTTTRACK_EXTRA_DTC_OVERLAY_FILE"
  MCUBOOT_OVERLAYS="$MCUBOOT_OVERLAYS;$PUTTTRACK_EXTRA_DTC_OVERLAY_FILE"
  BUILD_CMAKE_ARGS[0]="-DDTC_OVERLAY_FILE=$APP_OVERLAYS"
  BUILD_CMAKE_ARGS[1]="-Dmcuboot_DTC_OVERLAY_FILE=$MCUBOOT_OVERLAYS"
fi
if [[ -n "$PUTTTRACK_EXTRA_CONF_FILE" ]]; then
  BUILD_CMAKE_ARGS+=(
    "-Dnrf54l15_tag_app_EXTRA_CONF_FILE=$PUTTTRACK_EXTRA_CONF_FILE"
  )
fi

"$NRFUTIL" sdk-manager toolchain launch \
  --ncs-version "$NCS_VERSION" \
  -- \
  west build --sysbuild -p always \
  -b "$BOARD" \
  "$APP_DIR" \
  -d "$BUILD_DIR" \
  -- \
  "${BUILD_CMAKE_ARGS[@]}"

"$NRFUTIL" sdk-manager toolchain launch \
  --ncs-version "$NCS_VERSION" \
  -- \
  python3 "$NCS_DIR/zephyr/scripts/build/mergehex.py" \
  -o "$BUILD_DIR/first_install.hex" \
  "$BUILD_DIR/mcuboot/zephyr/zephyr.hex" \
  "$BUILD_DIR/$APP_IMAGE_NAME/zephyr/zephyr.signed.hex"

echo "Built signed BLE OTA image: $BUILD_DIR/$APP_IMAGE_NAME/zephyr/zephyr.signed.bin"
echo "Built first-install image: $BUILD_DIR/first_install.hex"
shasum -a 256 \
  "$BUILD_DIR/$APP_IMAGE_NAME/zephyr/zephyr.signed.bin" \
  "$BUILD_DIR/first_install.hex"
