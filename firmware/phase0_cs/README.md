# Phase-0 Channel Sounding Source Firmware Scaffold

## Purpose

This directory contains the PuttTrack-owned telemetry boundary that should be added to a **pinned Nordic Channel Sounding source build** after the Bbo vendor images pass the zero-custom-code smoke test.

It is deliberately not a forked copy of the whole Nordic sample. The canonical Channel Sounding implementation remains the pinned nRF Connect SDK source; PuttTrack owns only the small instrumentation/scheduling layer needed for reproducible research.

## Files

- `putttrack_cs_telemetry.h/.c` — Zephyr-side structured telemetry helper.
- `integration_example.c` — small example showing how estimator results are handed to the helper; it is documentation/scaffold, not a standalone application.

## Required output

Each completed distance report should produce one machine-readable JSON line:

```json
{
  "source_device_id": "A",
  "source_boot_id": "boot-a1b2c3d4e5f60718",
  "source_monotonic_ns": 1050000000,
  "source_sequence": 2,
  "procedure_id": "cs-00000002",
  "antenna_path": 0,
  "distance_ifft_m": 1.008,
  "distance_phase_m": 1.001,
  "distance_rtt_m": 1.076,
  "rssi_dbm": -48,
  "quality": {
    "source": "putttrack_source_firmware_v1",
    "cs_quality": "ok"
  }
}
```

The helper serializes distance floats as fixed-point decimal text so the logging path does not require floating-point `printf` support.

## Integration order

1. Flash and verify vendor Bbo RAS Initiator/Reflector binaries.
2. Freeze an exact NCS/toolchain revision and Bbo board/overlay configuration.
3. Build the unmodified source sample first.
4. Add this telemetry helper.
5. Call `pt_cs_telemetry_init("A")` once after boot/runtime initialization.
6. After one complete range report has been calculated, call `pt_cs_telemetry_emit_range()` for each antenna path/report that should become a host observation.
7. Capture with `tools/capture_cs.py --anchor-id A ...`.
8. Require `capture_summary.json -> source_identity_complete: true` before timing/loss/reset analysis.

## Important timing semantics

`source_monotonic_ns` is derived from Zephyr monotonic uptime ticks and expressed in nanoseconds. It is a source-local monotonic time, **not UTC** and not proof of one-way host latency.

If a later research phase needs sub-tick acquisition timing, add a separately specified high-resolution timestamp field instead of silently changing this field's semantics.

## Device ID safety

The firmware emits a configured `source_device_id` such as `A`. The host capture CLI also receives `--anchor-id A`.

If those identities disagree, the capture path rejects the structured record instead of silently assigning measurements to the wrong Anchor.

## Boot ID

The helper creates a non-security random boot nonce once per MCU boot. It is used only to define the telemetry sequence domain. Security device identity and production keys are separate Architecture V1 concerns.

## Build status

The helper is a source scaffold against stable Zephyr timing/random/print APIs. It has **not** yet been built against the actual Bbo board target in this environment because the NCS/Bbo toolchain and hardware are not present here.

Do not mark Issue #1 source-firmware gate complete until:

- the pinned source sample builds for the real Bbo board/overlay;
- real serial output is accepted by `capture_cs.py`;
- boot ID changes across reset;
- sequence/timestamps are monotonic inside a boot;
- no unexpected reset occurs in the 1 m / 3 m stability run.

## SDK profile rule

Keep the first source baseline RAS-compatible with the vendor comparison. Evaluate Nordic IPT separately later; do not mix procedure families inside the first calibration dataset.

See `docs/hardware/bbo-nrf54l15dk/SOURCE_TELEMETRY_CONTRACT.md`.
