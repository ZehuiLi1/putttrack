#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${TMPDIR:-/tmp}/putttrack-embedded-motion-test"
mkdir -p "$OUT"

cc -std=c11 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/firmware/nrf54l15_tag_motion_demo/src" \
  "$ROOT/firmware/nrf54l15_tag_motion_demo/src/motion_engine.c" \
  "$ROOT/tests_research/embedded_motion_c_harness.c" \
  -lm \
  -o "$OUT/embedded_motion_c_harness"

"$OUT/embedded_motion_c_harness"
