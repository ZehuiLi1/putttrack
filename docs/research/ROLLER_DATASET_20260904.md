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
| **Total** |  | **48** | **24,020** | **0** | **0** |

Every capture used Tag firmware `0.1.17`, device
`f383571202836e6f`, boot `b7d6474ba25dbade`, a frozen device-side history,
and a synchronized host runner. BMI270 acceleration and gyro had zero clipping
events in all 48 captures. The ADXL367 `±2 g` wake sensor clipped in 13 of 24 R2
captures (26 samples total) and 8 of 24 R3 captures (10 samples). This is a
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

Linear extrapolation would reach the BMI270 `±2000 dps` gyro range near a
commanded 202 RPM, but extrapolation is not an acceptance test. Higher-speed
work must explicitly monitor gyro clipping and should not jump directly to the
controller's 300 RPM software ceiling.

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

## Immediate next gates

1. Measure roller diameter/contact layout and add timestamped encoder speed if
   the driver exposes it; this converts commanded RPM into usable kinematic
   calibration.
2. Repeat selected `30/60/120 RPM` cases after a deliberate Ball orientation
   change and on a second day.
3. Collect the manual pickup/place and genuine putter/free-roll datasets before
   attempting semantic classification.
4. Add a guarded repeatable striker or release ramp if automated impact/free
   roll volume becomes more valuable than manual collection.
