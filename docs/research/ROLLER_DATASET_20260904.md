# Programmable roller dataset — 2026-09-04

## Scope and validity

This session characterizes the assembled research Ball in the programmable
roller. It is valid evidence for transport integrity, repeatability, commanded
speed response, direction asymmetry, IMU range use, powered starts and stops.
It is **not** ground truth for a putter strike, free roll, obstacle collision,
ball-to-ball collision, cup entry, pickup or carry.

All motor RPM values below are controller commands. Roller diameter, contact
geometry and slip have not been independently measured, so they must not be
reported as Ball RPM or ground speed.

## Dataset inventory

| Set | Profiles | Captures | Motion samples | Failed captures | Sequence gaps |
|---|---|---:|---:|---:|---:|
| R2 speed/direction | `±30/60/90/120 RPM`, 3 repeats | 24 | 10,811 | 0 | 0 |
| R3 start/stop | `±60 RPM`, acceleration `0/5/20/80`, 3 repeats | 24 | 13,209 | 0 | 0 |
| R2 low-speed boundary | `±1/2/3/5/10/15/20 RPM` | 14 | 7,608 | 0 | 0 |
| R2 high-speed boundary | `+135/150/155/165/180`, `-165/180 RPM` | 7 | 3,154 | 0 | 0 |
| R4 controlled stop | `±60 RPM` at `0/5/20/80`; `±120 RPM` at `5/80`; `+30 RPM` safety gate | 13 | 8,002 | 0 | 0 |
| R5 ten-second steady hold | `±60/120 RPM` | 4 | 3,000 | 0 | 0 |
| **Total** |  | **86** | **45,784** | **0** | **0** |

Every capture used Tag firmware `0.1.17`, device
`f383571202836e6f`, boot `b7d6474ba25dbade`, a frozen device-side history,
and a synchronized host runner. BMI270 acceleration had zero clipping events
in all 86 captures. BMI270 gyro had zero clipping in 84 captures; only the two
deliberate `±180 RPM` limit tests clipped (19 samples total). The ADXL367
`±2 g` wake sensor clipped in dynamic tests (144 samples total). This is a
warning about using ADXL367 for dynamic measurement, not a transport failure;
BMI270 remains the dynamic sensor.

## Commanded-speed response

The table uses the median BMI270 gyro norm during the steady portion of each
run, then averages the three repetitions.

| Motor command | + direction (rad/s) | − direction (rad/s) | Pair mean (rad/s) | −/+ amplitude ratio |
|---:|---:|---:|---:|---:|
| 30 RPM | 5.633 | 4.999 | 5.316 | 0.887 |
| 60 RPM | 10.653 | 10.058 | 10.356 | 0.944 |
| 90 RPM | 16.054 | 16.294 | 16.174 | 1.015 |
| 120 RPM | 20.749 | 20.423 | 20.586 | 0.984 |

Across these four pair means, the provisional fit is:

```text
BMI270 gyro norm [rad/s] = 0.2006 + 0.17210 × commanded motor RPM
R² = 0.99747
```

This establishes a strong monotonic fixture response over the tested range.
It does not establish no-slip kinematics. Direction asymmetry is largest at
30 RPM and falls substantially at higher speeds, consistent with contact,
preload, dead-band or low-speed control effects that still need mechanical
measurement.

### Measured low- and high-speed boundaries

The low-speed sweep used one capture in each direction. The table reports the
median gyro norm in the stable powered interval; stationary baseline medians
were only `0.0057–0.0064 rad/s`.

| Command | + direction (rad/s) | − direction (rad/s) | Result |
|---:|---:|---:|---|
| 1 RPM | 0.245 | 0.117 | Direction-dependent; the existing generic check classified `+1` active but left `-1` in its motion dead band |
| 2 RPM | 0.333 | 0.302 | Active in both directions; lowest reliable tested command |
| 3 RPM | 0.571 | 0.487 | Active in both directions |
| 5 RPM | 0.797 | 0.745 | Active in both directions |
| 10 RPM | 1.259 | 1.414 | Active in both directions |
| 15 RPM | 2.273 | 2.240 | Active in both directions |
| 20 RPM | 3.485 | 3.939 | Active in both directions |

This does not make `2 RPM` a product threshold. It is the fixture's measured
bidirectional detection boundary in this orientation and session.

