# Pickup precision phase 1A: no-lift handling

## Scope

This immutable evidence set contains ten operator-labelled `handling` episodes
captured from the assembled Research Ball after a device-side GO marker. The
planned actions were three light touches/presses, three rotations in place and
four short slides. The Ball was reported to remain in contact with the surface
throughout every episode.

The dataset is a false-pickup control. It does not establish that a pickup
occurred, validate scoring or authorize automatic round invalidation. Surface
material and independent video ground truth were not recorded, so later
sessions must vary and identify those conditions.

## Capture and quality result

- device ID: `f383571202836e6f`
- firmware: `0.1.17`
- source rate: 50 Hz
- captured episodes: 10
- continuity/metadata failures: 0
- quality: 9 `PASS`, 1 `WARN`
- warning: `handling-slide-r08` contains one ADXL367 clipping sample

All ten episodes passed the armed-capture pre-GO stationary gate and contained
post-GO motion. The standard generic-motion diagnostic labelled every episode
`ACTIVE_MOTION_CANDIDATE`; that is expected and demonstrates why generic motion
must not be treated as pickup.

## Preliminary findings

Across the standard complete capture windows, the three planned action groups
had these feature ranges:

| Planned action | Accel-norm stdev (m/s²) | Gyro RMS (rad/s) | Gyro peak (rad/s) | Jerk peak (m/s³) |
|---|---:|---:|---:|---:|
| touch/press, n=3 | 0.081-0.209 | 0.903-1.992 | 4.561-11.196 | 34.902-115.613 |
| rotate in place, n=3 | 0.156-0.256 | 1.431-2.353 | 7.017-11.680 | 98.537-207.627 |
| short slide, n=4 | 0.197-0.522 | 2.056-2.882 | 6.911-14.299 | 77.017-492.304 |

Using only accepted post-GO windows, this handling session reached an
accel-norm standard deviation of `0.612 m/s²`, gyro peak of `14.299 rad/s` and
jerk peak of `492.304 m/s³`. The nine accepted earlier `pickup_carry` episodes
had minimum corresponding values of `1.977 m/s²`, `9.529 rad/s` and
`679.583 m/s³`. Acceleration variability and jerk therefore separate these two
particular sessions better than gyro peak, but this is not yet evidence for a
universal threshold: session, surface, operator and action composition differ.

The result supports the frozen V0 direction of combining vertical dynamics and
gyro shape instead of using raw peak magnitude. It does not yet report a V0
false-positive rate because the repository still lacks the executable,
unit-tested V0 evaluator identified in the PR #21 review notes.

## Files

- `manifest.json` provides episode identity and known provenance.
- `raw/` contains the original unmodified JSONL captures.
- `analysis/dataset_summary.csv` and `.json` contain deterministic features.
- `analysis/quality_report.json` records structural quality outcomes.
- `analysis/plots/` contains dependency-free per-episode traces.

Regenerate the derived analysis with:

```bash
python tools/analyze_motion_dataset.py \
  experiments/research_ball_r1_pickup_precision_1a/manifest.json \
  --output-dir experiments/research_ball_r1_pickup_precision_1a/analysis
```
