#!/usr/bin/env bash
set -euo pipefail

NCS_MANIFEST_REF="${NCS_MANIFEST_REF:-v3.0.2}"
NCS_REV="${NCS_REV:-89ba1294ac9b624e28271a5c71e99193ed4d92a4}"
NCS_REPO="${NCS_REPO:-https://github.com/nrfconnect/sdk-nrf.git}"
NCS_DIR="${NCS_DIR:-$PWD/.ncs-v3.0.2}"
BOARD="${BOARD:-nrf54l15dk/nrf54l15/cpuapp}"
OUT_DIR="${OUT_DIR:-$PWD/build/ncs-phase0}"
PUTTTRACK_ROOT="${PUTTTRACK_ROOT:-$PWD}"

command -v west >/dev/null 2>&1 || {
  echo "west is required. Use Nordic's v3.0.2 toolchain/container or an NCS v3.0.2 environment." >&2
  exit 2
}

if [ ! -d "$NCS_DIR/.west" ]; then
  rm -rf "$NCS_DIR"
  # west init expects a cloneable branch/tag for --mr. Use the release tag,
  # then verify the resulting manifest repository resolves to the exact
  # expected commit before any dependency update/build is allowed.
  west init -m "$NCS_REPO" --mr "$NCS_MANIFEST_REF" "$NCS_DIR"
fi

pushd "$NCS_DIR" >/dev/null
CURRENT_REV="$(git -C nrf rev-parse HEAD)"
if [ "$CURRENT_REV" != "$NCS_REV" ]; then
  echo "NCS checkout mismatch: expected $NCS_REV, got $CURRENT_REV" >&2
  exit 3
fi

west update --narrow -o=--depth=1
west zephyr-export
mkdir -p "$OUT_DIR"

west build --sysbuild -p always \
  -b "$BOARD" \
  nrf/samples/bluetooth/channel_sounding_ras_initiator \
  -d "$OUT_DIR/ras_initiator"

west build --sysbuild -p always \
  -b "$BOARD" \
  nrf/samples/bluetooth/channel_sounding_ras_reflector \
  -d "$OUT_DIR/ras_reflector"

west build -p always \
  -b "$BOARD" \
  "$PUTTTRACK_ROOT/firmware/phase0_cs/telemetry_smoke_app" \
  -d "$OUT_DIR/telemetry_smoke"

popd >/dev/null

cat <<EOF
Phase-0 source build PASS
NCS ref      : $NCS_MANIFEST_REF
NCS revision : $NCS_REV
Board        : $BOARD
Initiator    : $OUT_DIR/ras_initiator
Reflector    : $OUT_DIR/ras_reflector
Telemetry    : $OUT_DIR/telemetry_smoke

This proves official-DK source compatibility only. It is not a Bbo hardware/overlay/flash PASS.
EOF
