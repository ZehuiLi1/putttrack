#!/usr/bin/env bash
set -euo pipefail

PROBE=""
FIRMWARE=""
CHIP="${CHIP:-nRF54L15}"
EXECUTE=0

usage() {
  echo "Usage: $0 --probe <VID:PID:SERIAL> --firmware <image.hex> [--yes]" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --probe) PROBE="${2:-}"; shift 2 ;;
    --firmware) FIRMWARE="${2:-}"; shift 2 ;;
    --yes) EXECUTE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

[ -n "$PROBE" ] || { echo "An explicit probe selector is required." >&2; exit 2; }
[ -n "$FIRMWARE" ] || { echo "A firmware path is required." >&2; exit 2; }
[ -f "$FIRMWARE" ] || { echo "Firmware not found: $FIRMWARE" >&2; exit 2; }
case "$FIRMWARE" in
  *.hex) ;;
  *) echo "Refusing non-HEX input for the first Tag flash: $FIRMWARE" >&2; exit 2 ;;
esac
PROBE_RS="$(command -v probe-rs || true)"
if [ -z "$PROBE_RS" ] && [ -x "$HOME/.cargo/bin/probe-rs" ]; then
  PROBE_RS="$HOME/.cargo/bin/probe-rs"
fi
[ -n "$PROBE_RS" ] || { echo "probe-rs is not installed." >&2; exit 2; }

CHIP_LIST="$("$PROBE_RS" chip list)"
if ! rg -qi "${CHIP}" <<<"$CHIP_LIST"; then
  echo "Target '$CHIP' was not found. Run daplink_preflight.sh and set CHIP to the exact listed name." >&2
  exit 3
fi

HASH="$(shasum -a 256 "$FIRMWARE" | awk '{print $1}')"
echo "Probe    : $PROBE"
echo "Chip     : $CHIP"
echo "Firmware : $FIRMWARE"
echo "SHA-256  : $HASH"
echo "Action   : program with read-back verification; no explicit mass erase/recover"
echo
echo "Command: probe-rs download --chip '$CHIP' --probe '$PROBE' --protocol swd --speed 1000 --binary-format hex --verify --reset '$FIRMWARE'"

if [ "$EXECUTE" -ne 1 ]; then
  echo "Dry run only. Add --yes after reviewing the target, image, hash, and wiring."
  exit 0
fi

"$PROBE_RS" download \
  --chip "$CHIP" \
  --probe "$PROBE" \
  --protocol swd \
  --speed 1000 \
  --binary-format hex \
  --verify \
  --reset \
  --non-interactive \
  "$FIRMWARE"
