# Pickup precision phase 1B: rolling-start pickup

## Scope

This immutable evidence set contains ten operator-labelled `rolling_pickup`
episodes captured from the assembled Research Ball after a device-side GO
marker. Each planned action was a manual roll followed by pickup while the Ball
was still moving, a short hold and placement. The first two captures preceded
low-clipping guidance and are retained as stress cases; later captures vary
slow, normal and near-stop pickup timing.

Surface material and an independent timestamp for the pickup sub-event were
not recorded. The episode label is therefore suitable for whole-episode and
state-path analysis, but not for supervised frame-level pickup-boundary
training or a timing-error claim.

## Capture and quality result

- device ID: `f383571202836e6f`
- firmware: `0.1.17`
- source rate: 50 Hz
- captured episodes: 10
- continuity/metadata failures: 0
- quality: 0 `PASS`, 10 `WARN`, 0 `FAIL`
- ADXL367 clipping: 10/10 episodes, 106 total samples
- BMI270 accelerometer clipping: 0/10 episodes
- BMI270 gyroscope clipping: 2/10 episodes, 78 total samples

Every warning is caused by sensor clipping rather than transport failure. The
ADXL367 ±2 g wake sensor clipped in every episode, so it must not be used for
rolling/pickup amplitude calibration. The BMI270 accelerometer retained the
full range in all ten episodes and remains the primary motion-analysis source.
The two stress episodes with BMI270 gyro clipping can support coarse state and
timing work but not gyro peak calibration.

## Whole-window findings

| Feature | Minimum | Median | Maximum |
|---|---:|---:|---:|
| Accel-norm stdev (m/s²) | 2.366 | 2.683 | 8.060 |
| Gyro RMS (rad/s) | 4.709 | 7.189 | 14.299 |
| Gyro peak (rad/s) | 22.939 | 33.107 | 53.379 |
| Jerk peak (m/s³) | 1476.190 | 1753.880 | 4486.640 |
| Active-sample fraction | 0.234 | 0.470 | 0.655 |

These values describe the combined push, roll, pickup, hold and placement
episode. They do not isolate the pickup transition.

## Detector consequence

The frozen stationary-start V0 searches for the first motion onset and builds
its feature window around that onset. In these episodes, the first onset is the
manual push/roll, not the later pickup. Applying that path unchanged would
therefore evaluate the wrong physical transition even though the pre-GO
baseline is stationary.

Rolling pickup needs a separate state-aware path:

1. establish `ROLLING` from sustained angular motion;
2. search inside that state for a later transition consistent with loss of
   ground contact/hand support;
3. classify only the transition window, not the original roll onset; and
4. return `UNKNOWN` when clipping or missing transition timing prevents a safe
   decision.

Before training or reporting transition-level accuracy, collect either a
second device-side marker at the actual pickup instant or independently
timestamped video. The current ten episodes are still valuable as complete
rolling-start path examples and for designing that annotation workflow.

## Files

- `manifest.json` provides episode identity and known provenance.
- `raw/` contains the original unmodified JSONL captures.
- `analysis/dataset_summary.csv` and `.json` contain deterministic features.
- `analysis/quality_report.json` records structural quality outcomes.
- `analysis/plots/` contains dependency-free per-episode traces.

Regenerate the derived analysis with:

```bash
python tools/analyze_motion_dataset.py \
  experiments/research_ball_r1_pickup_precision_1b/manifest.json \
  --output-dir experiments/research_ball_r1_pickup_precision_1b/analysis
```
