# Pinned NCS Phase-0 Build Baseline

## Purpose

Remove source/toolchain ambiguity before Bbo hardware arrives. This build gate verifies that the PuttTrack telemetry helper remains compatible with the same Nordic SDK generation as the vendor smoke image, without claiming Bbo board/overlay or RF validation.

## Pin

| Item | Value |
|---|---|
| nRF Connect SDK | `v3.0.2` |
| sdk-nrf commit | `89ba1294ac9b624e28271a5c71e99193ed4d92a4` |
| Zephyr line | NCS v3.0.2 manifest-controlled Zephyr |
| CI toolchain image | `ghcr.io/nrfconnect/sdk-nrf-toolchain:v3.0.2` |
| Official build target | `nrf54l15dk/nrf54l15/cpuapp` |
| Initiator | `samples/bluetooth/channel_sounding_ras_initiator` |
| Reflector | `samples/bluetooth/channel_sounding_ras_reflector` |

Nordic's v3.0.2 sample metadata explicitly lists `nrf54l15dk/nrf54l15/cpuapp` for both RAS Initiator and Reflector.

## Why official DK first

The Bbo package uses the Nordic DK board target plus vendor overlay/material, but the public PuttTrack repository intentionally does not redistribute the full vendor archive. Before physical hardware arrival, CI can prove:

1. official RAS Initiator source builds at the pinned revision;
2. official RAS Reflector source builds at the pinned revision;
3. PuttTrack's Zephyr telemetry helper itself compiles on the official nRF54L15 DK target.

It cannot prove:

- Bbo overlay correctness;
- Bbo UART/pin mapping;
- vendor serial bootloader behaviour;
- Bbo RF/antenna performance;
- Bbo flash success;
- Bbo <-> Tag interoperability.

Those stay in Issue #1.

## Reproducible build

Preferred environment: Nordic's matching toolchain container or an installed nRF Connect SDK v3.0.2 toolchain.

```bash
bash scripts/ncs/build_phase0_ras.sh
```

Environment overrides:

```text
NCS_REV
NCS_REPO
NCS_DIR
BOARD
OUT_DIR
PUTTTRACK_ROOT
```

Do not change the SDK revision while collecting the first controlled distance/orientation baseline.

## Bbo transition when boards arrive

1. verify actual vendor archive SHA-256;
2. extract/confirm the real overlay used for the board revision;
3. reproduce vendor smoke images first;
4. build official source RAS against the Bbo target/overlay;
5. record all source/config/toolchain hashes;
6. add PuttTrack telemetry helper;
7. flash and validate source identity/boot/sequence/time;
8. only then begin timing/accuracy claims.

A successful CI build in this document is a **source compatibility gate**, not a physical hardware gate.
