#!/usr/bin/env bash
set -euo pipefail

NCS_VERSION="${NCS_VERSION:-v3.4.0}"
NCS_DIR="${NCS_DIR:-/opt/nordic/ncs/v3.4.0}"
BOARD="${BOARD:-xiao_ble/nrf52840/sense}"
BUILD_DIR="${BUILD_DIR:-$PWD/build/xiao-nrf52840-hci-usb}"
NRFUTIL="${NRFUTIL:-$HOME/.local/bin/nrfutil}"

[ -x "$NRFUTIL" ] || {
  echo "nrfutil not found at $NRFUTIL" >&2
  exit 2
}
[ -d "$NCS_DIR/.west" ] || {
  echo "NCS workspace not found at $NCS_DIR" >&2
  exit 2
}

cd "$NCS_DIR"

"$NRFUTIL" sdk-manager toolchain launch \
  --ncs-version "$NCS_VERSION" \
  -- \
  west build -p always \
  -b "$BOARD" \
  zephyr/samples/bluetooth/hci_uart \
  -d "$BUILD_DIR" \
  -- \
  -DEXTRA_CONF_FILE=boards/nrf52840dongle_nrf52840.conf

UF2="$BUILD_DIR/hci_uart/zephyr/zephyr.uf2"
echo "Built XIAO USB HCI firmware: $UF2"
shasum -a 256 "$UF2"
