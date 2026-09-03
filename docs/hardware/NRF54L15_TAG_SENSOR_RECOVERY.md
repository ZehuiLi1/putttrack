# nRF54L15 Tag sensor fault detection and recovery

**Status:** confirmed physical `0.1.16`; healthy path passed, injected/recurrent
fault paths pending

## Observed fault

The first mechanically assembled research-ball session exposed one real fault
on 2026-09-03. Before a remote reset the Tag reported:

- uptime `11,641,871 ms`;
- `adxl_ready=false`, `bmi_ready=true`;
- `sensor_errors=72,195`;
- idle fallback polling every `160 ms`.

`72,195 × 160 ms = 11,551,200 ms`, which covers almost the complete boot.
Inspection of `0.1.13` confirmed that sensor readiness was sampled only once at
startup. A failed ADXL367 driver initialization could therefore never become
ready during that boot, while the fallback loop counted the same unavailable
sensor on every poll. The counter represented failed samples, not 72,195
independent hardware faults.

An encrypted SMP reset recovered the ADXL367 without opening the ball. The new
boot reported both sensors ready and zero errors. A subsequent assembled-ball
stationary capture produced 1,024 contiguous records over 20.46 seconds at
exactly 50 Hz with both sensors valid, zero sequence gaps, zero clipping and
zero error deltas. This proves recovery for that occurrence but does not prove
whether its root cause was power-up timing, driver initialization, bus state or
intermittent mechanical/electrical stress.

After the capture, the physical `0.1.13` Tag was returned to `auto/idle` through
the pinned BLE address and retry-capable tool. The final live status reported
both sensors ready, zero sensor/advertising/power-management errors, ADXL367
interrupt and wake-up mode enabled, BMI270 paths at zero ODR, SPI22 suspended
and the 2.0–2.5 second idle advertising interval.

## Candidate policy

Candidate `0.1.16` implements this bounded state machine:

```text
HEALTHY -- one failed sample --> SUSPECT
SUSPECT -- next good sample --> HEALTHY
SUSPECT -- 5 consecutive failures --> RECOVERING
RECOVERING -- configure + 3 good samples --> HEALTHY
RECOVERING -- 3 failed attempts --> DEGRADED
DEGRADED -- quiet 10 s, BLE disconnected, reboot unused --> one warm reboot
DEGRADED -- reboot guard already set --> QUARANTINED
```

The first two recovery retries are separated by 1 and 5 seconds. Recovery
stops the stream, invalidates live and frozen history and increments a recovery
generation. A successful recovery restarts an empty 50 Hz history; data from
before and after recovery cannot silently become one accepted capture.

The warm-reboot guard is kept in a `.noinit` record with a magic value, reboot
count and last fault bits. In the build-only image it is located at
`0x20027fd0`; MCUboot uses RAM only through `0x20006c08`, so the two regions do
not overlap. The guard clears only after five minutes of continuous healthy
operation. A fault that returns before then is quarantined instead of creating
an automatic reboot loop. This still requires physical testing on the exact
MCUboot/application pair before relying on SRAM retention as product evidence.

No automatic reboot is allowed while BLE is connected or until ten seconds
have elapsed since the last measured motion. A watchdog is deliberately not
used for sensor I/O faults; it remains appropriate only for a stuck scheduler
or main loop.

Active sampling checks every record. Hardware-interrupt idle adds one ADXL367
health read every ten minutes; after one idle self-test failure the interval
temporarily becomes one second so a persistent failure reaches recovery without
waiting fifty minutes. This periodic diagnostic is separate from motion wake
polling and needs a current measurement before its energy cost is claimed.

## Telemetry and capture contract

Encrypted SMP status adds:

- `sensor_health` and `capture_safe`;
- failed-sample count, fault-episode count and per-sensor consecutive streaks;
- recovery generation, attempts, successes and failed attempts;
- last error bitset and uptime;
- warm-reboot count, guard and pending state;
- idle health-check interval.

Host parsing remains backward compatible with `0.1.13`. Legacy firmware still
fails capture preflight when an old nonzero sensor counter exists. For `0.1.16`
and later, a healthy device may retain historical failed-sample counts, but a
capture fails if health is not `healthy`, `capture_safe` is false, an error
counter grows, or the recovery generation changes during the capture.

## Physical healthy-path result

The NFC variant of `0.1.16` was installed through the guarded BLE OTA path on
2026-09-03. Before confirmation, both sensors remained ready through powered
NFC reads, field removal and automatic return to idle. Sensor health stayed
`healthy`; sensor, recovery and power-management errors remained zero. After
remote confirmation and reset, both sensors initialized again and the Tag
returned to ADXL367 interrupt wake mode with BMI270 sampling stopped and SPI
suspended.

This establishes that the recovery code does not disturb the observed healthy
path. It does not exercise local reconfiguration, the retained one-reboot guard
or quarantine. Those require deliberate fault injection/reproduction and ten
sealed reset cycles before the complete recovery policy can be called a
physical pass.

## Evidence and remaining gates

Both default and NFC variants compile and sign under NCS v3.4.0. The build used
Nordic's insecure debug key strictly for compile evidence; those binaries must
not be flashed or distributed:

| Variant | App Flash | App RAM | debug signed BIN SHA-256 |
|---|---:|---:|---|
| Default | 185,268 / 696,176 B | 207,360 / 262,144 B | `6fee79ea7ba9c649ad7097edb48ef66703f5a52aebe289dc64c779bc91f91976` |
| NFC service | 192,544 / 696,176 B | 210,508 / 262,144 B | `a26d641651e38c36456dbae0c0dd2fb63078b4f53fd39d13f8aebea37a32ea3b` |

The recovery policy is now present in confirmed `0.1.17`; its ordinary healthy
path, idle wake and capture guards have passed on target. The remaining gates
are:

1. add deterministic firmware fault injection for fetch/read failures and
   retained reboot-guard state;
2. verify at least ten sealed-ball reset/start cycles;
3. deliberately prove local recovery, guarded reboot, quarantine and host
   capture rejection on target;
4. keep signed OTA test boot and the retained `0.1.16` slot as the recovery
   boundary while running those tests.
