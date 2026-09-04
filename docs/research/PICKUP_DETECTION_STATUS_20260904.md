# Pickup detection research status — 2026-09-04

## Decision status

Pickup detection is now the highest-priority IMU semantic research task. The
current assembled-Ball data supports a promising temporal separation between
pickup and putt/roll, but there is not yet an independently validated product
classifier. No threshold in this document has scoring authority.

The intended product behavior is:

```text
HOLE_ACTIVE and not cup-confirmed
        -> pickup candidate
        -> confidence and temporal confirmation
        -> PICKUP_SUSPECTED or PICKUP_CONFIRMED
        -> venue rule may invalidate the current hole/attempt
```

Pickup before Tee activation and after authoritative cup completion is ignored.
A pickup event must never invalidate an entire round by itself. Medium
confidence remains reviewable evidence; only a separately validated
high-confidence policy may automatically affect the current hole.

## Available physical evidence

The local workspace currently contains 161 unique raw IMU JSONL files with
113,867 `tag_motion` records. The repeatable packager is
`tools/package_imu_dataset.py`; generated archives and `runs/` remain local and
are intentionally not claimed as checked-in GitHub data.

The most relevant recent sets are:

- ten operator-labelled `pickup_carry` episodes at 50 Hz with zero sequence
  gaps and no BMI270 clipping;
- ten nominal `putt_normal` episodes at 50 Hz with zero sequence gaps;
- the checked-in seven-episode manual-floor set containing stationary, two
  free rolls, pickup/carry and restrained repeated taps;
- 86 formal programmable-roller captures, which characterize constrained
  rotation but are not semantic truth for real putts or pickup.

Latest pickup timing caveats:

- r07 contains pre-GO motion;
- r09 begins approximately 6.7 seconds after GO;
- r01, r03, r05 and r08 reach close to the window end and have limited clean
  stationary tail;
- all ten remain useful for pickup-onset exploration.

Latest nominal-putt quality review:

- r01–r04 are suspected to include an obstacle collision after the putt;
- r05 is stationary and is not a putt;
- r06 contains pre-GO motion and does not have a normal putt signature;
- r08 has pre-GO contamination but a usable post-GO rolling segment;
- r07, r09 and r10 are the cleanest current putt candidates;
- eight dynamic runs reach the BMI270 ±2000 dps gyro boundary, so clipped peak
  magnitude is not ground truth.

## Measured separation

Gravity-vector reversal is not a valid pickup rule. The ten latest pickup
episodes reach maximum body-frame gravity-direction changes of approximately
66–177 degrees, but earlier manual light and medium rolls also reach about 159
and 177 degrees. Only two of the ten pickups contain a sustained near-180-degree
orientation, so reversal would both miss pickups and accept rolls.

An upward-start feature is real but is also not sufficient. In the first 200 ms
after detected onset, all ten pickups increase acceleration norm relative to
the preceding rest by approximately 1.6–10.1 m/s². The usable nominal putts
increase by about 4.6–23.2 m/s². Putter contact can therefore create a larger
initial acceleration than pickup.

The strongest current distinction is the following one-second rotation shape:

| Feature | Latest pickup | Usable nominal putt |
|---|---:|---:|
| mean gyro norm | approximately 3–7 rad/s | approximately 31–44 rad/s |
| gyro-axis consistency | 0.27–0.60 | 0.89–1.00 |
| BMI270 gyro clipping | none | common |

Axis consistency here is the norm of the mean gyro vector divided by the mean
gyro norm. A rolling ball tends to retain one dominant rotation axis; human
handling is slower and more multi-axis. This must be recomputed in orientation-
and speed-diverse held-out sessions before it can become a threshold.

## Provisional research detector

A post-hoc exploratory rule was replayed over the current data:

1. estimate venue vertical from the pre-action stationary BMI270 acceleration;
2. propagate that direction over a short interval using BMI270 gyro;
3. require estimated positive vertical impulse above `0.5 m/s` over an
   approximately 0.6-second onset window;
4. require one-second mean gyro below `10 rad/s`;
5. require one-second gyro-axis consistency below `0.75`.

This research rule selected all 11 available pickup episodes, while selecting
none of eight usable/latest nominal putts, two older manual rolls or one
restrained-tap episode. Stationary files produced no motion candidate. This is
an in-sample result with thresholds chosen after inspection; it is evidence
that the approach is worth validating, not an accuracy estimate.

The runtime implementation should use two temporal paths:

```text
stationary -> upward onset -> low/moderate irregular rotation -> pickup

stable single-axis roll -> abrupt roll-model departure
                        -> upward onset + hand motion -> rolling pickup
```

After confirmation the event is latched until hole reset or the next Tee
activation. Placement is useful for dataset segmentation and state recovery,
but does not need to be a separate gameplay event.

## Required validation before implementation authority

Collect in this order:

1. at least 20 no-lift controls where the Ball is touched, rotated and slid but
   continuously remains on the surface;
2. at least 20 rolling-pickup episodes;
3. slow lift, fast grab, different grip/orientation and different operators;
4. explicit rail/wall collisions and representative course-step drops;
5. cup lip, entry, bounce and rest with independent cup/video truth;
6. a separate-day/session holdout never used to choose thresholds.

Begin with an interpretable state machine and logistic/tree baseline. Report
pickup precision, false-positive rate and confidence intervals by entire
session. A neural network is not justified until the labelled diversity and
holdout set are materially larger. The first host/Edge detector remains
research-only; deploy features to the nRF54L15 only after the definition is
stable and resource/power behavior is measured.

