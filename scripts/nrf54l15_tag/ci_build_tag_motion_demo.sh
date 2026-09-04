#!/usr/bin/env bash
set -euo pipefail

NCS_MANIFEST_REF="${NCS_MANIFEST_REF:-v3.4.0}"
NCS_REPO="${NCS_REPO:-https://github.com/nrfconnect/sdk-nrf.git}"
NCS_DIR="${NCS_DIR:-/tmp/ncs-v3.4.0}"
OUT_DIR="${OUT_DIR:-$PWD/build/ci-nrf54l15-tag-motion-demo}"
PUTTTRACK_ROOT="${PUTTTRACK_ROOT:-$PWD}"
BOARD="${BOARD:-nrf54l15tag/nrf54l15/cpuapp}"
APP_DIR="$PUTTTRACK_ROOT/firmware/nrf54l15_tag_app"
OTA_DIR="$PUTTTRACK_ROOT/firmware/nrf54l15_tag_ota"
APP_OVERLAY="$OTA_DIR/nrf54l15tag_ota.overlay"
MCUBOOT_OVERLAY="$OTA_DIR/mcuboot.overlay"
MCUBOOT_CONF="$OTA_DIR/mcuboot.conf"
CI_SIGNING_KEY="${CI_SIGNING_KEY:-/tmp/putttrack-ci-signing-key.pem}"

command -v west >/dev/null 2>&1 || {
  echo "west is required; run this inside Nordic's NCS toolchain container" >&2
  exit 2
}

if [ ! -d "$NCS_DIR/.west" ]; then
  rm -rf "$NCS_DIR"
  west init -m "$NCS_REPO" --mr "$NCS_MANIFEST_REF" "$NCS_DIR"
fi

pushd "$NCS_DIR" >/dev/null
west update --narrow -o=--depth=1
west zephyr-export

if [ ! -f "$CI_SIGNING_KEY" ]; then
  python3 bootloader/mcuboot/scripts/imgtool.py keygen \
    -t ecdsa-p256 -k "$CI_SIGNING_KEY"
fi

rm -rf "$OUT_DIR"
west build --sysbuild -p always \
  -b "$BOARD" \
  "$APP_DIR" \
  -d "$OUT_DIR" \
  -- \
  "-DDTC_OVERLAY_FILE=$APP_OVERLAY" \
  "-Dmcuboot_DTC_OVERLAY_FILE=$APP_OVERLAY;$MCUBOOT_OVERLAY" \
  "-Dmcuboot_EXTRA_CONF_FILE=$MCUBOOT_CONF" \
  -DSB_CONFIG_BOOTLOADER_MCUBOOT=y \
  "-DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE=\"$CI_SIGNING_KEY\""

popd >/dev/null

APP_BUILD="$OUT_DIR/nrf54l15_tag_app"
test -f "$APP_BUILD/zephyr/zephyr.elf"
test -f "$APP_BUILD/zephyr/zephyr.signed.bin"
test -f "$APP_BUILD/zephyr/.config"
grep -q '^CONFIG_PUTTTRACK_MOTION_DEMO_V0=y$' "$APP_BUILD/zephyr/.config"

echo "NCS target compile PASS"
echo "NCS ref : $NCS_MANIFEST_REF"
echo "Board   : $BOARD"
echo "Build   : $OUT_DIR"
echo "WARNING : the CI signing key is disposable and this image must never be flashed."

grep -E '^(CONFIG_PUTTTRACK_MOTION_DEMO_V0|CONFIG_MCUBOOT_IMGTOOL_SIGN_VERSION)=' \
  "$APP_BUILD/zephyr/.config"
if [ -f "$APP_BUILD/zephyr/zephyr.map" ]; then
  grep -E 'motion_demo_v0_(push|get_snapshot|init)' \
    "$APP_BUILD/zephyr/zephyr.map" | head -20 || true
fi
