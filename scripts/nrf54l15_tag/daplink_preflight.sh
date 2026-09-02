#!/usr/bin/env bash
set -euo pipefail

PROBE_RS="$(command -v probe-rs || true)"
if [ -z "$PROBE_RS" ] && [ -x "$HOME/.cargo/bin/probe-rs" ]; then
  PROBE_RS="$HOME/.cargo/bin/probe-rs"
fi

if [ -z "$PROBE_RS" ]; then
  echo "probe-rs is not installed." >&2
  echo "Install a current probe-rs release, then rerun this read-only check." >&2
  exit 2
fi

echo "probe-rs version"
"$PROBE_RS" --version

echo
echo "Detected debug probes"
"$PROBE_RS" list

echo
echo "Matching nRF54L15 targets"
CHIP_LIST="$("$PROBE_RS" chip list)"
rg -i 'nrf54l15' <<<"$CHIP_LIST" || {
  echo "No nRF54L15 target is present in this probe-rs installation." >&2
  exit 3
}

echo
echo "Preflight is read-only. No target was attached, erased, or programmed."
