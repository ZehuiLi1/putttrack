# nRF54L15 embedded-motion one-hole demo

This is the first firmware path that runs a generic PuttTrack motion recogniser
on the Research Ball MCU. It is deliberately a **demo/research image**, not a
commercial-accuracy or scoring-authority release.

## What is reused unchanged

The app reuses the current `nrf54l15_tag_app` source at build time, including:

- ADXL367 low-power wake;
- BMI270 100 Hz sensor ODR and 50 Hz exported motion stream;
- 1024-sample raw history and SMP capture commands;
- sensor recovery / clipping counters;
- encrypted BLE and signed MCUboot OTA;
- optional NFC Type-2 service / System OFF experiment.

The build-local baseline copy only changes the human-readable firmware version
from `0.1.17` to `0.1.18`. The raw telemetry service remains byte-compatible.

## Embedded motion engine V0

The additive engine consumes the exact raw motion packet already produced every
20 ms. It maintains a 128-sample causal buffer and emits these persistent
states:

- `UNKNOWN`
- `STATIONARY`
- `ROLLING`
- `SETTLING`
- `CARRIED`
- `AIRBORNE`

Transient event bits include:

- `MOTION_ONSET`
- `PICKUP_SUSPECTED`
- `ROLLING_START`
- `SETTLED`
- `DROP_LANDING_CANDIDATE`
- `TEE_ARM_MARKER`

Stationary-start pickup uses the thresholds generated directly from
`configs/research/pickup_detector_v0.json`. `UNKNOWN` and clipping are preserved;
rolling pickup, impact subtype and collision subtype are **not** promoted to
commercial truth by this demo.

Regenerate/check the header:

```bash
python tools/generate_embedded_pickup_config.py
python tools/generate_embedded_pickup_config.py --check
```

## BLE Motion Evidence service

The proven raw service stays unchanged. The demo adds a separate encrypted
research service:

```text
service:        8f3a1100-6e7d-4b9a-a6e8-3f3f7d2c0001
motion evidence 8f3a1101-6e7d-4b9a-a6e8-3f3f7d2c0001  read + notify
```

The 28-byte little-endian packet is:

| Offset | Type | Meaning |
|---:|---|---|
| 0 | u8 | protocol version |
| 1 | u8 | persistent state |
| 2 | u16 | transient event bits |
| 4 | u32 | source motion sequence |
| 8 | u64 | source monotonic time, us |
| 16 | u16 | confidence, permille |
| 18 | u16 | quality bits |
| 20 | u32 | frozen pickup config SHA-256 prefix |
| 24 | u32 | local Tee-arm epoch |

The packet contains no player, hole or score rule.

## Tee behaviour

`build_motion_demo.sh` enables the existing NFC service by default. A completed
NDEF data read from a Tee PN532 increments the Tag's existing read counter. The
demo observes that counter and:

1. clears the embedded motion buffer;
2. increments `tee_arm_epoch`;
3. emits `TEE_ARM_MARKER`;
4. reuses the existing auto-wake path when the Ball was idle;
5. requires a new stationary baseline before high-confidence pickup logic.

For the first one-hole demo, the Edge should wait until the Ball reports
`STATIONARY` after the Tee read before showing green `READY`.

NFC remains identity/context evidence, not authentication or score authority.

## Cup behaviour

Do **not** put cup truth in the Ball. Keep the already implemented Edge policy:

```text
optical cup-entry edge
        +
PN532 Ball identity/presence within confirmation window
        +
active Ball / active Hole context
        -> cup.confirmed
```

Ball `AIRBORNE` / `DROP_LANDING_CANDIDATE` may be logged as supporting motion
evidence only.

## Build the signed physical demo

Use the same private signing key as the confirmed Tag installation:

```bash
SIGNING_KEY=/absolute/private/key.pem \
scripts/nrf54l15_tag/build_motion_demo.sh
```

Outputs are under:

```text
build/nrf54l15-tag-motion-demo/
```

The default build includes the NFC service needed for Tee testing. Disable NFC
only for isolated bench work:

```bash
PUTTTRACK_MOTION_DEMO_NFC=0 \
SIGNING_KEY=/absolute/private/key.pem \
scripts/nrf54l15_tag/build_motion_demo.sh
```

## Live monitor

After OTA/commissioning, connect to the Ball and run:

```bash
python tools/monitor_embedded_motion.py \
  --address <BLE-address> \
  --output runs/embedded-motion-demo.jsonl
```

Expected console examples:

```text
state=STATIONARY confidence=0.990 events=-
state=ROLLING    confidence=0.960 events=MOTION_ONSET,ROLLING_START
state=SETTLING   confidence=0.800 events=-
state=STATIONARY confidence=0.990 events=SETTLED
state=CARRIED    confidence=0.990 events=PICKUP_SUSPECTED
```

## First physical acceptance sequence

Do not tune thresholds during this smoke test. Record failures.

1. Ball untouched for at least 2 s -> `STATIONARY`.
2. Light manual roll -> `ROLLING`.
3. Natural slow-down -> `SETTLING` then `STATIONARY`.
4. Stationary pickup -> `PICKUP_SUSPECTED` / `CARRIED`.
5. Touch/rotate/short slide without lift -> must not emit pickup.
6. Repeat 20 roll/stop cycles and log every `UNKNOWN`/clip.
7. Read at Tee PN532 -> `TEE_ARM_MARKER`, then wait for `STATIONARY` before READY.
8. Run a provisional one-hole sequence: Tee -> stroke candidates -> Cup physical confirmation.

The purpose is to expose MCU/real-time failure modes. It is not to claim
Puttshack-equivalent accuracy from the first live run.

## Host gates

```bash
python tools/verify.py
python tools/generate_embedded_pickup_config.py --check
bash tools/test_embedded_motion_c.sh
```

CI also compiles both raw-motion and Tee-NFC variants against NCS v3.4.0.
