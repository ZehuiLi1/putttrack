# Phase-0 Source Firmware Telemetry Contract

## Status

**Host contract ready; source-built firmware still requires a pinned NCS/Bbo build and real hardware verification.**

This document closes the gap between the vendor smoke-test log and the data identity required for timing, reset, loss and replay claims.

## 1. Two firmware profiles, two purposes

### Profile A — vendor RAS smoke image

Use the Bbo-supplied signed Initiator/Reflector images first to prove:

- serial boot/programming path;
- BLE connection / CS path;
- `Ranging data ready`;
- IFFT / phase-slope / RTT values;
- no obvious reset or board-level failure.

The vendor image does not emit a device acquisition timestamp, source-device identity, device boot domain or source sequence. `tools/capture_cs.py` therefore labels those values as host/capture/CLI fallbacks. **Never use that fallback log to claim true update latency, packet loss, ordering, reboot continuity or device-port identity.**

### Profile B — PuttTrack source-built RAS baseline

After Gate-0, build the Nordic RAS Initiator/Reflector workflow from a pinned NCS/toolchain/board configuration and add PuttTrack structured telemetry.

Each distance report must emit:

```json
{
  "source_device_id": "A",
  "source_boot_id": "boot-a1b2c3d4",
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

The host capture tool converts this into canonical `RangeObservation` while adding Edge receive time, run/experiment metadata, calibration/config versions and raw-line references.

## 2. Required source fields

### `source_device_id`

A stable experiment identity compiled/configured into the source firmware, such as `A`, `B`, `C`, `D` or `E` for the research Anchors.

Purpose:

- protect against USB/COM port swaps;
- make the source itself state which Anchor generated the record;
- allow the host to fail closed when firmware identity disagrees with the operator's `--anchor-id` argument.

This is an experiment/device label, not a production security credential. Production device authentication remains a separate Architecture V1 concern.

### `source_boot_id`

A new non-empty identifier generated once per MCU boot.

Purpose:

- distinguish sequence restart after reset from duplicate/corrupt packets;
- make `(source_device_id, source_boot_id, source_sequence)` an unambiguous source identity;
- expose reset events during long experiments.

It does not need to be a security credential. Device authentication/keys are a separate production security concern.

### `source_sequence`

Monotonically increasing unsigned record sequence inside one boot domain.

Rules:

- start at a documented value (recommended `1`);
- increment once for every emitted range record;
- never intentionally reuse within the same boot;
- reset only when `source_boot_id` changes.

### `source_monotonic_ns`

Monotonic device-local acquisition/report time represented in nanoseconds.

For the Phase-0 implementation, use a Zephyr monotonic uptime/tick source and convert ticks to nanoseconds. The numeric unit is nanoseconds even though the effective precision is limited by the configured Zephyr timer/tick source.

Do not interpret it as UTC/wall time.

### `procedure_id`

Identifier that ties estimator outputs to one completed Channel Sounding procedure/report. It can be generated from the same monotonic procedure counter used by the source telemetry layer.

## 3. Host behavior

`CsSerialParser` supports both:

- vendor human-readable RAS lines;
- PuttTrack structured JSON.

For structured telemetry it now preserves:

- `source_device_id` / `device_id`;
- `source_boot_id` / `boot_id`;
- `source_monotonic_ns` / `timestamp_ns`;
- `source_sequence` / `sequence`;
- procedure ID;
- antenna path;
- IFFT / phase / RTT / RSSI / quality.

`tools/capture_cs.py` uses device source identity when present. Vendor logs continue to use explicit capture/CLI fallbacks.

For source-built telemetry:

```text
firmware source_device_id != capture --anchor-id
        -> record rejected
        -> identity_mismatches incremented
        -> source_identity_complete = false
```

This is intentional fail-closed behavior. A real experiment should stop and correct the physical/port mapping rather than relabel measurements after the fact.

`capture_summary.json` reports:

- observed source device IDs;
- observed source boot IDs;
- number of records with device timestamp;
- number with device sequence;
- number with device boot ID;
- number with device source-device ID;
- identity mismatch count;
- `source_identity_complete`.

A run may be used for update-rate/loss/order/reset/device-assignment claims only when the relevant records have complete source identity.

## 4. Timing implementation guidance

Portable Phase-0 baseline:

```c
uint64_t source_monotonic_ns =
    k_ticks_to_ns_floor64((uint64_t)k_uptime_ticks());
```

This preserves monotonic source ordering with the timer/tick precision available in the build. If later CS timing research requires finer acquisition timing, add a separately calibrated high-resolution hardware-cycle timestamp rather than silently changing the semantics of `source_monotonic_ns`.

Keep both source and host time:

```text
source_monotonic_ns = when the device says it emitted/finished the measurement
edge_received_ns    = when capture host received the line
```

The difference is useful for diagnostics but is not a one-way latency measurement until clock-domain relationships are calibrated.

## 5. SDK/version policy

Do not mix SDK upgrades into the first reproducible baseline.

1. Reproduce the vendor path and record the exact vendor binaries/hashes.
2. Build a source RAS baseline with one pinned NCS/toolchain/board overlay and record the exact manifest.
3. Keep that profile unchanged through the first distance/orientation comparison.
4. Evaluate later NCS/CS features in a separate run/config identity.

As of the 2026 architecture review, Nordic's current NCS line also contains an Inline PCT Transfer (IPT) Channel Sounding sample. Nordic documents IPT as reducing setup/data-transfer latency and supporting higher PBR update rate because peer raw ranging data does not require a separate GATT transfer. The current sample is explicitly PBR-focused, single-antenna, and requires RAS or an equivalent return path for RTT.

Therefore:

- **RAS source baseline:** Phase-0/Phase-1 comparison authority;
- **IPT:** later performance/scalability research profile;
- do not silently compare RAS and IPT data as if the procedure configuration were identical.

## 6. Build metadata

A source-built run must record at minimum:

- PuttTrack git SHA;
- NCS version/tag/manifest revision;
- Zephyr/toolchain version;
- board target;
- Bbo overlay/config hash;
- Initiator firmware hash;
- Reflector firmware hash;
- `source_device_id` configuration;
- CS mode/submode/channel/procedure configuration;
- antenna path configuration;
- UART/log settings.

## 7. No-performance-claim rule

This contract and the checked-in structured fixture prove only that the data path preserves source identity.

They do **not** prove:

- Bbo firmware builds on the real board;
- Bbo ↔ Nordic Tag interoperability;
- range accuracy;
- true update rate;
- multi-ball scalability;
- energy/update;
- no-reset stability.

Those remain real-hardware gates in Issue #1.

## 8. Primary-source references

- Nordic nRF Connect SDK `cs_de` library and API (`include/bluetooth/cs_de.h`).
- Nordic RAS Initiator / RAS Reflector Channel Sounding samples.
- Nordic IPT Initiator / IPT Reflector samples for the later research profile.
- Zephyr Kernel Timing and Time Units APIs (`k_uptime_ticks`, `k_ticks_to_ns_floor64`).
- Zephyr random API used only for the non-security boot-domain nonce.

Use the exact pinned source revision in each experiment manifest rather than relying on a moving `main` branch.