At the upper boundary, `±165 RPM` completed with no BMI270 gyro clipping.
The peak single-axis rates were `32.688 rad/s` in the positive direction and
`31.481 rad/s` in the negative direction. Both `±180 RPM` runs reached
approximately `34.91 rad/s` on one axis and generated 10 and 9 clipping events.
Therefore:

- `165 RPM` is the highest bidirectionally verified no-clipping command for
  this assembly;
- `180 RPM` is a deliberately captured invalid/limit example, not training
  truth for amplitude-sensitive features;
- no `195/300 RPM` test is justified with the present `±2000 dps` range.

## Start/stop characterization

The Emm_V5 `F6` acceleration field is a dimensionless driver setting in
`0..255`; zero requests direct acceleration. The values below are derived from
a five-sample median-filtered gyro norm at 50 Hz. `t10`, `t50` and `t90` are
relative to the device-side GO marker and therefore include the host's serial
open/probe/arm latency. The `10–90% rise` difference removes most of that
constant latency and is the useful comparison.

| Direction | Acceleration setting | Steady gyro (rad/s) | t10 (s) | t50 (s) | t90 (s) | 10–90% rise (s) |
|:---:|---:|---:|---:|---:|---:|---:|
| + | 0, direct | 10.978 ± 0.301 | 0.887 ± 0.064 | 0.907 ± 0.064 | 1.013 ± 0.061 | **0.127 ± 0.012** |
| + | 5 | 11.694 ± 0.102 | 0.987 ± 0.012 | 1.247 ± 0.031 | 1.400 ± 0.140 | 0.413 ± 0.147 |
| + | 20 | 11.416 ± 0.323 | 0.980 ± 0.020 | 1.213 ± 0.023 | 1.360 ± 0.140 | 0.380 ± 0.139 |
| + | 80 | 11.003 ± 0.203 | 0.953 ± 0.011 | 1.133 ± 0.023 | 1.287 ± 0.133 | 0.333 ± 0.127 |
| − | 0, direct | 10.437 ± 0.285 | 0.847 ± 0.023 | 0.853 ± 0.031 | 0.920 ± 0.035 | **0.073 ± 0.012** |
| − | 5 | 10.967 ± 0.746 | 0.980 ± 0.020 | 1.187 ± 0.031 | 1.533 ± 0.031 | 0.553 ± 0.042 |
| − | 20 | 11.394 ± 0.896 | 1.040 ± 0.040 | 1.213 ± 0.042 | 1.387 ± 0.208 | 0.347 ± 0.170 |
| − | 80 | 10.902 ± 0.456 | 0.926 ± 0.030 | 1.120 ± 0.034 | 1.186 ± 0.023 | 0.260 ± 0.020 |

Direct acceleration is distinctly and repeatably faster in both directions.
Across the two direction means, nonzero settings also follow the expected broad
trend (`5` slowest, `20` intermediate, `80` fastest), but individual
distributions still overlap with only three repetitions per direction. Contact
dynamics and 20 ms sample resolution can dominate the smaller differences.
Keep setting 20 as the normal safe default; reserve setting 0 for bounded
transition tests.

Every R3 run also includes the controller's redundant immediate stop and the
post-stop settling interval. Those stop transients are useful negative/control
examples for transition detection. They must be labelled `powered_stop_proxy`,
not `collision` or `putter_impact`.

## Controlled deceleration and stop safety

The controller and synchronized runner now accept an optional deceleration
field. If the ramp-to-zero command is not acknowledged or does not reach zero
within four seconds, firmware falls back to the redundant immediate STOP path
before disabling the driver. All 13 R4 captures ended at encoder-reported zero,
disabled output, no stall flags and no fallback. BMI270 had no clipping.

The following single-run values use a five-sample median filter. `90–10% fall`
starts at the last sample at or above 90% of the steady gyro level and ends at
the first sustained interval at or below 10%. They characterize the complete
fixture response, not the driver's internal ramp alone.

| Command | Deceleration | 90–10% fall (s) |
|---:|---:|---:|
| +30 RPM | 5 | 0.16 |
| +60 RPM | 0 / 5 / 20 / 80 | 0.14 / 0.48 / 0.46 / 0.22 |
| −60 RPM | 0 / 5 / 20 / 80 | 0.52 / 0.64 / 0.30 / 0.86 |
| +120 RPM | 5 / 80 | 1.08 / 0.92 |
| −120 RPM | 5 / 80 | 0.98 / 0.84 |

