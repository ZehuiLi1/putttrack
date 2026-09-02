# nRF54L15 Tag motion baseline

## Physical result

On 2026-09-02, the physical nRF54L15 Tag, now running repository firmware `0.1.7`,
passed the first no-CS motion transport baseline through a Seeed XIAO nRF52840
Sense USB HCI adapter.

The verified stationary capture contained:

| Measurement | Result |
|---|---:|
| Samples | 170 |
| Source duration | 3.38 s |
| Observed source rate | 50.0 Hz |
| Sequence gaps | 0 |
| Valid ADXL367 + BMI270 records | 100% |
| BMI270 acceleration magnitude mean | 9.8101 m/s² |
| BMI270 acceleration magnitude standard deviation | 0.0211 m/s² |
| BMI270 gyro magnitude RMS | 0.0114 rad/s |
| ADXL367 / BMI270 acceleration / BMI270 gyro clip deltas | 0 / 0 / 0 |
| Provisional diagnostic | `STATIONARY_CANDIDATE` |

The hardware device ID remained stable across OTA/reboots while the boot ID
changed. Both sensors reported ready, sample error bits stayed zero and the
firmware health counter stayed zero.

The capture also recorded the actual sensor configuration exported by firmware:
50 Hz stream; ADXL367 100 Hz/±2g; BMI270 acceleration 100 Hz/±16g; and BMI270
gyroscope 100 Hz/±2000 dps. Clipping counters are per boot and are sampled both
before and after each labelled episode so the host can calculate episode-local
deltas.

Two later firmware `0.1.7` frozen-history repetitions extended the stationary
baseline from a short transport check to complete 20.48-second rings:

| Frozen stationary repetition | Samples / duration | Rate / gaps / validity | Accel stdev (m/s²) | Gyro RMS (rad/s) | Active / clipped samples |
|---|---:|---:|---:|---:|---:|
| Post-confirm reboot | 1024 / 20.4601 s | 49.9998 Hz / 0 / 100% | 0.01783 | 0.01370 | 0% / 0 |
| Post-handling rest | 1024 / 20.4600 s | 50.0000 Hz / 0 / 100% | 0.01521 | 0.00668 | 0% / 0 |
| Stable tilted orientation | 1024 / 20.4600 s | 50.0000 Hz / 0 / 100% | 0.01172 | 0.00434 | 0% / 0 |

All three passed `STATIONARY_CANDIDATE`. The tilted run retained a gravity-magnitude
mean of 9.8304 m/s², showing that the provisional norm-based stationary check is
not tied to the original flat orientation. Its canonical observation again
entered the one-hole runtime only as non-authoritative `motion.stationary`; the
hole remained `READY` and strokes remained zero.

## First clearly active physical window

A separately labelled continuous hand-motion window established the other end
of the initial diagnostic separation:

| Measurement | Result |
|---|---:|
| Samples / source duration | 502 / 10.02 s |
| Observed source rate / gaps / validity | 50.0 Hz / 0 / 100% |
| BMI270 acceleration magnitude standard deviation | 2.9514 m/s² |
| BMI270 acceleration magnitude maximum | 33.4070 m/s² |
| BMI270 gyro magnitude RMS / maximum | 4.0061 / 12.1787 rad/s |
| Jerk magnitude RMS / peak | 167.87 / 1289.62 m/s³ |
| ADXL367 / BMI270 acceleration / BMI270 gyro clip deltas | 17 / 0 / 0 |
| Provisional diagnostic | `ACTIVE_MOTION_CANDIDATE` |

The corresponding stationary values were approximately 0.0211 m/s²
acceleration standard deviation and 0.0114 rad/s gyro RMS. The current smoke
gate leaves a wide unclassified dead band between stationary and clearly
active data. It does not yet distinguish pickup, handling, impact, rolling or
settling.

Two earlier files labelled `pickup_carry` contained no measured motion. The
label-consistency check correctly rejects both instead of allowing their labels
to contaminate later threshold work. The accepted active window had ADXL367
clipping, as expected from its ±2g role, while the ±16g BMI270 retained the
full acceleration waveform.

## Natural pickup/carry with frozen history

Firmware `0.1.7` replaced timing-sensitive long SMP polling for labelled
episodes with an always-on 1024-sample history. Command 3 freezes all 20.48
seconds atomically; commands 4–19 retrieve immutable chunks. The host verifies
one capture ID, exact chunk order/bounds and continuous source sequences.

The first natural desk → hand → carry → desk episode passed:

| Measurement | Result |
|---|---:|
| Samples / duration | 1024 / 20.46 s |
| Source rate / gaps / validity | 50.0 Hz / 0 / 100% |
| First / last active offset | 4.08 / 7.80 s |
| Active sample fraction | 18.16% |
| BMI270 acceleration standard deviation / maximum | 1.5067 / 28.9826 m/s² |
| BMI270 gyro RMS / maximum | 1.7490 / 8.5000 rad/s |
| Frozen-window ADXL367 / BMI270 accel / gyro clip samples | 5 / 0 / 0 |
| Label consistency | `PASS` |
| Diagnostic | `ACTIVE_MOTION_CANDIDATE` |

This preserves about 4.08 seconds of pre-action rest and 12.66 seconds after
the last active sample. Its canonical observation entered the one-hole runtime
as non-authoritative `motion.active`; the hole remained `READY`, the audit
gained one decision and strokes remained zero.

## Ordinary handling false-positive control

