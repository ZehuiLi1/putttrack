# nRF54L15 Tag Pickup V0 MCU shadow mode

## Status — 2026-09-05

Firmware candidate `0.1.18` ports the frozen stationary-start Pickup V0
evaluator to C and runs it on the nRF54L15 only when explicitly requested. It
is a **build-only/software pass** until the signed image is test-booted on the
assembled Ball. Every result contains `authority=false`; it cannot change a
score, invalidate a turn, assign a hole, or enter System OFF.

This is intentionally narrower than the planned PG-DH-HSMM recognizer. The
repository does not yet contain independently validated per-frame emission
coefficients for the six persistent states. Shipping placeholder coefficients
would not be a meaningful MCU test. Pickup V0 is the only frozen semantic path
that can currently be ported without changing the research hypothesis.

## Implemented vertical slice

```text
encrypted SMP command 24
    -> verify active 50 Hz dual-IMU path and >=1 s retained history
    -> bind generation + device monotonic GO timestamp
    -> user performs one stationary-start action
encrypted SMP command 25
    -> copy a bounded history snapshot
    -> run the frozen V0 C kernel on the nRF54L15
    -> return decision, reason/rule masks, features and runtime_us
    -> authority=false
```

The C kernel implements the same baseline, onset, propagated-up vertical
impulse, gyro mean, axis-consistency and clipping checks as
`src/putttrack/motion/pickup_v0.py`. A read before enough post-GO evidence is
available returns `PENDING`; corrupt, discontinuous, unhealthy, nonstationary
or clipped evidence fails closed to `UNKNOWN`.

The detector response pins SHA-256:

```text
62c82c1a313f70912a5bb6c2f53c635fe179c537cdb3738dbc5d2a347050c8ad
```

Unit tests fail if the embedded hash or decision thresholds diverge from
`configs/research/pickup_detector_v0.json`.

## Evidence completed before physical installation

- Native C compiles with C11 warnings-as-errors.
- All 62 supported repository precision episodes produce the same final
  decision as the Python evaluator.
- For non-clipped evaluable episodes, positive vertical impulse, mean gyro and
  axis consistency match Python to the parity-test tolerance.
- Early live evaluation remains `PENDING` rather than becoming a false
  negative.
- The host parser rejects malformed decisions, invalid hashes and any
  `authority=true` result.
- The signed NFC/OTA `0.1.18` candidate builds successfully with NCS v3.4.0.

Build measurements compared with the confirmed `0.1.17` NFC image:

| ELF section | `0.1.17` | `0.1.18` candidate | Delta |
|---|---:|---:|---:|
| text | 198,556 B | 204,688 B | +6,132 B |
| data | 2,900 B | 2,900 B | 0 B |
| bss | 208,037 B | 221,114 B | +13,077 B |

The Zephyr link report is 207,592 B Flash of 696,176 B (29.82%) and 224,012 B
RAM of 256 KiB (85.45%). The extra RAM is a bounded 272-sample evaluation
snapshot. This is acceptable for the physical shadow experiment but is not a
commitment to the final streaming recognizer; V1 should use an incremental
feature state rather than add another full window.

Signed application SHA-256:

```text
4a131e62fc9642782ed10a1d72e38a8beb32d99a312c98e3173a896e374c2cdd
```

Local artifact:

```text
build/nrf54l15-tag-nfc-shadow-v0.1.18/nrf54l15_tag_app/zephyr/zephyr.signed.bin
```

## Physical test gate

Reconnect the XIAO nRF52840 HCI bridge, then upload `0.1.18` as an unconfirmed
MCUboot test image. Do not confirm it until identity, sensors, NFC, low-power
wake and the two shadow trials below pass.

First leave the Ball stationary after GO:

```bash
python tools/test_tag_pickup_shadow.py \
  --expected-device-id f383571202836e6f \
  --expect NOT_PICKUP
```

Then repeat and pick the stationary Ball up naturally after GO:

```bash
python tools/test_tag_pickup_shadow.py \
  --expected-device-id f383571202836e6f \
  --expect PICKUP_SUSPECTED
```

The tool locks the full encrypted device identity, selects `research`, waits
for a stationary baseline, arms the device-side GO marker, validates detector
hash/generation/authority, prints the MCU features and restores `auto` even
after most failures.

Record at least ten pickup and ten stationary/no-lift trials before deciding
whether runtime and repeatability justify keeping this port. A successful
shadow test still does not authorize automatic turn invalidation; that requires
the independent date/operator/second-Ball/surface gate.
