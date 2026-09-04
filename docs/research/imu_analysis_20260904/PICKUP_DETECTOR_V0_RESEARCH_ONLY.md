# Pickup Detector V0 — research-only specification

## Status

This is a post-hoc research hypothesis. It has no gameplay or scoring authority.

## Current stationary-start candidate

For a window aligned to motion onset:

1. Estimate venue vertical from the pre-action stationary BMI270 acceleration vector.
2. Propagate the vertical direction over a short interval using BMI270 gyro.
3. Calculate positive vertical impulse over approximately 0.6 s.
4. Calculate one-second mean gyro norm.
5. Calculate one-second gyro-axis consistency:

   `axis_consistency = norm(mean(gyro_vector)) / mean(norm(gyro_vector))`

Current exploratory candidate:

```text
positive_vertical_impulse_0p6s > 0.5 m/s
AND mean_gyro_norm_1s < 10 rad/s
AND gyro_axis_consistency_1s < 0.75
```

Observed on the deliberately selected current research set:

```text
pickup:     11 / 11 selected
non-pickup:  0 / 11 selected
```

This is not an accuracy estimate because thresholds were chosen after inspecting these episodes.

The exact frozen feature/onset definition for the next untouched capture batch
is stored in
[`configs/research/pickup_detector_v0.json`](../../../configs/research/pickup_detector_v0.json).
It records `authority=false`, treats missing/invalid/clipped evidence as UNKNOWN,
and supports only the stationary-start path. Do not alter that file after
viewing holdout results; any later definition must receive a new detector ID.

## Required rolling-start path

```text
stable dominant-axis rolling
    -> abrupt departure from the rolling model
    -> positive vertical impulse
    -> low/moderate irregular hand rotation
    -> pickup candidate
```

The stationary-start rule is not sufficient for a rolling pickup.

## Context and safety boundary

```text
HOLE_ACTIVE
AND not CUP_CONFIRMED
AND motion-quality checks pass
    -> PICKUP_SUSPECTED / PICKUP_CONFIRMED evidence
```

A Ball-side classifier must not directly alter score. Medium confidence remains reviewable; only a separately validated high-confidence policy can affect the current hole.