Only one repetition exists for each controlled-stop cell, and the constrained
ball's gyro norm oscillates with contact geometry. These results prove that the
profiles and safety fallback work; they do not support a monotonic physical
mapping from the Emm_V5 setting to SI deceleration. Omit the field for the
proven immediate STOP behavior; use a supplied field only to create a labelled
`powered_deceleration_proxy`.

## Ten-second steady holds

Four longer runs checked transport continuity and within-run drift. Comparing
two equal stable windows near the beginning and end of each hold gave:

| Command | First median (rad/s) | Second median (rad/s) | Change |
|---:|---:|---:|---:|
| +60 RPM | 11.435 | 10.962 | −4.14% |
| −60 RPM | 11.691 | 10.748 | −8.07% |
| +120 RPM | 22.648 | 22.278 | −1.64% |
| −120 RPM | 22.834 | 22.715 | −0.52% |

All 3,000 samples were contiguous and free of BMI270 clipping. The larger
60 RPM change is another reason to treat commanded speed as a fixture label,
not calibrated ball speed; contact preload, slip and speed regulation remain
convolved.

## What the roller can automate

Without an operator touching the Ball, the current rig can collect:

- stationary-in-fixture baselines;
- repeatable constant rolling at bounded commanded speeds;
- both directions and direction-dependent contact effects;
- powered start/ramp comparisons;
- immediate powered-stop transients and settling;
- day-to-day repeatability, thermal/battery drift and data-transport soak;
- sensor clipping onset and feature stability.

An abrupt start or stop can be a useful **generic transient proxy**, but it
cannot provide semantic ground truth for a strike or collision. A single motor
roller also cannot reproduce free translation over turf, slope, bounce, cup
geometry, off-axis impact or human handling.

## Data that requires physical help or added actuators

The following classes need an operator and synchronized video/independent
event marker, unless the rig is expanded with a striker, release ramp, wall,
cup and optical gates:

| Required class | Minimum next collection | Why the roller cannot label it |
|---|---:|---|
| Pickup, carry, place | 20 episodes each, varied people/speeds | Human handling has translation and changing grip/orientation |
| Putter strike | 20 gentle, 20 medium, 20 hard; include off-centre hits | Contact impulse and free departure are absent in the roller |
| Free roll and natural stop | 20 per representative surface/slope | Fixture contact continuously constrains the Ball |
| Wall/rail collision | 20 per useful angle/speed | A powered stop has different contact physics |
| Ball-to-ball collision | 20 controlled pairs | Requires two freely moving bodies and identity ground truth |
| Cup lip, entry, drop and rest | 20 complete sequences | Requires actual cup geometry and an authoritative cup sensor/video |
| False-positive venue motion | several 10–30 minute sessions | Floor vibration, trolley/rack transport and nearby impacts are site-specific |

Each manual episode should contain pre-event rest, exactly one named action,
post-event rest, a unique filename, operator notes and video/event-marker truth.
Ambiguous or multi-action episodes stay in the dataset but are marked invalid
for supervised training.

## Analysis decision

Do not train a neural network from this roller-only session. First use these
captures to validate segmentation, invariant features, clipping policy and
rolling/settling candidates. Then add the independently labelled physical
classes above and split evaluation by complete session/day/mechanical revision,
never by adjacent windows from one run. A compact rule-based baseline should be
recorded before comparing small classical models or neural networks; the
gameplay engine must continue treating IMU classification as non-authoritative
evidence.

## Roller-phase closure

The required roller work for this mechanical/firmware revision is complete.
It established transport integrity, bidirectional repeatability, low-speed
detection, high-range clipping onset, acceleration/stop proxies, controlled
deceleration safety and ten-second steady behavior. The roller can now be
removed from the normal field kit; the Ball and XIAO nRF52840 HCI bridge are
sufficient for the next manual/free-motion capture phase.

Reopen roller collection only after a sensor range/rate change, firmware motion
pipeline change, shell/carrier/contact revision, unexplained field regression,
or a deliberate calibrated-kinematics study. Those are requalification events,
not unfinished work in this dataset.

## Next gates without the roller

1. Collect the manual pickup/place and genuine putter/free-roll datasets before
   attempting semantic classification.
2. Collect wall/rail, ball-to-ball and real cup sequences with synchronized
   video or independent event markers.
3. Add a guarded repeatable striker or release ramp if automated impact/free
   roll volume becomes more valuable than manual collection.
4. Treat roller diameter/contact geometry and timestamped encoder telemetry as
   an optional future calibration study, not a prerequisite for field capture.
