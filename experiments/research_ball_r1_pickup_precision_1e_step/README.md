# Pickup precision phase 1E: course-step controls

## Scope

This evidence set preserves ten successful `track_step_drop` captures plus one
automatically rejected diagnostic attempt. The planned action was a single
manual push over one fixed small course-like step followed by natural settling,
without pickup. Planned speeds were three slow, four normal and three faster
runs.

The operator reported that successful episode r08 rolled after the step and
then collided with an obstacle. It is preserved as a mixed step-plus-collision
negative and excluded from clean step-only comparisons. A separately named
replacement capture is planned rather than overwriting or relabelling r08.

Step height, surface and independent video truth were not measured. These are
pickup hard-negative controls, not stroke, cup or scoring authority.

## Capture and quality result

- device ID: `f383571202836e6f`
- firmware: `0.1.17`
- source rate: 50 Hz
- successful captures: 10
- clean step-only captures: 9
- mixed step-plus-obstacle captures: 1 (`r08`)
- automatically rejected diagnostics: 1 (first `r09` attempt)
- successful-capture continuity/metadata failures: 0
- successful-capture quality: 0 `PASS`, 10 `WARN`, 0 `FAIL`
- ADXL367 clipping: 10/10 successful episodes, 102 total samples
- BMI270 accelerometer clipping: 0/10 successful episodes
- BMI270 gyroscope clipping: 1/10 successful episodes, 54 samples (`r08`)

The rejected first r09 attempt had pre-GO gyro activity and failed the
stationary baseline gate. Its diagnostic JSONL is retained under
`diagnostics/`; the accepted retry is the canonical r09 capture.

## Post-GO clean comparison

| Feature | Pickup holdout, n=10 | Clean step-only, n=9 | Interpretation |
|---|---:|---:|---|
| Accel-norm stdev (m/s²) | 1.474-4.864 | 1.956-5.121 | strongly overlaps |
| Gyro RMS (rad/s) | 1.708-4.531 | 4.923-14.535 | separated here, near boundary |
| Gyro peak (rad/s) | 6.934-17.385 | 16.629-44.238 | slight boundary overlap |
| Jerk peak (m/s³) | 318.272-1294.090 | 1112.250-3472.600 | boundary overlap |
| Active-sample fraction | 0.318-0.772 | 0.246-0.386 | overlap at boundary |

Course-step motion also destroys any simple acceleration-variability pickup
threshold. Its temporal profile is generally shorter and more energetic than
pickup/carry, but all listed scalar features have or approach a boundary
overlap. A robust decision therefore needs temporal state/shape and explicit
`UNKNOWN` handling rather than a one-dimensional threshold.

The mixed r08 episode has post-GO gyro RMS `17.319 rad/s`, gyro peak
`59.773 rad/s` and active fraction `0.175`, making it visibly different from
the nine clean planned step episodes. The operator report is still the reason
the semantic label is known; the IMU values alone cannot prove which obstacle
was hit.

## Files

- `manifest.json` provides episode identity and known provenance.
- `raw/` contains the ten original successful JSONL captures.
- `diagnostics/` contains the automatically rejected pre-GO-contaminated
  attempt; it is not in the manifest or aggregate metrics.
- `analysis/dataset_summary.csv` and `.json` contain deterministic features.
- `analysis/quality_report.json` records structural quality outcomes.
- `analysis/plots/` contains dependency-free per-episode traces.

Regenerate the derived analysis with:

```bash
python tools/analyze_motion_dataset.py \
  experiments/research_ball_r1_pickup_precision_1e_step/manifest.json \
  --output-dir experiments/research_ball_r1_pickup_precision_1e_step/analysis
```
