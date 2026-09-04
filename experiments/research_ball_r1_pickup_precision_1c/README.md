# Pickup precision phase 1C: stationary-start pickup holdout

## Scope

This immutable evidence set contains ten `pickup_carry` episodes captured only
after the stationary-start V0 hypothesis was frozen. Each planned action starts
with the Ball at rest, then a natural pickup, 2-3 seconds of walking and gentle
placement. Planned variations cover ordinary, slow/smooth and somewhat faster
natural pickups with varied unmeasured initial orientation.

Do not tune `pickup_detector_v0_stationary_start` from these episodes. If V0
fails and the hypothesis changes, assign a new detector ID and evaluate it on a
later untouched set.

Surface material and independent video truth were not recorded. The operator
confirmed completion of the requested physical actions, so this is useful
holdout evidence but not yet a new-day/new-operator/new-Ball product claim.

## Capture and quality result

- device ID: `f383571202836e6f`
- firmware: `0.1.17`
- source rate: 50 Hz
- captured episodes: 10
- pre-GO stationary gate: 10/10 `PASS`
- continuity/metadata failures: 0
- quality: 4 `PASS`, 6 `WARN`, 0 `FAIL`
- ADXL367 clipping: 6/10 episodes, 38 total samples
- BMI270 accelerometer clipping: 0/10 episodes
- BMI270 gyroscope clipping: 0/10 episodes

The warnings are ADXL367 ±2 g saturation only. BMI270 retained full
accelerometer and gyroscope range in all ten captures, so all ten remain usable
for stationary-start feature evaluation.

## Post-GO comparison with phase 1A

| Feature | No-lift handling, n=10 | Pickup holdout, n=10 | Separation in these sessions |
|---|---:|---:|---|
| Accel-norm stdev (m/s²) | 0.094-0.612 | 1.474-4.864 | no overlap |
| Gyro RMS (rad/s) | 1.057-3.379 | 1.708-4.531 | substantial overlap |
| Gyro peak (rad/s) | 4.561-14.299 | 6.934-17.385 | substantial overlap |
| Jerk peak (m/s³) | 34.902-492.304 | 318.272-1294.090 | overlap |
| Active-sample fraction | 0.227-0.643 | 0.318-0.772 | substantial overlap |

Acceleration-norm variability is the clearest simple separator in these two
same-day sessions. Gyroscope magnitude, jerk and generic active fraction are
not safe standalone pickup rules. The apparent acceleration gap is not a
product threshold: collision, course-step, different-surface and independent
session/operator controls still need to challenge it.

The next immediate hard-negative batch is `putt_rail_collision`. It tests
whether a legitimate in-course impact can occupy the apparent gap without the
Ball being picked up.

## Evaluation boundary

The standard repository pipeline has validated capture integrity and emitted
deterministic whole-window/post-GO generic features. A frozen-V0 pickup
pass/fail rate is not claimed here because the exact V0 vertical-impulse
feature extractor/evaluator is not yet executable and unit-tested in the
repository. The preserved three-feature ML script reproduces the historical
22-episode model baseline from a feature ledger; it does not extract V0
features from these new raw files.

## Files

- `manifest.json` provides episode identity and known provenance.
- `raw/` contains the original unmodified JSONL captures.
- `analysis/dataset_summary.csv` and `.json` contain deterministic features.
- `analysis/quality_report.json` records structural quality outcomes.
- `analysis/plots/` contains dependency-free per-episode traces.

Regenerate the derived analysis with:

```bash
python tools/analyze_motion_dataset.py \
  experiments/research_ball_r1_pickup_precision_1c/manifest.json \
  --output-dir experiments/research_ball_r1_pickup_precision_1c/analysis
```