A separate episode kept the PCB on the desk while the operator lightly touched
its edge or adjusted the cable. It produced acceleration standard deviation
`0.2351 m/s²`, gyro RMS `0.2268 rad/s`, no clipped samples and 18.07% active
samples. This is above stationary noise but below the deliberately wide active
gates (`0.5 m/s²` acceleration standard deviation or `0.25 rad/s` gyro RMS).

The result correctly remained `UNCLASSIFIED` with reason `motion_dead_band`;
the label-consistency check passed because handling may remain unclassified or
become generic active motion, but must never imply pickup or stroke semantics.
Its canonical observation was rejected by the one-hole candidate policy as an
unsupported state, remained non-authoritative and left the hole `READY` at zero
strokes.

A second, deliberately stronger desk-bound handling episode exercised the
opposite side of this control. It passed transport integrity with 1024 samples,
20.46 seconds, 50.0 Hz, zero sequence gaps and 100% valid records, but crossed
the generic activity gate:

| Labelled episode | Accel stdev (m/s²) | Gyro RMS (rad/s) | Active samples | Diagnostic |
|---|---:|---:|---:|---|
| Natural pickup/carry 1 | 1.5067 | 1.7490 | 18.16% | `ACTIVE_MOTION_CANDIDATE` |
| Natural pickup/carry 2 | 0.5535 | 1.1992 | 30.66% | `ACTIVE_MOTION_CANDIDATE` |
| Desk handling 1, light | 0.2351 | 0.2268 | 18.07% | `UNCLASSIFIED` |
| Desk handling 2, stronger | 1.1965 | 1.7831 | 37.79% | `ACTIVE_MOTION_CANDIDATE` |

The stronger handling record had active samples from 1.14–8.98 seconds, an
acceleration maximum of 31.0727 m/s², gyro maximum of 11.9200 rad/s and four
ADXL367 clipped records. Its status-counter delta was zero; the four values are
sample flags already present inside the frozen window. The canonical
observation was routed only as non-authoritative `motion.active`; the hole
remained `READY`, strokes remained zero and the decision was audited.

This is an important negative result: the pickup and handling distributions
already overlap in whole-window intensity. Generic activity is useful, but
acceleration/gyro magnitude alone cannot safely promote an episode to
`PICKED_UP`, `CARRIED`, `IMPACT_CANDIDATE` or a confirmed stroke. Those semantics
need temporal modelling plus independent tee/game/mechanical context and
held-out validation. The current firmware/host therefore continue to emit only
stationary, generic active or unclassified diagnostics.

## Why firmware 0.1.5 was necessary

The first ring-window build exposed a useful timing defect rather than hiding
it. Firmware `0.1.3` used the ADXL367 power-on default ODR and achieved only
about 12.8 Hz. Firmware `0.1.4` set the ADXL367/BMI270 ODR to 100 Hz but used a
relative 20 ms sleep, so processing time reduced the measured stream to about
44.4 Hz. Firmware `0.1.5` uses an absolute 20 ms deadline and measured exactly
50.0 Hz over the accepted run.

Firmware `0.1.6` retains that timing behavior and adds explicit ODR/range
reporting plus per-sensor clipping counters. A new 170-sample physical run and a
64-sample post-confirm/reboot run both measured 50 Hz with no sequence gaps or
clipping-counter increments.

The acceptance value comes from source monotonic timestamps, not configuration
intent or host arrival time.

## Capture paths

- GATT motion notifications carry a 56-byte binary record and are the intended
  continuously connected gateway path.
- Custom mcumgr group 64 command 2 returns the latest 64 binary records as a
  hex-encoded ring window. The host de-duplicates overlapping windows and checks
  source sequence/time continuity.
- Command 3 plus commands 4–19 freeze and retrieve the latest 1024 records. This
  is the default labelled-episode path because BLE retries cannot alter a frozen
  capture.
- Command 1 returns one low-rate snapshot for compatibility and diagnostics; it
  is not adequate for impact or rolling research.

Use:

```bash
python tools/capture_tag_smp.py \
  --mode frozen --label stationary \
  --output runs/tag-motion.jsonl
python tools/analyze_tag_capture.py runs/tag-motion.jsonl
```

Convert a validated window into the canonical diagnostic-only observation used
by the one-hole ingress:

```bash
python tools/analyze_tag_capture.py runs/tag-motion.jsonl \
  --emit-observation runs/tag-motion-observation.jsonl \
  --ball-id ball-01 --hole-id H01
```

The emitted record has `confidence=0.0`,
`confidence_calibrated=false` and `diagnostic_only=true`. This avoids inventing
a probability before labelled data exists. A physical `0.1.7` stationary record
was routed through the one-hole runtime as `motion.stationary`; the hole stayed
`READY`, the audit received one motion decision and the stroke count stayed
zero.

## Evidence boundary and remaining work

The current stationary/active gates are explicitly provisional. They check
duration, sensor validity, sequence continuity, acceleration variability and
gyro RMS. They are lab diagnostics, not authoritative gameplay evidence and
not product thresholds. A real active observation was routed through the
one-hole runtime as `motion.active`; the hole remained `READY`, the audit gained
one decision and strokes remained zero.

Before extending the deterministic FSM, collect separately labelled episodes
for multiple stationary orientations and, once a protective core exists,
putter impact, rolling, settling and free-fall/drop. Pickup/carry and ordinary
handling now have two transport-valid repetitions each, but that is far too
small for product thresholds and already proves simple intensity separation is
unsafe. Episode-level train/test separation, clipping observation, a
mechanically repeatable instrumented ball core and independent labels remain
required. The Tag must continue emitting generic observations; the Venue Edge,
physical tee/cup sensors and game context own authoritative decisions.
