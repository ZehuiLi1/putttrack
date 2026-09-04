# IMU analysis snapshot — 2026-09-04

This directory preserves the reviewed analysis artifacts produced from the 2026-09-04 PuttTrack Research Ball IMU export. It is a **research snapshot**, not a product-accuracy claim and not Gameplay authority.

## Scope

The source package contained 161 unique raw captures and 113,867 `tag_motion` records. The most decision-relevant semantic evidence was still small: ten recent pickup/carry captures, ten nominal-putt captures of mixed label quality, the seven-episode manual-floor set and the completed 86-run programmable-roller characterization.

The current finding is that short positive vertical impulse combined with one-second gyro energy and rotation-axis consistency is worth validating for pickup detection. The present thresholds were selected after inspecting the same data and therefore remain post-hoc, research-only hypotheses.

## Files

- `IMU_ANALYSIS_REPORT_CN.md` — full Chinese engineering analysis and recommendation.
- `PICKUP_DETECTOR_V0_RESEARCH_ONLY.md` — explicit research-only detector definition and authority boundary.
- `model_benchmark_leave_one_episode_out.csv` — whole-episode small-data baseline comparison.
- `next_capture_plan.csv` — minimum next capture matrix for no-lift, rolling pickup, clean putt, collision/step and cup sequences.
- `dataset_manifest_audit_summary.csv` — category-level audit derived from the full local manifest; the complete row-level audit remains in the local delivery bundle.
- `GITHUB_NEXT_CHANGE_RECOMMENDATION.md` — proposed holdout-evaluator implementation scope.
- `figures/01_pickup_feature_space.svg` — current pickup/putt/roll feature-space view.
- `figures/02_representative_gyro_traces.svg` — representative rotation traces aligned to detected onset.
- `figures/04_model_benchmark.svg` — baseline model comparison.

## Decision boundary

Do not infer product accuracy from the current 11/11 pickup and 0/11 selected-negative replay. The detector must first pass strict no-lift controls, rolling pickup, collision/step controls and a separately collected day/session/operator holdout.

Do not copy these thresholds into Gameplay or scoring code. The next implementation target is a host/Edge holdout evaluator that reports whole-episode/session metrics, confidence intervals, clipping and provenance while keeping `authority=false`.

## Data policy

The generated ZIP bundle, raw field `runs/`, duplicate local captures and the complete row-level manifest audit remain local. Git contains only the reviewed analysis artifacts, the compact audit summary and existing curated research evidence.
