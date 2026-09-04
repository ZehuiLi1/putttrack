# Pickup precision phase 1D: gentle unobstructed putts

## Scope

This evidence set preserves eleven successful `putt_gentle` captures. Ten are
clean unobstructed-putt controls; original r05 hit an obstacle after the putt
and is retained as a mixed putt-plus-collision control. A separately named
clean replacement was collected instead of overwriting r05.

The operator reported one gentle putt followed by natural settling without
pickup after each visible GO cue. Planned variations include very light and
ordinary light strokes plus changed unmeasured initial orientation/direction.
Surface, travel distance/speed and independent video truth were not measured.
These episodes are pickup negatives, not authoritative stroke or scoring
evidence.

The operator confirmed that long-distance/high-energy unobstructed strokes
cannot be collected in the current space without hitting an obstacle and may
leave the present BLE capture link on a real course. That motion class was
removed from the active collection plan; a prepared batch was cancelled before
any episode was recorded. Collision traces must not be relabelled as clean
unobstructed strokes.

## Capture and quality result

- device ID: `f383571202836e6f`
- firmware: `0.1.17`
- source rate: 50 Hz
- successful captures: 11
- clean unobstructed putts: 10
- mixed putt-plus-obstacle captures: 1 (`r05`)
- continuity/metadata failures: 0
- successful-capture quality: 0 `PASS`, 11 `WARN`, 0 `FAIL`
- ADXL367 clipping: 11/11 episodes
- BMI270 accelerometer clipping: 0/11 episodes
- BMI270 gyroscope clipping: 10/11 episodes

Even gentle putts rotate the assembled Ball fast enough to saturate the
BMI270's configured gyroscope range in most episodes. This is expected evidence
against using measured gyro peak as a calibrated speed estimate. BMI270
acceleration retained full range throughout.

## Post-GO clean comparison

| Feature | Pickup holdout, n=10 | Clean gentle putts, n=10 | Interpretation |
|---|---:|---:|---|
| Accel-norm stdev (m/s²) | 1.474-4.864 | 2.599-6.997 | overlaps |
| Gyro RMS (rad/s) | 1.708-4.531 | 8.564-22.805 | separated here; putts partly clipped |
| Gyro peak (rad/s) | 6.934-17.385 | 32.617-52.089 | separated here; putts partly clipped |
| Jerk peak (m/s³) | 318.272-1294.090 | 1771.870-4855.900 | separated in this setup |
| Active-sample fraction | 0.318-0.772 | 0.270-0.491 | overlaps |

Gentle putts can exceed pickup acceleration variability, so that feature is
again unsafe alone. In this setup, sustained sphere rotation and stronger jerk
separate clean putts from pickup/carry. Because most putt gyro traces clip, the
observed gyro statistics are lower-bound/shape evidence rather than calibrated
true peaks.

The data strengthens the rationale for the frozen V0 combination: pickup is
not merely a large impulse, while ordinary rolling has strong, axis-consistent
angular motion. Exact raw V0 evaluation remains gated on the executable
vertical-impulse/gyro-shape evaluator rather than retrospective threshold
tuning.

## Files

- `manifest.json` provides episode identity and known provenance.
- `raw/` contains all original successful captures and the separately named
  clean replacement.
- `analysis/dataset_summary.csv` and `.json` contain deterministic features.
- `analysis/quality_report.json` records structural quality outcomes.
- `analysis/plots/` contains dependency-free per-episode traces.

Regenerate the derived analysis with:

```bash
python tools/analyze_motion_dataset.py \
  experiments/research_ball_r1_pickup_precision_1d_gentle/manifest.json \
  --output-dir experiments/research_ball_r1_pickup_precision_1d_gentle/analysis
```
